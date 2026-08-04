#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "login" && "${2:-}" == "status" ]]; then
  echo 'Logged in using ChatGPT'
  exit 0
fi
prompt=$(cat)
role=$(printf '%s' "$prompt" | sed -n 's/^ROLE ID: //p' | head -n1)
[[ -n "$role" ]] || role=unknown
if [[ -n "${FAKE_TRACE:-}" ]]; then
  printf 'codex|%s|%s\n' "$role" "$*" >> "$FAKE_TRACE"
fi
if [[ "${FAKE_EXPECT_STRIPPED:-}" == "1" ]]; then
  [[ -z "${OPENAI_API_KEY:-}" && -z "${OPENAI_BASE_URL:-}" && -z "${CODEX_API_KEY:-}" ]] || {
    echo 'provider api env leaked' >&2
    exit 9
  }
fi
if [[ ",${FAKE_FAIL_ROLES:-}," == *",$role,"* ]]; then
  printf '{"type":"error","message":"forced failure for %s"}\n' "$role"
  exit 1
fi
if [[ ",${FAKE_STALE_ON_RESUME_ROLES:-}," == *",$role,"* && "$*" == *" resume "* ]]; then
  printf '{"type":"error","message":"thread not found"}\n'
  exit 1
fi
if [[ ",${FAKE_SLEEP_ROLES:-}," == *",$role,"* ]]; then
  sleep "${FAKE_SLEEP_SECS:-1}"
fi
printf '{"type":"thread.started","thread_id":"codex-%s"}\n' "$role"
printf '{"type":"item.completed","item":{"type":"agent_message","text":"codex handoff role=%s"}}\n' "$role"
printf '{"type":"turn.completed"}\n'
