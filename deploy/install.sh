#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="/"
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    *) echo "usage: install.sh [--root DIR]" >&2; exit 2 ;;
  esac
done
ROOT="${ROOT%/}"
if [ -z "$ROOT" ] && [ "$(id -u)" -ne 0 ]; then
  echo "install.sh must run as root (sudo) when installing on /" >&2
  exit 1
fi

MOTHBOX="$ROOT/home/pi/Desktop/Mothbox"
[ -d "$MOTHBOX" ] || { echo "Mothbox folder not found: $MOTHBOX" >&2; exit 1; }

echo "1/8 copy webui"
rm -rf "$MOTHBOX/webui"
mkdir -p "$MOTHBOX/webui"
( cd "$HERE/webui" && find . -type f ! -path '*/__pycache__/*' -print0 | while IFS= read -r -d '' f; do
    mkdir -p "$MOTHBOX/webui/$(dirname "$f")"
    cp "$f" "$MOTHBOX/webui/$f"
  done )

echo "2/8 systemd service (not enabled)"
install -D -m 644 "$HERE/deploy/mothbox-webui.service" "$ROOT/etc/systemd/system/mothbox-webui.service"

echo "3/8 captive portal DNS"
install -D -m 644 "$HERE/deploy/captive-dnsmasq.conf" "$ROOT/etc/NetworkManager/dnsmasq-shared.d/mothbox-captive.conf"

echo "4/8 DebugMode.py"
if ! grep -q "mothbox-webui" "$MOTHBOX/DebugMode.py"; then
  cat >> "$MOTHBOX/DebugMode.py" <<'PY'

# mothbox-webui
subprocess.run(["sudo", "systemctl", "start", "mothbox-webui"], check=False)
PY
fi

echo "5/8 hotspot name Mothbox-<name>"
AP="$ROOT/usr/bin/accesspopup"
if [ -f "$AP" ] && ! grep -q "mothbox-webui" "$AP"; then
  BLOCK="$(mktemp)"
  cat > "$BLOCK" <<'SH'
# mothbox-webui ssid begin
_mb_name=$(sed -n 's/^name=//p' "${NAMEFILE:-/boot/firmware/mothbox_custom/system/controls/name.txt}" 2>/dev/null | tr -cd 'A-Za-z0-9-' | cut -c1-24)
if [ -n "$_mb_name" ]; then ap_ssid="Mothbox-$_mb_name"; else ap_ssid='mothboxwifi'; fi
# mothbox-webui ssid end
# mothbox-webui sync begin
if nmcli -t -f NAME con show 2>/dev/null | grep -qx "$ap_profile_name"; then
	[ "$(nmcli -g 802-11-wireless.ssid con show "$ap_profile_name" 2>/dev/null)" = "$ap_ssid" ] || nmcli con modify "$ap_profile_name" 802-11-wireless.ssid "$ap_ssid" >/dev/null 2>&1
fi
# mothbox-webui sync end
SH
  sed -i "/^ap_ssid='mothboxwifi'$/d" "$AP"
  sed -i "/^ap_gate=/r $BLOCK" "$AP"
  rm -f "$BLOCK"
fi

echo "6/8 Scheduler.py: EEPROM fix (keep BOOT_ORDER)"
python3 "$HERE/deploy/patch_mothbox.py" scheduler "$MOTHBOX/Scheduler.py"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$MOTHBOX/Scheduler.py"

echo "7/8 accesspopup: keep AP profile, create it without wlan0 up"
if [ -f "$AP" ]; then
  python3 "$HERE/deploy/patch_mothbox.py" accesspopup "$AP"
  bash -n "$AP"
fi

echo "8/8 replace saved wifi networks by a clean hotspot profile"
NMC="$ROOT/etc/NetworkManager/system-connections"
mkdir -p "$NMC"
for f in "$NMC"/*; do
  [ -e "$f" ] || continue
  echo "   - $(basename "$f")"
  rm -f "$f"
done
NAMEF="$ROOT/boot/firmware/mothbox_custom/system/controls/name.txt"
_mb_name=$(sed -n 's/^name=//p' "$NAMEF" 2>/dev/null | tr -cd 'A-Za-z0-9-' | cut -c1-24 || true)
if [ -n "$_mb_name" ]; then SSID="Mothbox-$_mb_name"; else SSID="mothboxwifi"; fi
PSK=$(sed -n "s/^ap_pw='\(.*\)'$/\1/p" "$AP" 2>/dev/null | head -1)
[ -n "$PSK" ] || PSK="lunaluna"
python3 "$HERE/deploy/patch_mothbox.py" ap-profile "$NMC/AccessPopup.nmconnection" \
  "$SSID" "$PSK" "192.168.50.5/24" "192.168.50.254"
echo "   + AccessPopup.nmconnection (ssid $SSID)"

echo "done"
