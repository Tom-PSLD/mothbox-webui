#!/bin/bash
# Builds a Mothbox image with the web UI from a stock image.
# usage: sudo deploy/build_image.sh <stock.img> <output.img>
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
[ $# -eq 2 ] || { echo "usage: sudo $0 <stock.img> <output.img>" >&2; exit 2; }
SRC="$1"; OUT="$2"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$SRC" ] || { echo "not found: $SRC" >&2; exit 1; }
[ -e "$OUT" ] && { echo "already exists: $OUT" >&2; exit 1; }

MNT="$(mktemp -d)"
LOOP=""
cleanup() {
  set +e
  mountpoint -q "$MNT/boot/firmware" && umount "$MNT/boot/firmware"
  mountpoint -q "$MNT" && umount "$MNT"
  [ -n "$LOOP" ] && losetup -d "$LOOP"
  rmdir "$MNT"
}
trap cleanup EXIT

echo "copy $SRC -> $OUT"
cp --sparse=always "$SRC" "$OUT"

LOOP="$(losetup -fP --show "$OUT")"
mount "${LOOP}p2" "$MNT"
mount "${LOOP}p1" "$MNT/boot/firmware"

bash "$HERE/deploy/install.sh" --root "$MNT"

sync
cleanup
trap - EXIT

if command -v e2fsck >/dev/null; then
  LOOP="$(losetup -fP --show "$OUT")"
  e2fsck -fn "${LOOP}p2" >/dev/null && echo "rootfs check OK"
  losetup -d "$LOOP"; LOOP=""
fi

chown --reference="$(dirname "$OUT")" "$OUT"
echo "zip..."
( cd "$(dirname "$OUT")" && zip -q "$(basename "$OUT").zip" "$(basename "$OUT")" \
  && sha256sum "$(basename "$OUT").zip" > "$(basename "$OUT").zip.sha256" \
  && chown --reference=. "$(basename "$OUT").zip" "$(basename "$OUT").zip.sha256" )
echo "done: $OUT"
