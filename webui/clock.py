import time

from .config import Paths
from .controls import write_kv
from .settings_csv import write_settings

MIN_EPOCH = 1735689600
MAX_EPOCH = 4102444800


def _zones(paths: Paths) -> list[str]:
    try:
        lines = paths.timezone_list.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip()]


def list_timezones(paths: Paths) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for name in _zones(paths):
        region, _, city = name.partition("/")
        if not city:
            region, city = "Other", name
        groups.setdefault(region, []).append(city)
    return {region: sorted(cities) for region, cities in groups.items()}


def is_valid_timezone(paths: Paths, tz: str) -> bool:
    return bool(tz) and tz in _zones(paths)


def set_clock(runner, epoch_ms: int) -> int:
    seconds = int(epoch_ms) // 1000
    if not MIN_EPOCH <= seconds < MAX_EPOCH:
        raise ValueError("bad_time")
    before = time.time()
    if not runner.run(["date", "-u", "-s", f"@{seconds}"]).ok:
        raise RuntimeError("hardware_error")
    runner.run(["hwclock", "-w"])
    return round(seconds - before)


def set_timezone(paths: Paths, runner, tz: str) -> None:
    if not is_valid_timezone(paths, tz):
        raise ValueError("bad_timezone")
    write_settings(
        paths.settings_csv,
        paths.default_settings_csv,
        {"timezone": tz, "autoSystemTime": "True"},
    )
    write_kv(paths.controls_root / "timezone.txt", "timezone", tz)
    runner.run(["python3", str(paths.mothbox_root / "TimezoneUpdater.py")])
    time.tzset()
