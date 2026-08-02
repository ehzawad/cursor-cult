#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DESTINATION=${CURSOR_PLUGIN_DIR:-$HOME/.cursor/plugins/local}/cursor-cult
MODE=${1:---link}

case "$MODE" in
  --link|--copy) ;;
  *)
    printf 'usage: %s [--link|--copy]\n' "$0" >&2
    exit 2
    ;;
esac

mkdir -p "$(dirname -- "$DESTINATION")"
if [[ -e "$DESTINATION" || -L "$DESTINATION" ]]; then
  BACKUP="${DESTINATION}.bak.$(date +%Y%m%d%H%M%S).$$"
  mv "$DESTINATION" "$BACKUP"
  printf 'backed up %s -> %s\n' "$DESTINATION" "$BACKUP"
fi

if [[ "$MODE" == "--link" ]]; then
  ln -s "$REPO_ROOT" "$DESTINATION"
else
  mkdir -p "$DESTINATION"
  cp -R "$REPO_ROOT/.cursor-plugin" "$DESTINATION/.cursor-plugin"
  cp -R "$REPO_ROOT/agents" "$DESTINATION/agents"
  cp -R "$REPO_ROOT/skills" "$DESTINATION/skills"
  cp "$REPO_ROOT/README.md" "$REPO_ROOT/DESIGN.md" "$REPO_ROOT/SECURITY.md" \
    "$REPO_ROOT/CHANGELOG.md" "$REPO_ROOT/LICENSE" "$DESTINATION/"
fi

printf 'installed Cursor Cult plugin at %s\n' "$DESTINATION"
printf 'Reload Cursor before invoking /cursor-cult.\n'
