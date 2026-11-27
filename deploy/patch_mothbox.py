#!/usr/bin/env python3
"""Fixes applied to the stock Mothbox v5.2.1 files by install.sh.

scheduler <Scheduler.py>      EEPROM: only change POWER_OFF_ON_HALT / WAKE_ON_GPIO,
                              keep every other line (BOOT_ORDER=0xf461, [all]...).
                              The stock regex (\\w+)=(\\d+) turned BOOT_ORDER=0xf461
                              into BOOT_ORDER=0 and dropped [all].
accesspopup <accesspopup>     Hotspot: do not delete the AP profile when wlan0 is
                              only temporarily unavailable, and create the profile
                              without needing wlan0 to be up.
ap-profile <file> <ssid> <psk> <ip/cidr> <gateway>
                              Writes a ready AccessPopup NetworkManager profile.
"""
import sys
import uuid as uuidlib
from pathlib import Path

MARK = "mothbox-webui"

EEPROM_CODE = '''def check_eeprom_settings():  # mothbox-webui eeprom fix
    """Returns the current EEPROM settings as {key: value}, values kept verbatim
    (BOOT_ORDER=0xf461 stays "0xf461")."""
    output = subprocess.check_output(["sudo", "rpi-eeprom-config"]).decode("utf-8")
    settings = {}
    for line in output.splitlines():
        match = re.match(r"\\s*(\\w+)\\s*=\\s*(\\S+)", line)
        if match:
            settings[match.group(1)] = match.group(2)
    return settings


def merge_eeprom_config(current_text, wanted):
    """Sets only the keys of `wanted`; every other line is kept as is."""
    lines = current_text.splitlines()
    done = set()
    for i, line in enumerate(lines):
        match = re.match(r"\\s*(\\w+)\\s*=", line)
        if match and match.group(1) in wanted:
            lines[i] = f"{match.group(1)}={wanted[match.group(1)]}"
            done.add(match.group(1))
    for key, value in wanted.items():
        if key not in done:
            lines.append(f"{key}={value}")
    return "\\n".join(lines) + "\\n"


def set_eeprom_settings(settings):
    """Applies the settings that differ from the current EEPROM, without
    touching anything else (BOOT_ORDER, sections...)."""
    current_text = subprocess.check_output(["sudo", "rpi-eeprom-config"]).decode("utf-8")
    current = {}
    for line in current_text.splitlines():
        match = re.match(r"\\s*(\\w+)\\s*=\\s*(\\S+)", line)
        if match:
            current[match.group(1)] = match.group(2)
    wanted = {k: str(v) for k, v in settings.items() if current.get(k) != str(v)}
    if not wanted:
        return
    if "BOOT_ORDER" in wanted:
        print("Refusing to change BOOT_ORDER in EEPROM")
        return
    config_content = merge_eeprom_config(current_text, wanted)

    with open("/tmp/eeprom_config.txt", "w") as f:
        f.write(config_content)

    subprocess.run(["sudo", "rpi-eeprom-config", "--apply", "/tmp/eeprom_config.txt"])


'''


def patch_scheduler(src: str) -> str:
    if f"{MARK} eeprom fix" in src:
        return src
    start = src.index("def check_eeprom_settings():")
    set_def = src.index("def set_eeprom_settings(", start)
    end = src.index("\ndef ", set_def + 1) + 1
    return src[:start] + EEPROM_CODE + src[end:]


AP_UP_OLD = '''	if [ $stat -ne 0 ] ; then
		#activating AP failed
'''
AP_UP_NEW = '''	if [ $stat -ne 0 ] && ! echo "$apup" | grep -q "device is not available" ; then # mothbox-webui keep-profile
		#activating AP failed
'''

AP_NEW_OLD = '''nmcli device wifi hotspot ifname $wdev0 con-name "$ap_profile_name" ssid "$ap_ssid" band bg channel 6 password "$ap_pw" >/dev/null 2>&1
nmcli connection modify "$ap_profile_name" ipv4.method shared ipv4.addr "$ap_ip" ipv4.gateway "$ap_gate" >/dev/null 2>&1
'''
AP_NEW_NEW = '''# mothbox-webui add-profile: create without activating, works even if wlan0 is not up yet
if ! nmcli connection add type wifi ifname $wdev0 con-name "$ap_profile_name" autoconnect no ssid "$ap_ssid" \\
	802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \\
	802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.proto rsn \\
	802-11-wireless-security.group ccmp 802-11-wireless-security.pairwise ccmp \\
	802-11-wireless-security.psk "$ap_pw" \\
	ipv4.method shared ipv4.addresses "$ap_ip" ipv4.gateway "$ap_gate" ipv6.method ignore >/dev/null 2>&1; then
nmcli device wifi hotspot ifname $wdev0 con-name "$ap_profile_name" ssid "$ap_ssid" band bg channel 6 password "$ap_pw" >/dev/null 2>&1
nmcli connection modify "$ap_profile_name" ipv4.method shared ipv4.addr "$ap_ip" ipv4.gateway "$ap_gate" >/dev/null 2>&1
fi
'''


def patch_accesspopup(src: str) -> str:
    for old, new, tag in ((AP_UP_OLD, AP_UP_NEW, "keep-profile"),
                          (AP_NEW_OLD, AP_NEW_NEW, "add-profile")):
        if f"{MARK} {tag}" in src:
            continue
        if src.count(old) != 1:
            raise SystemExit(f"accesspopup: block for {tag} not found")
        src = src.replace(old, new)
    return src


def ap_profile(ssid, psk, ip, gateway, uuid=None):
    return f"""[connection]
id=AccessPopup
uuid={uuid or uuidlib.uuid4()}
type=wifi
autoconnect=false
interface-name=wlan0

[wifi]
band=bg
channel=6
mode=ap
ssid={ssid}

[wifi-security]
group=ccmp;
key-mgmt=wpa-psk
pairwise=ccmp;
proto=rsn;
psk={psk}

[ipv4]
address1={ip},{gateway}
method=shared

[ipv6]
addr-gen-mode=default
method=ignore

[proxy]
"""


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd in ("scheduler", "accesspopup") and len(argv) == 3:
        path = Path(argv[2])
        fn = patch_scheduler if cmd == "scheduler" else patch_accesspopup
        path.write_text(fn(path.read_text()))
    elif cmd == "ap-profile" and len(argv) == 7:
        path = Path(argv[2])
        path.write_text(ap_profile(*argv[3:7]))
        path.chmod(0o600)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
