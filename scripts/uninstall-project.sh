#!/usr/bin/env bash
set -euo pipefail

TARGET=${1:-$PWD}
TARGET=$(CDPATH= cd -- "$TARGET" && pwd)
rm -rf "$TARGET/.cursor/skills/cursor-cult"
for name in scout architect specialist critic reviewer verifier builder; do
  file="$TARGET/.cursor/agents/${name}.md"
  if [[ -f "$file" ]] && grep -q '^name: cursor-cult-' "$file"; then
    rm -f "$file"
  fi
done
printf 'removed Cursor Cult project-scoped assets from %s\n' "$TARGET"
