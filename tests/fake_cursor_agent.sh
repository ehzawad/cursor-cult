#!/usr/bin/env bash
set -euo pipefail

contains_role() {
  local list=${1:-} role=${2:-}
  [[ ",$list," == *",$role,"* ]]
}

if [[ ${1:-} == "status" ]]; then
  echo "Logged in with browser session"
  exit 0
fi
if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  help="cursor-agent -p --output-format stream-json --mode --model --resume --force --trust --approve-mcps"
  [[ ${FAKE_CURSOR_NO_DISABLE_PROJECT_CONFIGS:-0} == 1 ]] || help="$help --disable-project-configs"
  echo "$help"
  exit 0
fi
if [[ ${1:-} == "--version" ]]; then
  echo "cursor-agent 2026.08"
  exit 0
fi

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
disable_project_configs=0
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  case ${args[$i]} in
    --force) force=1 ;;
    --trust) trust=1 ;;
    --mode) ((i+=1)); mode=${args[$i]:-} ;;
    --resume) ((i+=1)); resume=${args[$i]:-} ;;
    --resume=*) resume=${args[$i]#--resume=} ;;
    --disable-project-configs) disable_project_configs=1 ;;
  esac
done

if [[ -n ${FAKE_CURSOR_TRACE:-} ]]; then
  printf '%s|force=%s|trust=%s|mode=%s|resume=%s|project-configs-disabled=%s\n' "$role" "$force" "$trust" "$mode" "$resume" "$disable_project_configs" >> "$FAKE_CURSOR_TRACE"
fi

if [[ ${FAKE_CURSOR_REQUIRE_PROJECT_CONFIGS_DISABLED:-0} == 1 && $disable_project_configs != 1 ]]; then
  echo "project configs were not disabled" >&2
  exit 96
fi

if [[ -n ${FAKE_CURSOR_ASSERT_EFFECTIVE_DENIES:-} || -n ${FAKE_CURSOR_ASSERT_EFFECTIVE_NOT_DENIES:-} ]]; then
  python3 - "$CURSOR_CONFIG_DIR/cli-config.json" "$PWD/.cursor/cli.json"     "$disable_project_configs" "${FAKE_CURSOR_ASSERT_EFFECTIVE_DENIES:-}"     "${FAKE_CURSOR_ASSERT_EFFECTIVE_NOT_DENIES:-}" <<'PY_FAKE_POLICY'
import json
import sys
from pathlib import Path

global_path, project_path, disabled, required, forbidden = sys.argv[1:]
config = json.loads(Path(global_path).read_text())
permissions = dict(config.get("permissions") or {})
project = Path(project_path)
if disabled != "1" and project.exists():
    value = json.loads(project.read_text())
    if isinstance(value, dict) and isinstance(value.get("permissions"), dict):
        permissions.update(value["permissions"])
deny = permissions.get("deny") or []
required_tokens = [item for item in required.split("||") if item]
forbidden_tokens = [item for item in forbidden.split("||") if item]
missing = [item for item in required_tokens if item not in deny]
present = [item for item in forbidden_tokens if item in deny]
if missing or present:
    raise SystemExit(f"effective deny mismatch missing={missing} forbidden-present={present} deny={deny}")
PY_FAKE_POLICY
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
