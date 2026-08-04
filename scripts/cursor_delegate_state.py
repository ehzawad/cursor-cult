"""State, staging, authentication, and prompt contracts for Cursor delegation."""
from cursor_delegate_model import *

def parse_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def validate_intent_capsule(text: str) -> None:
    missing = [heading for heading in INTENT_HEADINGS if heading not in text]
    if missing:
        raise UsageError("context is missing mandatory Intent Capsule headings: " + ", ".join(missing))
    sections = parse_markdown_sections(text)
    empty = [name for name in NONEMPTY_INTENT_SECTIONS if not sections.get(name, "").strip()]
    if empty:
        raise UsageError("Intent Capsule sections must be non-empty: " + ", ".join(empty))


def read_context(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise UsageError(f"context file not found: {path}") from exc
    if not text.strip():
        raise UsageError("context file must be non-empty")
    validate_intent_capsule(text)
    return text


def validate_private_staging(roles_path: Path, context_path: Path) -> None:
    for path in (roles_path, context_path):
        if path.is_symlink():
            raise UsageError(f"staging input must not be a symlink: {path}")
        try:
            path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise UsageError(f"staging input does not exist: {path}") from exc
    parent = roles_path.resolve().parent
    if parent != context_path.resolve().parent:
        raise UsageError("roles and context must share one private staging directory")
    if parent.is_symlink():
        raise UsageError("staging directory must not be a symlink")
    info = parent.stat()
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise UsageError("staging directory must be owned by the current user")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise UsageError("staging directory must be private (mode 0700)")


def validate_write_authority(roles: Sequence[DelegateRole], writer_ids: set[str]) -> None:
    role_ids = {role.id for role in roles}
    unknown = writer_ids - role_ids
    if unknown:
        raise UsageError("unknown writer role(s): " + ", ".join(sorted(unknown)))
    if len(writer_ids) > 1:
        raise UsageError("one shared worktree permits one writer")
    unauthorized = sorted(role.id for role in roles if role.mode == "agent" and role.id not in writer_ids)
    if unauthorized:
        raise UsageError("role(s) declare mode 'agent' without --writer: " + ", ".join(unauthorized))
    inert = sorted(role.id for role in roles if role.id in writer_ids and role.mode != "agent")
    if inert:
        raise UsageError("--writer role(s) must declare mode 'agent': " + ", ".join(inert))


def project_root(cwd: Path) -> Path:
    current = cwd.expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def state_root() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "cursor-cult" / "delegates"


def derive_session_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    for key in (
        "CURSOR_CULT_DELEGATE_SESSION_KEY",
        "CURSOR_AGENT_SESSION_ID",
        "CURSOR_SESSION_ID",
        "TERM_SESSION_ID",
        "TMUX_PANE",
        "STY",
        "VSCODE_PID",
    ):
        value = os.environ.get(key)
        if value:
            return f"{key.lower()}:{value}"
    return "project"


def short_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def session_path(root: Path, session_key: str, role: DelegateRole) -> Path:
    name = f"{short_hash(str(root))}-{short_hash(session_key)}__{role.provider}__{role.id}.json"
    return state_root() / "sessions" / name


def load_session(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        quarantine = path.with_name(f"{path.name}.corrupt.{time.time_ns()}")
        with contextlib.suppress(OSError):
            path.rename(quarantine)
        return None
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    return session_id if isinstance(session_id, str) and session_id else None


def save_session(path: Path, role: DelegateRole, session_key: str, session_id: str) -> None:
    atomic_write_json(
        path,
        {
            "provider": role.provider,
            "role_id": role.id,
            "role_label": role.label,
            "session_key": session_key,
            "session_id": session_id,
            "updated_at": utc_now(),
        },
    )


def delegation_depth() -> int:
    raw = os.environ.get("CURSOR_CULT_DELEGATION_DEPTH", "0")
    try:
        depth = int(raw)
    except ValueError as exc:
        raise UsageError("CURSOR_CULT_DELEGATION_DEPTH must be an integer") from exc
    if depth < 0:
        raise UsageError("CURSOR_CULT_DELEGATION_DEPTH must not be negative")
    return depth


def sanitized_provider_env(provider: str, keep_api_env: bool) -> dict[str, str]:
    env = dict(os.environ)
    if not keep_api_env:
        keys = CODEX_API_ENV_KEYS if provider == "codex" else CLAUDE_API_ENV_KEYS
        for key in keys:
            env.pop(key, None)
    env["CURSOR_CULT_DELEGATION_DEPTH"] = str(delegation_depth() + 1)
    return env


def find_binary(provider: str, explicit: str | None) -> str:
    candidates = [explicit] if explicit else []
    override = os.environ.get(f"CURSOR_CULT_{provider.upper()}_BIN")
    if override:
        candidates.append(override)
    candidates.append(provider)
    for candidate in candidates:
        if candidate:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
    raise UsageError(f"{provider} CLI not found; install it or set CURSOR_CULT_{provider.upper()}_BIN")


def probe_provider(provider: str, binary: str, root: Path, keep_api_env: bool) -> str:
    command = [binary, "login", "status"] if provider == "codex" else [binary, "auth", "status"]
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            env=sanitized_provider_env(provider, keep_api_env),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UsageError(f"failed to check {provider} authentication: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stdout.strip()[-2000:]
        login = "codex login" if provider == "codex" else "claude auth login"
        raise UsageError(f"{provider} CLI is not authenticated; run `{login}`. Details: {detail or 'status failed'}")
    return proc.stdout.strip()


