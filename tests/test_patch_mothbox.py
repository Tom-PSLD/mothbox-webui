import ast
import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference_v5.2.1"

spec = importlib.util.spec_from_file_location("patch_mothbox", ROOT / "deploy" / "patch_mothbox.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

FACTORY = "[all]\nBOOT_UART=1\nBOOT_ORDER=0xf461\nNET_INSTALL_AT_POWER_ON=1\n"


def load_eeprom_functions(src, eeprom_text):
    """Extracts the EEPROM functions of a patched Scheduler.py and runs them
    against a fake rpi-eeprom-config."""
    tree = ast.parse(src)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and ("eeprom" in n.name)]
    module = ast.Module(body=funcs, type_ignores=[])
    applied = {}

    class FakeSubprocess:
        @staticmethod
        def check_output(cmd):
            assert cmd == ["sudo", "rpi-eeprom-config"]
            return eeprom_text.encode()

        @staticmethod
        def run(cmd, **kw):
            assert cmd[:3] == ["sudo", "rpi-eeprom-config", "--apply"]
            applied["text"] = Path(cmd[3]).read_text()

    ns = {"re": re, "subprocess": FakeSubprocess}
    exec(compile(module, "Scheduler.py", "exec"), ns)
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
