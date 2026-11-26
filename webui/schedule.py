from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from .settings_csv import split_multi

FALLBACK_HOURS = [19, 21, 23, 2, 4]
DAY_SWITCHES = {"d0": 7, "d1": 1, "d2": 2, "d3": 3, "d4": 4, "d5": 5, "d6": 6}


@dataclass
class Schedule:
    weekdays: list[int]
    hours: list[int]
    minute: int
    runtime: int

    def to_dict(self) -> dict:
        return asdict(self)


def _ints(value) -> list[int]:
    try:
        return split_multi(value)
    except ValueError:
        return []


def _int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def schedule_from_settings(settings: dict[str, str]) -> Schedule:
    minutes = _ints(settings.get("minute", "0"))
    return Schedule(
        weekdays=_ints(settings.get("weekday", "")),
        hours=_ints(settings.get("hour", "")),
        minute=minutes[0] if minutes else 0,
        runtime=_int(settings.get("runtime", "0")),
    )


def schedule_from_switches(switch_vals: dict[str, str]) -> Schedule:
    hour_map = {"h00": 0, **{f"h{i}": i for i in range(1, 24)}}
    hours = [h for name, h in hour_map.items() if _int(switch_vals.get(name, 0)) == 1]
    days = [d for name, d in DAY_SWITCHES.items() if _int(switch_vals.get(name, 0)) == 1]
    if not hours:
        hours = list(FALLBACK_HOURS)
    if not days:
        days = [1, 2, 3, 4, 5, 6, 7]
    return Schedule(sorted(days), sorted(hours), 0, 59)


def validate(s: Schedule) -> list[str]:
    errors = []
    if not s.weekdays:
        errors.append("no_day")
    if not s.hours:
        errors.append("no_hour")
    if any(d < 1 or d > 7 for d in s.weekdays):
        errors.append("bad_weekday")
    if any(h < 0 or h > 23 for h in s.hours):
        errors.append("bad_hour")
    if not 0 <= s.minute <= 59:
        errors.append("bad_minute")
    if not 1 <= s.runtime <= 1439:
        errors.append("bad_runtime")
    return errors


def next_session(s: Schedule, now: datetime) -> datetime | None:
    if validate(s):
        return None
    base = now.replace(second=0, microsecond=0)
    candidates = []
    for offset in range(8):
        day = (base + timedelta(days=offset)).date()
        if day.isoweekday() not in s.weekdays:
            continue
        for h in s.hours:
            start = datetime(day.year, day.month, day.day, h, s.minute)
            if start > now:
                candidates.append(start)
    return min(candidates) if candidates else None


def schedule_to_updates(s: Schedule) -> dict:
    return {
        "weekday": sorted(s.weekdays),
        "hour": list(s.hours),
        "minute": str(s.minute),
        "runtime": str(s.runtime),
    }
