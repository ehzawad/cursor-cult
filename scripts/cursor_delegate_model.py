#!/usr/bin/env python3
"""Delegate task-specific roles from Cursor to authenticated Codex and Claude CLIs."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

VERSION = "0.5.0"
ROLE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
PROVIDERS = {"codex", "claude"}
MODES = {"ask", "plan", "agent"}
INTENT_HEADINGS = (
    "# Intent Capsule",
    "## Verbatim request",
    "## Authorized outcome",
    "## Hard constraints and non-goals",
    "## Explicit lenses or panel requests",
    "## Authority boundaries",
    "## Acceptance evidence",
)
NONEMPTY_INTENT_SECTIONS = (
    "Verbatim request",
    "Authorized outcome",
    "Authority boundaries",
    "Acceptance evidence",
)
CODEX_API_ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_ORGANIZATION",
    "OPENAI_PROJECT",
    "OPENAI_PROJECT_ID",
    "CODEX_API_KEY",
)
CLAUDE_API_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
)
STALE_CODEX_MARKERS = (
    "no rollout found",
    "thread not found",
    "session not found",
    "session expired",
    "thread expired",
)
STALE_CLAUDE_MARKERS = (
    "no conversation found",
    "conversation not found",
    "session not found",
    "not a valid session",
    "is not a uuid",
    "requires a valid session",
)


class UsageError(RuntimeError):
    """Invalid invocation or local configuration."""


@dataclasses.dataclass(frozen=True)
class DelegateRole:
    id: str
    provider: str
    label: str
    instruction: str
    mode: str = "ask"
    model: str | None = None


@dataclasses.dataclass
class DelegateResult:
    role: DelegateRole
    ok: bool
    text: str = ""
    error: str | None = None
    session_id: str | None = None
    exit_code: int | None = None
    resumed: bool = False
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": dataclasses.asdict(self.role),
            "ok": self.ok,
            "text": self.text,
            "error": self.error,
            "session_id": self.session_id,
            "exit_code": self.exit_code,
            "resumed": self.resumed,
            "duration_ms": self.duration_ms,
        }


@dataclasses.dataclass
class ActiveProcessRegistry:
    processes: dict[str, asyncio.subprocess.Process] = dataclasses.field(default_factory=dict)
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)

    async def add(self, role_id: str, proc: asyncio.subprocess.Process) -> None:
        async with self.lock:
            self.processes[role_id] = proc

    async def remove(self, role_id: str, proc: asyncio.subprocess.Process) -> None:
        async with self.lock:
            if self.processes.get(role_id) is proc:
                self.processes.pop(role_id, None)

    async def terminate_all(self) -> None:
        async with self.lock:
            procs = list(self.processes.values())
        await asyncio.gather(*(terminate_process_group(proc) for proc in procs), return_exceptions=True)


class AsyncFileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any | None = None

    async def __aenter__(self) -> "AsyncFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.handle = self.path.open("a+")
        while True:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                await asyncio.sleep(0.1)

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.handle is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UsageError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"invalid JSON in {path}: {exc}") from exc


def parse_roles(path: Path) -> list[DelegateRole]:
    raw = load_json(path)
    if not isinstance(raw, list) or not raw:
        raise UsageError("roles file must be a non-empty JSON array")
    roles: list[DelegateRole] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise UsageError(f"role[{index}] must be an object")
        role_id = item.get("id")
        provider = item.get("provider")
        label = item.get("label")
        instruction = item.get("instruction")
        mode = item.get("mode", "ask")
        model = item.get("model")
        if not isinstance(role_id, str) or ROLE_ID_RE.fullmatch(role_id) is None:
            raise UsageError(f"role[{index}].id must match {ROLE_ID_RE.pattern}")
        if role_id in seen:
            raise UsageError(f"duplicate role id: {role_id}")
        if provider not in PROVIDERS:
            raise UsageError(f"role[{index}].provider must be codex or claude")
        if not isinstance(label, str) or not label.strip():
            raise UsageError(f"role[{index}].label must be non-empty")
        if isinstance(instruction, list):
            instruction = "\n".join(str(part).strip() for part in instruction if str(part).strip())
        if not isinstance(instruction, str) or not instruction.strip():
            raise UsageError(f"role[{index}].instruction must be non-empty")
        if mode not in MODES:
            raise UsageError(f"role[{index}].mode must be ask, plan, or agent")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise UsageError(f"role[{index}].model must be a non-empty string")
        seen.add(role_id)
        roles.append(
            DelegateRole(
                id=role_id,
                provider=provider,
                label=label.strip(),
                instruction=instruction.strip(),
                mode=mode,
                model=model.strip() if isinstance(model, str) else None,
            )
        )
    return roles


