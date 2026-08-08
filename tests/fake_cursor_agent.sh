#!/usr/bin/env bash
set -euo pipefail

contains_role() {
  local list=${1:-} role=${2:-}
  [[ ",$list," == *",$role,"* ]]
}

# Option handling mirrors the real cursor-agent, because two of its properties are
# load-bearing and mismodelling either one lets a launch-blocking bug pass CI:
#
#   1. `--disable-project-configs` is REAL but HIDDEN. Cursor registers it with
#      Commander's `.hideHelp()`, so it works and never appears in `--help`. A fake that
#      prints it in `--help` makes a help-text capability probe look correct when it can
#      never be correct against the real binary.
#   2. `--help` and `--version` short-circuit BEFORE option validation, so
#      `cursor-agent --any-nonsense --help` exits 0. Any probe built on them reports
#      every imaginable flag as supported. Unknown options are otherwise rejected as
#      `error: unknown option '<x>'` with exit 1.
#
# FAKE_CURSOR_LEGACY=1 models a CLI that genuinely lacks the flag — rejection, not
# omission from help — so fail-closed behaviour is testable in both directions.
for _arg in "$@"; do
  case $_arg in
    --help|-h)
      # Deliberately omits --disable-project-configs. The real binary hides it.
      echo "cursor-agent -p --output-format stream-json --mode --model --resume --force --trust --approve-mcps"
      exit 0 ;;
    --version|-v)
      echo "cursor-agent 2026.08"
      exit 0 ;;
  esac
done

_skip_value=0
for _arg in "$@"; do
  if [[ $_skip_value == 1 ]]; then _skip_value=0; continue; fi
  case $_arg in
    --output-format|--mode|--model|--resume) _skip_value=1; continue ;;
    --disable-project-configs)
      if [[ ${FAKE_CURSOR_LEGACY:-0} == 1 ]]; then
        echo "error: unknown option '--disable-project-configs'" >&2
        exit 1
      fi
      continue ;;
    -p|--print|--force|--trust|--approve-mcps) continue ;;
    --*)
      echo "error: unknown option '$_arg'" >&2
      exit 1 ;;
  esac
done

# `mcp list` is the capability probe target: cheap, parses options, no auth round-trip.
if [[ " $* " == *" mcp "* && " $* " == *" list "* ]]; then
  echo "No MCP servers configured (expected in .cursor/mcp.json or ~/.cursor/mcp.json)"
  exit 0
fi

for _arg in "$@"; do
  if [[ $_arg == status ]]; then
    echo "Logged in with browser session"
    exit 0
  fi
done

if [[ ${FAKE_CURSOR_EXPECT_STRIPPED:-0} == 1 ]]; then
  if [[ -n ${CURSOR_API_KEY:-} || -n ${CURSOR_AGENT_API_KEY:-} ]]; then
    echo "API key environment leaked" >&2
    exit 97
  fi
fi

prompt=${!#}
role=$(printf '%s\n' "$prompt" | sed -n 's/^ROLE ID: //p' | head -n1)
[[ -n $role ]] || role=unknown
force=0
trust=0
mode=""
resume=""
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  case ${args[$i]} in
    --force) force=1 ;;
    --trust) trust=1 ;;
    --mode) ((i+=1)); mode=${args[$i]:-} ;;
    --resume) ((i+=1)); resume=${args[$i]:-} ;;
    --resume=*) resume=${args[$i]#--resume=} ;;
  esac
done

if [[ -n ${FAKE_CURSOR_TRACE:-} ]]; then
  printf '%s|force=%s|trust=%s|mode=%s|resume=%s\n' "$role" "$force" "$trust" "$mode" "$resume" >> "$FAKE_CURSOR_TRACE"
fi

if contains_role "${FAKE_CURSOR_SLEEP_ROLES:-}" "$role"; then
  sleep "${FAKE_CURSOR_SLEEP_SECS:-2}"
fi

auth=${FAKE_CURSOR_AUTH_SOURCE:-login}
session="session-$role"
printf '{"type":"system","subtype":"init","apiKeySource":"%s","session_id":"%s"}\n' "$auth" "$session"

if [[ $resume == stale ]]; then
  printf '{"type":"result","subtype":"error","is_error":true,"result":"session not found"}\n'
  exit 1
fi
if contains_role "${FAKE_CURSOR_FAIL_ROLES:-}" "$role"; then
  printf '{"type":"result","subtype":"error","is_error":true,"result":"forced failure for %s"}\n' "$role"
  exit 1
fi
if contains_role "${FAKE_CURSOR_NO_RESULT_ROLES:-}" "$role"; then
  exit 0
fi
if contains_role "${FAKE_CURSOR_EMPTY_RESULT_ROLES:-}" "$role"; then
  printf '{"type":"result","subtype":"success","is_error":false,"result":""}\n'
  exit 0
fi
if contains_role "${FAKE_CURSOR_HUGE_LINE_ROLES:-}" "$role"; then
  pad=$(head -c "${FAKE_CURSOR_HUGE_LINE_BYTES:-100000}" /dev/zero | tr '\0' 'x')
  printf '{"type":"result","subtype":"success","is_error":false,"result":"handoff role=%s pad=%s END_OF_HUGE_LINE"}\n' "$role" "$pad"
  exit 0
fi
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n'
printf '{"type":"result","subtype":"success","is_error":false,"result":"handoff role=%s force=%s"}\n' "$role" "$force"
