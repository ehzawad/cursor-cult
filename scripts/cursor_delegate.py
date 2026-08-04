#!/usr/bin/env python3
"""Cursor-hosted delegation to authenticated Codex and Claude CLIs."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from cursor_delegate_runtime import *  # noqa: F401,F403,E402

def result_status(results: Sequence[DelegateResult]) -> str:
    successes = sum(1 for result in results if result.ok)
    if successes == len(results):
        return "succeeded"
    if successes:
        return "partial"
    return "failed"


def exit_code_for_status(status: str) -> int:
    return {"succeeded": 0, "partial": 3, "failed": 1, "cancelled": 130}.get(status, 2)


def render_markdown(results: Sequence[DelegateResult]) -> str:
    lines = ["# Cursor Cult delegate report", "", f"Fleet status: **{result_status(results)}**", ""]
    for result in results:
        lines.extend(
            [
                f"## {result.role.label} (`{result.role.id}`)",
                "",
                f"Provider: `{result.role.provider}`",
                f"Status: **{'ok' if result.ok else 'failed'}**",
                f"Duration: `{result.duration_ms} ms`",
            ]
        )
        if result.session_id:
            lines.append(f"Session: `{result.session_id}`")
        if result.resumed:
            lines.append("Resumed: `true`")
        if result.error:
            lines.extend(("", "```text", result.error, "```"))
        if result.text:
            lines.extend(("", result.text))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_json(results: Sequence[DelegateResult]) -> str:
    return json.dumps(
        {"status": result_status(results), "results": [result.to_dict() for result in results]},
        indent=2,
        sort_keys=True,
    ) + "\n"


def prepare(ns: argparse.Namespace) -> tuple[list[DelegateRole], str, Path, dict[str, str], dict[str, str]]:
    if delegation_depth() >= 1:
        raise UsageError("nested delegation is blocked: a delegated Codex/Claude worker may not launch another Cursor Cult delegation")
    roles_path = Path(ns.roles_file).expanduser()
    context_path = Path(ns.context_file).expanduser()
    if not ns.unsafe_staging:
        validate_private_staging(roles_path, context_path)
    roles = parse_roles(roles_path)
    context = read_context(context_path)
    root = project_root(Path(ns.cwd))
    validate_write_authority(roles, set(ns.writer))
    binaries: dict[str, str] = {}
    statuses: dict[str, str] = {}
    for provider in sorted({role.provider for role in roles}):
        explicit = ns.codex_bin if provider == "codex" else ns.claude_bin
        binary = find_binary(provider, explicit)
        binaries[provider] = binary
        statuses[provider] = probe_provider(provider, binary, root, ns.keep_provider_api_env)
    return roles, context, root, binaries, statuses


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--roles-file", required=True)
    parser.add_argument("--context-file", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--writer", action="append", default=[])
    parser.add_argument("--max-parallel", type=int, default=int(os.environ.get("CURSOR_CULT_DELEGATE_MAX_PARALLEL", "0")))
    parser.add_argument("--session-key")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--codex-bin")
    parser.add_argument("--claude-bin")
    parser.add_argument("--keep-provider-api-env", action="store_true")
    parser.add_argument("--unsafe-staging", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cursor-cult delegate", description="Delegate Cursor roles to authenticated Codex and Claude CLIs")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="validate roles, staging, binaries, and authentication")
    add_common(check)
    run = sub.add_parser("run", help="run a mixed Codex/Claude fleet")
    add_common(run)
    run.add_argument("--format", choices=("markdown", "json"), default="markdown")
    run.add_argument("--output")
    return parser


def command_check(ns: argparse.Namespace) -> int:
    roles, _context, root, binaries, statuses = prepare(ns)
    payload = {
        "ok": True,
        "project_root": str(root),
        "roles": len(roles),
        "providers": {
            provider: {"binary": binaries[provider], "auth_status": statuses[provider]}
            for provider in sorted(binaries)
        },
        "writer": ns.writer[0] if ns.writer else None,
        "session_key": derive_session_key(ns.session_key),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


async def command_run(ns: argparse.Namespace) -> int:
    roles, context, root, binaries, _statuses = prepare(ns)
    registry = ActiveProcessRegistry()
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, task.cancel if task else lambda: None)
    try:
        results = await execute_fleet(
            roles=roles,
            root=root,
            binaries=binaries,
            context=context,
            writer_ids=set(ns.writer),
            max_parallel=ns.max_parallel,
            resume=not ns.no_resume,
            session_key=derive_session_key(ns.session_key),
            keep_api_env=ns.keep_provider_api_env,
            registry=registry,
        )
    except asyncio.CancelledError:
        await registry.terminate_all()
        return 130
    output = render_json(results) if ns.format == "json" else render_markdown(results)
    if ns.output:
        Path(ns.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return exit_code_for_status(result_status(results))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    try:
        if ns.command == "check":
            return command_check(ns)
        return asyncio.run(command_run(ns))
    except UsageError as exc:
        print(f"cursor-cult delegate: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
