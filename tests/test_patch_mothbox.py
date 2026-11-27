import ast
import importlib.util
import os
import tempfile
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference_v5.2.1"

spec = importlib.util.spec_from_file_location("patch_mothbox", ROOT / "deploy" / "patch_mothbox.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

FACTORY = "[all]\nBOOT_UART=1\nBOOT_ORDER=0xf461\nNET_INSTALL_AT_POWER_ON=1\n"


EEPROM_SIZE = 2097152


def eeprom_bin(path, ts):
    data = f"xx BUILD_TIMESTAMP={ts}\n".encode()
    Path(path).write_bytes(data + b"\0" * (EEPROM_SIZE - len(data)))
    return str(path)


def load_eeprom_functions(src, eeprom_text, current_ts=200, flashrom_ts=200, latest_ts=100):
    """Extracts the EEPROM functions of a patched Scheduler.py and runs them
    against fake rpi-eeprom-config / vcgencmd / flashrom / rpi-eeprom-update."""
    tree = ast.parse(src)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and ("eeprom" in n.name)]
    module = ast.Module(body=funcs, type_ignores=[])
    applied = {}
    tmp = Path(tempfile.mkdtemp())
    latest = eeprom_bin(tmp / "pieeprom-latest.bin", latest_ts)

    class FakeSubprocess:
        @staticmethod
        def check_output(cmd):
            if cmd == ["sudo", "rpi-eeprom-config"]:
                return eeprom_text.encode()
            if cmd == ["vcgencmd", "bootloader_version"]:
                return f"2026/10/30 20:55:54\nversion abc\ntimestamp {current_ts}\n".encode()
            if cmd == ["rpi-eeprom-update", "-l"]:
                return (latest + "\n").encode()
            if cmd[:2] == ["sudo", "flashrom"]:
                assert "-r" in cmd and "-w" not in cmd
                if flashrom_ts is None:
                    raise RuntimeError("flashrom failed")
                eeprom_bin(cmd[-1], flashrom_ts)
                return b""
            raise AssertionError(cmd)

        @staticmethod
        def run(cmd, **kw):
            assert cmd[:3] == ["sudo", "rpi-eeprom-config", "--apply"]
            applied["text"] = Path(cmd[3]).read_text()
            applied["image"] = cmd[4] if len(cmd) > 4 else None

    ns = {"re": re, "os": os, "subprocess": FakeSubprocess}
    exec(compile(module, "Scheduler.py", "exec"), ns)
    if "eeprom_source_image" in ns:
        ns["eeprom_source_image"].__defaults__ = (str(tmp / "current.bin"),)
    if "eeprom_blocked_by_first_boot" in ns:
        ns["eeprom_blocked_by_first_boot"].__defaults__ = (str(tmp / "no-rc.local"),)
    if "eeprom_current_timestamp" in ns:
        ns["eeprom_current_timestamp"].__defaults__ = (str(tmp / "dt-build-timestamp"),)
    ns["_dt"] = tmp / "dt-build-timestamp"
    ns["_latest"] = latest
    ns["_dump"] = str(tmp / "current.bin")
    return ns, applied


def caller_flow(ns):
    """Same flow as Scheduler.py main code."""
    desired = {"POWER_OFF_ON_HALT": "1", "WAKE_ON_GPIO": "0"}
    current = ns["check_eeprom_settings"]()
    if all(current.get(k) == v for k, v in desired.items()):
        return False
    for k, v in desired.items():
        if k not in current or current[k] != v:
            current[k] = v
    ns["set_eeprom_settings"](current)
    return True


def test_original_scheduler_corrupts_boot_order():
    ns, applied = load_eeprom_functions((REF / "Mothbox/Scheduler.py").read_text(), FACTORY)
    caller_flow(ns)
    assert "BOOT_ORDER=0\n" in applied["text"] + "\n"


def test_patched_scheduler_keeps_boot_order_and_sections():
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY)
    assert caller_flow(ns) is True
    assert applied["text"] == (
        "[all]\nBOOT_UART=1\nBOOT_ORDER=0xf461\nNET_INSTALL_AT_POWER_ON=1\n"
        "POWER_OFF_ON_HALT=1\nWAKE_ON_GPIO=0\n"
    )


def test_patched_scheduler_replaces_existing_key_in_place():
    text = "[all]\nBOOT_UART=1\nPOWER_OFF_ON_HALT=0\nBOOT_ORDER=0xf461\n"
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, text)
    caller_flow(ns)
    assert applied["text"] == (
        "[all]\nBOOT_UART=1\nPOWER_OFF_ON_HALT=1\nBOOT_ORDER=0xf461\nWAKE_ON_GPIO=0\n"
    )


def test_patched_scheduler_no_write_when_already_correct():
    text = "[all]\nBOOT_UART=1\nPOWER_OFF_ON_HALT=1\nBOOT_ORDER=0xf461\nWAKE_ON_GPIO=0\n"
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, text)
    assert caller_flow(ns) is False
    assert applied == {}


PISHRINK_RC_LOCAL = "#!/bin/bash\ndo_expand_rootfs() {\n  reboot\n}\nraspi_config_expand\n"


def test_patched_scheduler_waits_for_first_boot_expand(tmp_path):
    rc = tmp_path / "rc.local"
    rc.write_text(PISHRINK_RC_LOCAL)
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY)
    ns["eeprom_blocked_by_first_boot"].__defaults__ = (str(rc),)
    caller_flow(ns)
    assert applied == {}


def test_patched_scheduler_writes_after_first_boot_expand(tmp_path):
    rc = tmp_path / "rc.local"
    rc.write_text("#!/bin/sh -e\nexit 0\n")
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY)
    ns["eeprom_blocked_by_first_boot"].__defaults__ = (str(rc),)
    caller_flow(ns)
    assert "POWER_OFF_ON_HALT=1" in applied["text"]


def test_patched_scheduler_writes_without_rc_local(tmp_path):
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY)
    ns["eeprom_blocked_by_first_boot"].__defaults__ = (str(tmp_path / "missing"),)
    caller_flow(ns)
    assert "POWER_OFF_ON_HALT=1" in applied["text"]


def test_patched_scheduler_keeps_current_bootloader_version():
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY, current_ts=200, flashrom_ts=200, latest_ts=100)
    caller_flow(ns)
    assert applied["image"] == ns["_dump"]


def test_patched_scheduler_never_downgrades_when_read_fails():
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY, current_ts=200, flashrom_ts=None, latest_ts=100)
    caller_flow(ns)
    assert applied == {}


def test_patched_scheduler_rejects_dump_of_other_version():
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY, current_ts=200, flashrom_ts=150, latest_ts=100)
    caller_flow(ns)
    assert applied == {}


def test_patched_scheduler_uses_packaged_image_when_not_older():
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY, current_ts=100, flashrom_ts=None, latest_ts=150)
    caller_flow(ns)
    assert applied["image"] == ns["_latest"]


def test_patched_scheduler_reads_version_from_device_tree():
    src = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    ns, applied = load_eeprom_functions(src, FACTORY, current_ts=1, flashrom_ts=None, latest_ts=150)
    ns["_dt"].write_bytes((200).to_bytes(4, "big"))
    caller_flow(ns)
    assert applied == {}


def test_patch_scheduler_is_idempotent_and_valid_python():
    once = patch.patch_scheduler((REF / "Mothbox/Scheduler.py").read_text())
    assert patch.patch_scheduler(once) == once
    ast.parse(once)
    assert once.count("def check_eeprom_settings") == 1
    assert once.count("def set_eeprom_settings") == 1


def test_patch_accesspopup_is_idempotent_and_valid_bash(tmp_path):
    once = patch.patch_accesspopup((REF / "accesspopup").read_text())
    assert patch.patch_accesspopup(once) == once
    f = tmp_path / "ap"
    f.write_text(once)
    subprocess.run(["bash", "-n", str(f)], check=True)
    # profile is no longer deleted when wlan0 is just unavailable
    assert 'grep -q "device is not available"' in once
    # profile creation no longer needs wlan0 to be up
    assert "nmcli connection add type wifi" in once


def test_ap_profile_matches_original_layout():
    text = patch.ap_profile("Mothbox-adultoAngu", "lunaluna", "192.168.50.5/24",
                            "192.168.50.254", uuid="98803cdb-239c-4dc3-b833-07d8d5ef33e2")
    assert "id=AccessPopup\n" in text
    assert "type=wifi\n" in text
    assert "mode=ap\n" in text
    assert "ssid=Mothbox-adultoAngu\n" in text
    assert "psk=lunaluna\n" in text
    assert "address1=192.168.50.5/24,192.168.50.254\n" in text
    assert "method=shared\n" in text
