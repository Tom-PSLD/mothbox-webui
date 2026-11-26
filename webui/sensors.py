import re
import shutil
from pathlib import Path

from .config import Paths
from .controls import read_kv

THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")
VOLTAGE_RE = re.compile(r"Voltage:\s*([\d.]+)")


def battery_percent(voltage, bat20, bat80):
    if voltage is None or bat80 == bat20:
        return None
    percent = 20 + (voltage - bat20) * 60 / (bat80 - bat20)
    return round(max(0, min(percent, 100)))


def _float(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _voltage(paths: Paths, runner):
    runner.run(["python3", str(paths.mothbox_root / "scripts/3v3SensorsOn.py")])
    r = runner.run(["python3", str(paths.mothbox_root / "scripts/read_Vin.py")])
    match = VOLTAGE_RE.search(r.stdout) if r.ok else None
    return float(match.group(1)) if match else None


def _cpu_temp(thermal_path: Path):
    try:
        return round(int(Path(thermal_path).read_text().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def _gps(paths: Paths, key: str):
    value = read_kv(paths.controls_root / f"{key}.txt").get(key, "")
    if not value or value.lower().startswith("err") or value.lower() == "n/a":
        return None
    return value


def read_sensors(paths: Paths, runner, settings: dict, thermal_path: Path = THERMAL) -> dict:
    voltage = _voltage(paths, runner)
    bat20 = _float(settings.get("bat_20perVolts"))
    bat80 = _float(settings.get("bat_80perVolts"))
    percent = None if bat20 is None or bat80 is None else battery_percent(voltage, bat20, bat80)
    lat, lon = _gps(paths, "lat"), _gps(paths, "lon")
    if lat is None or lon is None:
        lat = lon = None
    return {
        "voltage": voltage,
        "percent": percent,
        "cpu_temp": _cpu_temp(thermal_path),
        "disk_free_gb": round(shutil.disk_usage("/").free / 1e9, 1),
        "lat": lat,
        "lon": lon,
    }
