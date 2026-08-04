#!/usr/bin/env sh
set -eu
MODE=link
FORCE=0
# Codex discovers global user skills here only.
DEST=${CODEX_HOME:-"$HOME/.codex"}/skills/cursor-cult
while [ "$#" -gt 0 ]; do
  case "$1" in
    --link) MODE=link ;;
    --copy) MODE=copy ;;
    --dest) shift; DEST=$1 ;;
    --force) FORCE=1 ;;
    -h|--help) echo "Usage: $0 [--link|--copy] [--dest DIR] [--force]"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
# Install the self-contained Codex skill tree, not the repository root.
SKILL=$ROOT/codex-skills/cursor-cult
[ -f "$SKILL/SKILL.md" ] || { echo "missing Codex skill tree: $SKILL" >&2; exit 1; }
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  [ "$FORCE" -eq 1 ] || { echo "Codex skill exists: $DEST" >&2; exit 1; }
  rm -rf "$DEST"
fi
mkdir -p "$(dirname "$DEST")"
if [ "$MODE" = link ]; then
  ln -s "$SKILL" "$DEST"
else
  mkdir -m 700 "$DEST"
  cp "$SKILL/SKILL.md" "$DEST/"
  cp -R "$SKILL/scripts" "$SKILL/references" "$DEST/"
fi
printf 'Installed Cursor Cult Codex skill (%s): %s\n' "$MODE" "$DEST"
