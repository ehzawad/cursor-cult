#!/usr/bin/env python3
from __future__ import annotations

import argparse, asyncio, hashlib, json, os, re, shutil, signal, sys, tempfile
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.2.0"
DONE = "CURSOR_CULT_DONE"
ROLE_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

@dataclass(frozen=True)
class Role:
    id: str
    label: str
    instruction: str
    mode: str = "ask"

@dataclass
class Result:
    role: Role
    ok: bool
    text: str
    session_id: str | None = None
    error: str | None = None
    exit_code: int | None = None


def parse_roles(path: Path) -> list[Role]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list) or not raw:
        raise ValueError("roles file must be a non-empty JSON array")
    roles: list[Role] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"role[{i}] must be an object")
        rid = item.get("id")
        label = item.get("label")
        instruction = item.get("instruction")
        mode = item.get("mode", "ask")
        if not isinstance(rid, str) or not ROLE_ID.fullmatch(rid):
            raise ValueError(f"role[{i}].id must match {ROLE_ID.pattern}")
        if rid in seen:
            raise ValueError(f"duplicate role id: {rid}")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"role[{i}].label must be non-empty")
        if isinstance(instruction, list):
            instruction = " ".join(str(x).strip() for x in instruction if str(x).strip())
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError(f"role[{i}].instruction must be non-empty")
        if mode not in {"ask", "plan", "agent"}:
            raise ValueError(f"role[{i}].mode must be ask, plan, or agent")
        seen.add(rid)
        roles.append(Role(rid, label.strip(), instruction.strip(), mode))
    return roles


def project_root(cwd: Path) -> Path:
    cur = cwd.resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def state_path(root: Path, role_id: str) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "cursor-cult"
    key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    return base / f"{key}__{role_id}.json"


def load_session(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text())
        value = data.get("session_id")
        return value if isinstance(value, str) and value else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def save_session(path: Path, session_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"session_id": session_id}, f)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_prompt(role: Role, context: str, allow_edit: bool) -> str:
    posture = (
        "You are the sole authorized writer. You may edit files and run mutating commands when required."
        if allow_edit else
        "Work read-only. Do not modify files, create commits, or run mutating commands. Return analysis only."
    )
    return f"""You are one worker in Cursor Cult, an adaptive fleet orchestrated by a Codex or Claude Code host.

ROLE: {role.label} ({role.id})
ROLE MANDATE: {role.instruction}
ACCESS: {posture}

Work independently. Inspect the repository directly. Do not assume sibling workers can see your work. Distinguish evidence, inference, assumptions, and recommendations. Cite file paths, symbols, commands, and observed outputs. Surface nothing material as explicitly as material findings. End with a concise handoff containing: findings, evidence, risks, recommendations, unknowns, and confidence.

SHARED TASK CONTEXT
-------------------
{context}
"""


def find_cli(explicit: str | None) -> str:
    candidates = [explicit] if explicit else []
    candidates += [os.environ.get("CURSOR_CULT_CURSOR_BIN"), "cursor-agent", "agent"]
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate
    raise FileNotFoundError("Cursor CLI not found. Install it, then run `cursor-agent login`. Set CURSOR_CULT_CURSOR_BIN to override.")


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    if env.get("CURSOR_CULT_KEEP_CURSOR_API_ENV") != "1":
        for key in ("CURSOR_API_KEY", "CURSOR_AGENT_API_KEY"):
            env.pop(key, None)
    return env


def parse_stream(stdout: bytes) -> tuple[str, str | None]:
    texts: list[str] = []
    session: str | None = None
    for raw in stdout.decode("utf-8", "replace").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        sid = event.get("session_id")
        if isinstance(sid, str):
            session = sid
        if event.get("type") == "assistant":
            message = event.get("message", {})
            blocks = message.get("content", []) if isinstance(message, dict) else []
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    texts.append(block["text"])
        if event.get("type") == "result" and isinstance(event.get("result"), str) and not texts:
            texts.append(event["result"])
    return "".join(texts).strip(), session


async def run_role(cli: str, root: Path, role: Role, context: str, allow_edit: bool, resume: bool, sem: asyncio.Semaphore) -> Result:
    async with sem:
        state = state_path(root, role.id)
        sid = load_session(state) if resume else None
        args = [cli, "-p", "--output-format", "stream-json", "--mode", role.mode]
        if allow_edit:
            args.append("--force")
        if sid:
            args += ["--resume", sid]
        args.append(build_prompt(role, context, allow_edit))
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=root,
                env=clean_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            out, err = await proc.communicate()
        except asyncio.CancelledError:
            if proc is not None and proc.returncode is None:
                os.killpg(proc.pid, signal.SIGTERM)
            raise
        text, new_sid = parse_stream(out)
        if proc.returncode == 0:
            if new_sid:
                save_session(state, new_sid)
            return Result(role, True, text or "(no assistant text emitted)", new_sid, exit_code=0)
        diagnostic = err.decode("utf-8", "replace").strip()[-4000:]
        if sid and ("session" in diagnostic.lower() or "resume" in diagnostic.lower()):
            try:
                state.unlink()
            except FileNotFoundError:
                pass
        return Result(role, False, text, new_sid, diagnostic or "Cursor CLI failed", proc.returncode)


def render(results: list[Result]) -> str:
    lines = ["# Cursor Cult report", ""]
    for r in results:
        lines += [f"## {r.role.label} (`{r.role.id}`)", "", f"Status: {'ok' if r.ok else 'failed'}"]
        if r.session_id:
            lines.append(f"Session: `{r.session_id}`")
        if r.error:
            lines += ["", "```text", r.error, "```"]
        if r.text:
            lines += ["", r.text]
        lines.append("")
    return "\n".join(lines)


async def amain(ns: argparse.Namespace) -> int:
    roles = parse_roles(Path(ns.roles_file))
    context = Path(ns.context_file).read_text() if ns.context_file else ns.task
    if not context or not context.strip():
        raise ValueError("provide --task or --context-file")
    if ns.max_parallel < 1:
        raise ValueError("--max-parallel must be positive")
    writer_ids = set(ns.writer or [])
    unknown = writer_ids - {r.id for r in roles}
    if unknown:
        raise ValueError(f"unknown writer role(s): {', '.join(sorted(unknown))}")
    if len(writer_ids) > 1 and not ns.allow_multiple_writers:
        raise ValueError("multiple writers require --allow-multiple-writers and isolated worktrees")
    cli = find_cli(ns.cursor_bin)
    root = project_root(Path(ns.cwd))
    if ns.check:
        print(json.dumps({"ok": True, "cursor_bin": cli, "project_root": str(root), "roles": [r.id for r in roles]}, indent=2))
        return 0
    sem = asyncio.Semaphore(ns.max_parallel)
    tasks = [
        asyncio.create_task(run_role(cli, root, role, context, role.id in writer_ids, not ns.no_resume, sem))
        for role in roles
    ]
    try:
        results = await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return 130
    report = render(results)
    if ns.output:
        Path(ns.output).write_text(report)
    print(report)
    print(DONE, file=sys.stderr)
    return 0 if any(r.ok for r in results) else 1


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Adaptive Cursor CLI worker fleet for Codex and Claude Code hosts")
    p.add_argument("--roles-file", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--task")
    group.add_argument("--context-file")
    p.add_argument("--cwd", default=".")
    p.add_argument("--cursor-bin")
    p.add_argument("--max-parallel", type=int, default=int(os.environ.get("CURSOR_CULT_MAX_PARALLEL", "6")))
    p.add_argument("--writer", action="append", help="Role id allowed to edit; repeat only with isolated worktrees")
    p.add_argument("--allow-multiple-writers", action="store_true")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--output")
    p.add_argument("--check", action="store_true")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main() -> None:
    try:
        raise SystemExit(asyncio.run(amain(parser().parse_args())))
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"cursor-cult: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
