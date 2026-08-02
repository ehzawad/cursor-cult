#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
TARGET=$PWD
MODE=${CURSOR_CULT_INSTALL_MODE:-copy}
TARGET_SET=0

usage() {
  printf 'usage: %s [project-dir] [--copy|--link]\n' "$0" >&2
}

while (($# > 0)); do
  case "$1" in
    --copy)
      MODE=copy
      ;;
    --link)
      MODE=link
      ;;
    --help)
      usage
      exit 0
      ;;
    --*)
      usage
      exit 2
      ;;
    *)
      if ((TARGET_SET)); then
        usage
        exit 2
      fi
      TARGET=$1
      TARGET_SET=1
      ;;
  esac
  shift
done

case "$MODE" in
  copy|link) ;;
  *)
    printf 'CURSOR_CULT_INSTALL_MODE must be copy or link; received %s\n' "$MODE" >&2
    exit 2
    ;;
esac

mkdir -p "$TARGET"
TARGET=$(CDPATH= cd -- "$TARGET" && pwd)
SKILL_DEST="$TARGET/.cursor/skills/cursor-cult"
AGENT_DEST="$TARGET/.cursor/agents"
STAMP="$(date +%Y%m%d%H%M%S).$$"

backup_existing() {
  local destination=$1
  if [[ -e "$destination" || -L "$destination" ]]; then
    local backup="${destination}.bak.${STAMP}"
    mv "$destination" "$backup"
    printf 'backed up %s -> %s\n' "$destination" "$backup"
  fi
}

install_path() {
  local source=$1
  local destination=$2
  backup_existing "$destination"
  mkdir -p "$(dirname -- "$destination")"
  if [[ "$MODE" == link ]]; then
    ln -s "$source" "$destination"
  else
    cp -R "$source" "$destination"
  fi
  printf 'installed %s\n' "$destination"
}

install_path "$REPO_ROOT/skills/cursor-cult" "$SKILL_DEST"
mkdir -p "$AGENT_DEST"
for source in "$REPO_ROOT"/agents/*.md; do
  install_path "$source" "$AGENT_DEST/$(basename -- "$source")"
done

printf '\nCursor Cult installed project-scoped in %s using %s mode.\n' "$TARGET" "$MODE"
printf 'Reload Cursor, then invoke /cursor-cult <goal> in Agent mode.\n'
if [[ "$MODE" == link ]]; then
  printf 'Note: copy mode is more portable; link mode is intended for local development.\n'
fi
