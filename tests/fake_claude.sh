#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "auth" && "${2:-}" == "status" ]]; then
  echo '{"loggedIn":true}'
  exit 0
fi
prompt=$(cat)
role=$(printf '%s' "$prompt" | sed -n 's/^ROLE ID: //p' | head -n1)
[[ -n "$role" ]] || role=unknown
if [[ -n "${FAKE_TRACE:-}" ]]; then
  printf 'claude|%s|%s\n' "$role" "$*" >> "$FAKE_TRACE"
fi
if [[ "${FAKE_EXPECT_STRIPPED:-}" == "1" ]]; then
  [[ -z "${ANTHROPIC_API_KEY:-}" && -z "${ANTHROPIC_AUTH_TOKEN:-}" && -z "${ANTHROPIC_BASE_URL:-}" ]] || {
    echo 'provider api env leaked' >&2
    exit 9
  }
fi
if [[ ",${FAKE_FAIL_ROLES:-}," == *",$role,"* ]]; then
  printf '{"is_error":true,"result":"forced failure for %s","session_id":"claude-%s"}\n' "$role" "$role"
  exit 0
fi
if [[ ",${FAKE_STALE_ON_RESUME_ROLES:-}," == *",$role,"* && "$*" == *"--resume"* ]]; then
  printf '{"is_error":true,"result":"no conversation found","session_id":"claude-%s"}\n' "$role"
  exit 0
fi
if [[ ",${FAKE_SLEEP_ROLES:-}," == *",$role,"* ]]; then
  sleep "${FAKE_SLEEP_SECS:-1}"
fi
printf '{"is_error":false,"result":"claude handoff role=%s","session_id":"claude-%s"}\n' "$role" "$role"
