#!/usr/bin/env sh
set -eu
MODE=link
FORCE=0
PREFIX=${XDG_DATA_HOME:-"$HOME/.local/share"}/cursor-cult
BINDIR=${XDG_BIN_HOME:-"$HOME/.local/bin"}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --link) MODE=link ;;
    --copy) MODE=copy ;;
    --prefix) shift; PREFIX=$1 ;;
    --bindir) shift; BINDIR=$1 ;;
    --force) FORCE=1 ;;
    -h|--help) echo "Usage: $0 [--link|--copy] [--prefix DIR] [--bindir DIR] [--force]"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
if [ -e "$PREFIX" ] || [ -L "$PREFIX" ]; then
  [ "$FORCE" -eq 1 ] || { echo "installation exists: $PREFIX" >&2; exit 1; }
  rm -rf "$PREFIX"
fi
mkdir -p "$(dirname "$PREFIX")" "$BINDIR"
if [ "$MODE" = link ]; then
  ln -s "$ROOT" "$PREFIX"
else
  mkdir -m 700 "$PREFIX"
  cp -R "$ROOT/bin" "$ROOT/scripts" "$ROOT/README.md" "$ROOT/DESIGN.md" "$ROOT/SECURITY.md" "$ROOT/LICENSE" "$PREFIX/"
fi
TARGET="$BINDIR/cursor-cult"
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  [ "$FORCE" -eq 1 ] || { echo "executable exists: $TARGET" >&2; exit 1; }
  rm -f "$TARGET"
fi
ln -s "$PREFIX/bin/cursor-cult" "$TARGET"
printf 'Installed Cursor Cult (%s): %s\n' "$MODE" "$TARGET"
