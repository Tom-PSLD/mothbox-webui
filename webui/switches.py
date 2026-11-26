from .config import Paths
from .controls import read_kv


def refresh_switches(paths: Paths, runner) -> dict[str, str]:
    runner.run(["python3", str(paths.mothbox_root / "GetConfigSwitches.py")])
    return read_kv(paths.controls_root / "switches.txt")


def schedule_source(switch_vals: dict[str, str]) -> str:
    return "switches" if switch_vals.get("U1") == "1" else "csv"
