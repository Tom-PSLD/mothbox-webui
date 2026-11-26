from datetime import datetime

from conftest import extract_scheduler_functions
from webui.schedule import (
    Schedule,
    next_session,
    schedule_from_settings,
    schedule_from_switches,
    schedule_to_updates,
    validate,
)
from webui.settings_csv import read_settings


def test_from_settings_reference(sim_paths):
    s = schedule_from_settings(read_settings(sim_paths.settings_csv, sim_paths.default_settings_csv))
    assert s == Schedule([1, 2, 3, 4, 5, 6, 7], [19, 21, 23, 2, 4], 0, 59)


def test_from_settings_bad_values_fall_back():
    s = schedule_from_settings({"weekday": "x", "hour": "", "minute": "?", "runtime": "abc"})
    assert s == Schedule([], [], 0, 0)


def switches(**on):
    vals = {f"h{i}": "0" for i in range(1, 24)}
    vals.update({"h00": "0", **{f"d{i}": "0" for i in range(7)}})
    vals.update({k: "1" for k in on})
    return vals


def test_from_switches_mirrors_scheduler():
    s = schedule_from_switches(switches(h19=1, h21=1, d0=1, d1=1))
    assert s == Schedule([1, 7], [19, 21], 0, 59)
    ref = extract_scheduler_functions("read_switch_schedule")["read_switch_schedule"]
    for case in (switches(h19=1, h21=1, d0=1, d1=1), switches(h00=1, d6=1), switches()):
        mine = schedule_from_switches(case)
        theirs = ref(case)
        assert ",".join(map(str, mine.hours)) == theirs["hour"]
        assert ",".join(map(str, mine.weekdays)) == theirs["weekday"]
        assert mine.runtime == theirs["runtime"]
        assert str(mine.minute) == theirs["minute"]


def test_from_switches_fallback():
    s = schedule_from_switches(switches())
    assert s.hours == [2, 4, 19, 21, 23]
    assert s.weekdays == [1, 2, 3, 4, 5, 6, 7]


def test_validate_errors():
    ok = Schedule([1], [20], 0, 59)
    assert validate(ok) == []
    assert "no_day" in validate(Schedule([], [20], 0, 59))
    assert "no_hour" in validate(Schedule([1], [], 0, 59))
    assert "bad_minute" in validate(Schedule([1], [20], 60, 59))
    assert "bad_runtime" in validate(Schedule([1], [20], 0, 0))
    assert "bad_runtime" in validate(Schedule([1], [20], 0, 1440))
    assert "bad_hour" in validate(Schedule([1], [24], 0, 59))
    assert "bad_weekday" in validate(Schedule([8], [20], 0, 59))


def test_next_session_same_day():
    s = Schedule([1, 2, 3, 4, 5, 6, 7], [19, 21], 0, 59)
    assert next_session(s, datetime(2026, 11, 26, 20, 0)) == datetime(2026, 11, 26, 21, 0)


def test_next_session_next_week():
    s = Schedule([1], [19], 30, 59)
    monday = datetime(2026, 11, 23, 23, 0)
    assert next_session(s, monday) == datetime(2026, 11, 30, 19, 30)


def test_next_session_crosses_midnight_hour_2():
    s = Schedule([4], [2, 23], 0, 59)
    thursday_late = datetime(2026, 11, 26, 23, 30)
    assert next_session(s, thursday_late) == datetime(2026, 12, 3, 2, 0)


def test_next_session_strictly_after_now():
    s = Schedule([4], [19], 0, 59)
    assert next_session(s, datetime(2026, 11, 26, 19, 0)) == datetime(2026, 12, 3, 19, 0)


def test_next_session_empty_is_none():
    assert next_session(Schedule([], [19], 0, 59), datetime(2026, 11, 26)) is None


def test_schedule_to_updates():
    u = schedule_to_updates(Schedule([1, 5], [20, 22], 15, 30))
    assert u == {"weekday": [1, 5], "hour": [20, 22], "minute": "15", "runtime": "30"}
