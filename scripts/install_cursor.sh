#!/usr/bin/env sh
set -eu
MODE=link
FORCE=0
PROJECT=
DEST=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --link) MODE=link ;;
    --copy) MODE=copy ;;
    --project) shift; PROJECT=$1 ;;
    --dest) shift; DEST=$1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      echo "Usage: $0 [--link|--copy] [--project DIR | --dest DIR] [--force]"
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SOURCE=$ROOT/.cursor/skills/cursor-cult-delegate
if [ -n "$PROJECT" ] && [ -n "$DEST" ]; then
  echo "--project and --dest are mutually exclusive" >&2
  exit 2
fi
if [ -n "$PROJECT" ]; then
  DEST=$PROJECT/.cursor/skills/cursor-cult-delegate
elif [ -z "$DEST" ]; then
  DEST=${CURSOR_HOME:-"$HOME/.cursor"}/skills/cursor-cult-delegate
fi
[ -f "$SOURCE/SKILL.md" ] || { echo "missing Cursor skill source: $SOURCE/SKILL.md" >&2; exit 1; }
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  [ "$FORCE" -eq 1 ] || { echo "installation exists: $DEST" >&2; exit 1; }
  rm -rf "$DEST"
fi
mkdir -p "$(dirname "$DEST")"
if [ "$MODE" = link ]; then
  ln -s "$SOURCE" "$DEST"
else
  mkdir "$DEST"
  cp "$SOURCE/SKILL.md" "$DEST/SKILL.md"
fi
printf 'Installed Cursor Cult delegate skill (%s): %s\n' "$MODE" "$DEST"
