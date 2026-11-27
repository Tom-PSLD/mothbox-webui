#!/bin/bash
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
fail() { echo "FAIL: $*"; exit 1; }

mkdir -p "$ROOT/home/pi/Desktop" "$ROOT/usr/bin" "$ROOT/etc/systemd/system/multi-user.target.wants" \
         "$ROOT/etc/NetworkManager/system-connections" "$ROOT/boot/firmware"
cp -r "$HERE/reference_v5.2.1/Mothbox" "$ROOT/home/pi/Desktop/Mothbox"
cp -r "$HERE/reference_v5.2.1/mothbox_custom" "$ROOT/boot/firmware/mothbox_custom"
cp "$HERE/reference_v5.2.1/accesspopup" "$ROOT/usr/bin/accesspopup"
for p in STARLINK LIB-7449855 AccessPopup preconfigured; do
  echo "psk=secret" > "$ROOT/etc/NetworkManager/system-connections/$p.nmconnection"
done

bash "$HERE/deploy/install.sh" --root "$ROOT" > /dev/null || fail "first run"
bash "$HERE/deploy/install.sh" --root "$ROOT" > /dev/null || fail "second run"

M="$ROOT/home/pi/Desktop/Mothbox"
[ -f "$M/webui/app.py" ] || fail "webui not copied"
[ -f "$M/webui/static/index.html" ] || fail "static not copied"
[ -z "$(find "$M/webui" -name __pycache__)" ] || fail "pycache copied"
[ -f "$ROOT/etc/systemd/system/mothbox-webui.service" ] || fail "service missing"
grep -q '^ExecStart=/usr/bin/python3 -m webui$' "$ROOT/etc/systemd/system/mothbox-webui.service" || fail "ExecStart"
[ -z "$(find "$ROOT/etc/systemd" -name 'mothbox-webui.service' -path '*.wants*')" ] || fail "service enabled"
grep -q '^address=/#/192.168.50.5$' "$ROOT/etc/NetworkManager/dnsmasq-shared.d/mothbox-captive.conf" || fail "dnsmasq conf"
[ "$(grep -c 'mothbox-webui' "$M/DebugMode.py")" -eq 2 ] || fail "DebugMode marker count $(grep -c 'mothbox-webui' "$M/DebugMode.py")"
grep -q 'systemctl", "start", "mothbox-webui"' "$M/DebugMode.py" || fail "DebugMode start line"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$M/DebugMode.py" || fail "DebugMode syntax"
grep -q "^ap_ssid='mothboxwifi'$" "$ROOT/usr/bin/accesspopup" && fail "ap_ssid unchanged"
[ "$(grep -c 'mothbox-webui' "$ROOT/usr/bin/accesspopup")" -eq 6 ] || fail "accesspopup block count"
bash -n "$ROOT/usr/bin/accesspopup" || fail "accesspopup syntax"
[ "$(ls -A "$ROOT/etc/NetworkManager/system-connections")" = "AccessPopup.nmconnection" ] || fail "wifi profiles: $(ls -A "$ROOT/etc/NetworkManager/system-connections")"
NMF="$ROOT/etc/NetworkManager/system-connections/AccessPopup.nmconnection"
grep -q '^psk=secret$' "$NMF" && fail "old profile kept"
grep -q '^ssid=Mothbox-adultoAngu$' "$NMF" || fail "profile ssid"
grep -q '^psk=lunaluna$' "$NMF" || fail "profile psk"
grep -q '^mode=ap$' "$NMF" || fail "profile mode"
[ "$(stat -c %a "$NMF")" = "600" ] || fail "profile perms"
grep -q 'mothbox-webui eeprom fix' "$M/Scheduler.py" || fail "Scheduler not patched"
grep -q '(\\w+)=(\\d+)' "$M/Scheduler.py" && fail "old EEPROM regex still there"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$M/Scheduler.py" || fail "Scheduler syntax"
grep -q 'mothbox-webui keep-profile' "$ROOT/usr/bin/accesspopup" || fail "accesspopup keep-profile"
grep -q 'mothbox-webui add-profile' "$ROOT/usr/bin/accesspopup" || fail "accesspopup add-profile"

SSID=$(cd "$ROOT" && NAMEFILE="$ROOT/boot/firmware/mothbox_custom/system/controls/name.txt" bash -c "
  $(sed -n '/# mothbox-webui ssid begin/,/# mothbox-webui ssid end/p' "$ROOT/usr/bin/accesspopup")
  echo \$ap_ssid")
[ "$SSID" = "Mothbox-adultoAngu" ] || fail "ssid computed '$SSID'"

if [ "$(id -u)" -ne 0 ]; then
  bash "$HERE/deploy/install.sh" --root / > /dev/null 2>&1 && fail "should refuse non-root on /"
fi
echo OK
