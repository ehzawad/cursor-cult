#!/usr/bin/env sh
set -eu
MODE=link
FORCE=0
DEST=${AGENTS_HOME:-"$HOME/.agents"}/skills/cursor-cult
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
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  [ "$FORCE" -eq 1 ] || { echo "Codex skill exists: $DEST" >&2; exit 1; }
  rm -rf "$DEST"
fi
mkdir -p "$(dirname "$DEST")"
if [ "$MODE" = link ]; then
  ln -s "$ROOT" "$DEST"
else
  mkdir -m 700 "$DEST"
  cp "$ROOT/SKILL.md" "$ROOT/README.md" "$ROOT/DESIGN.md" "$ROOT/SECURITY.md" "$ROOT/LICENSE" "$DEST/"
  cp -R "$ROOT/scripts" "$ROOT/skills" "$ROOT/examples" "$DEST/"
fi
printf 'Installed Cursor Cult Codex skill (%s): %s\n' "$MODE" "$DEST"
