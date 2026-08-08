#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


RUNNER = "scripts/cursor_cult.py"
replace_once(
    RUNNER,
    '''    # `--force` is NOT merely a prompt suppressor. Cursor's headless documentation is
    # explicit that "without --force, changes are only proposed, not applied", so in
    # `-p` mode it is the flag that makes edits real. Read-only roles are therefore
    # held read-only by `--mode` alone, and Cursor does not document whether an
    # explicit `ask`/`plan` mode outranks `--force`. Treat that precedence as an
    # unverified external dependency, not a guarantee enforced here — which is why
    # validate_read_only_capability() refuses to launch a read-only role at all when
    # `--mode` was not positively detected.
''',
    '''    # `--force` is NOT merely a prompt suppressor. Cursor documents it as allowing
    # commands unless explicitly denied, and print mode needs it for real file edits.
    # Read-only roles therefore use three independent guards: explicit ask/plan mode,
    # generated Write(**)/Shell(*) denies, and disabled project CLI configuration so a
    # repository cannot replace those arrays. Missing capabilities fail closed.
''',
)
replace_once(
    RUNNER,
    '''    `--mode` is the only mechanism that holds an `ask`/`plan` role read-only, and it
    is emitted solely when the CLI advertises the flag. Detection fails to False when
    the `--help` probe times out, raises, or returns nothing, while every other
    capability defaults permissive — so failing open here would silently launch a
    read-only role in Cursor's default agent mode carrying `--force`, identical to an
    authorized writer. Fail closed instead: no mode flag, no read-only role.
''',
    '''    Explicit ask/plan mode is one independent guard alongside generated permission
    denies and project-config isolation. Because omitting `--mode` selects agent mode,
    a failed or empty capability probe must never silently turn a reader into a writer.
    Fail closed instead: no positively advertised mode flag, no read-only role.
''',
)

for path in ("skills/cursor-cult/SKILL.md", "codex-skills/cursor-cult/SKILL.md"):
    replace_once(
        path,
        "Mode and tool access are separate decisions. Cursor's native web/search tools do not require shell.",
        "Mode and tool access are separate decisions. When Cursor exposes native web/search tools, they use a different capability path from shell.",
    )
    replace_once(
        path,
        "Cursor Cult preserves the operator's global permission arrays and passes `--disable-project-configs` so repository `.cursor/cli.json` cannot replace them. A CLI without that capability is refused.",
        "Cursor Cult preserves the operator's global permission arrays and passes `--disable-project-configs` so repository `.cursor/cli.json` cannot replace them. This deliberately ignores that project CLI file for workers; required settings from it must be moved to the operator config or supplied explicitly. A CLI without the isolation capability is refused.",
    )
    replace_once(
        path,
        "When an isolated read-only invocation explicitly needs terminal commands, append `--readonly-shell` to the matching `run` or `start`. You may also append it to `check` to keep the requested argv visible, but current `check` only accepts the common option; it does not validate or report the generated shell permission. Never pass it only to `check`, and do not treat a successful preflight as proof of shell or network access.",
        "When an isolated read-only invocation explicitly needs terminal commands, append `--readonly-shell` to `check` and to the matching `run` or `start`. `check` validates that the fleet is one isolated ask/plan role and reports `readonly_shell: true`; it does not launch a worker or prove shell/network availability. Never validate one permission profile and execute another.",
    )

replace_once(
    "skills/cursor-cult/SKILL.md",
    "The runner derives a host-session key by checking, in order, `CURSOR_CULT_SESSION_KEY`, `CLAUDE_CODE_REMOTE_SESSION_ID`, `CLAUDE_SESSION_ID`, `CODEX_THREAD_ID`, terminal/editor fallbacks, and finally the literal `project`.",
    "The runner derives a host-session key by checking, in order, `CURSOR_CULT_SESSION_KEY`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_REMOTE_SESSION_ID`, `CLAUDE_SESSION_ID`, `CODEX_THREAD_ID`, terminal/editor fallbacks, and finally the literal `project`.",
)

replace_once(
    "README.md",
    "Workers also pass `--disable-project-configs`, because Cursor's project-level `.cursor/cli.json` permission arrays otherwise replace the global arrays and could erase the role boundary.",
    "Workers also pass `--disable-project-configs`, because Cursor's project-level `.cursor/cli.json` permission arrays otherwise replace the global arrays and could erase the role boundary. This means worker runs intentionally ignore that project CLI file; move any required settings from it to the operator config or supply them explicitly in the invocation.",
)
replace_once(
    "SECURITY.md",
    "Repository configuration cannot erase operator denies, the generated `Write(**)` / `Shell(*)` reader boundary, or protection of the generated config itself.",
    "Repository configuration cannot erase operator denies, the generated `Write(**)` / `Shell(*)` reader boundary, or protection of the generated config through Cursor's native Write tool. The tradeoff is that worker invocations ignore project `.cursor/cli.json`; settings required from that file must be promoted to trusted operator configuration or supplied explicitly. A shell-enabled role remains able to mutate anything allowed by the outer OS sandbox.",
)

print("PR #11 final review corrections applied")
