#!/usr/bin/env sh
# Mirror the canonical runner and skill trees into the packaged plugin copies.
# Claude and Codex keep separate skill sources; only the runner is shared.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

RUNNER=scripts/cursor_cult.py
CLAUDE_SRC=skills/cursor-cult
CODEX_SRC=codex-skills/cursor-cult
CLAUDE_PKG=plugins/cursor-cult/skills/cursor-cult
CODEX_PKG=plugins/cursor-cult-codex/skills/cursor-cult

status=0
mirror() {
  src=$ROOT/$1
  dst=$ROOT/$2
  if [ "$CHECK" -eq 1 ]; then
    diff -r "$src" "$dst" >/dev/null 2>&1 || { echo "out of sync: $2" >&2; status=1; }
  else
    rm -rf "$dst"
    mkdir -p "$(dirname "$dst")"
    cp -R "$src" "$dst"
  fi
}
mirror_file() {
  src=$ROOT/$1
  dst=$ROOT/$2
  if [ "$CHECK" -eq 1 ]; then
    cmp -s "$src" "$dst" || { echo "out of sync: $2" >&2; status=1; }
  else
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
  fi
}

mirror "$CLAUDE_SRC" "$CLAUDE_PKG"
mirror "$CODEX_SRC" "$CODEX_PKG"
for tree in "$CLAUDE_SRC" "$CODEX_SRC" "$CLAUDE_PKG" "$CODEX_PKG"; do
  mirror_file "$RUNNER" "$tree/scripts/cursor_cult.py"
done

[ "$CHECK" -eq 1 ] && [ "$status" -eq 0 ] && echo "packages in sync"
exit "$status"
