import pytest

from webui.clock import is_valid_timezone, list_timezones, set_clock, set_timezone
from webui.controls import read_kv
from webui.runner import SimRunner
from webui.settings_csv import read_settings


def test_list_timezones_groups(sim_paths):
    tz = list_timezones(sim_paths)
    assert "Zurich" in tz["Europe"]
    assert "Paris" in tz["Europe"]
    assert "Argentina/Buenos_Aires" in tz["America"]
    assert tz["Europe"] == sorted(tz["Europe"])


def test_list_timezones_names_without_slash_in_other(sim_paths):
    sim_paths.timezone_list.write_text("Europe/Paris\nUTC\n")
    assert list_timezones(sim_paths) == {"Europe": ["Paris"], "Other": ["UTC"]}


def test_is_valid_timezone(sim_paths):
    assert is_valid_timezone(sim_paths, "Europe/Zurich")
    assert not is_valid_timezone(sim_paths, "Etc/Unknown")
    assert not is_valid_timezone(sim_paths, "")


def test_set_clock_commands(monkeypatch):
    sim = SimRunner()
    monkeypatch.setattr("webui.clock.time.time", lambda: 1795000000 - 120)
    offset = set_clock(sim, 1795000000_000)
    assert sim.calls == [["date", "-u", "-s", "@1795000000"], ["hwclock", "-w"]]
    assert offset == 120


def test_set_clock_rejects_old_epoch():
    sim = SimRunner()
    with pytest.raises(ValueError, match="bad_time"):
        set_clock(sim, 1577836800_000)
    assert sim.calls == []


def test_set_clock_rejects_far_future():
    with pytest.raises(ValueError, match="bad_time"):
        set_clock(SimRunner(), 4200000000_000)


def test_set_clock_date_failure_raises():
    sim = SimRunner()
    sim.fail(["date"])
    with pytest.raises(RuntimeError, match="hardware_error"):
        set_clock(sim, 1795000000_000)


def test_set_timezone_writes_csv_and_control(sim_paths):
    sim = SimRunner()
    set_timezone(sim_paths, sim, "Europe/Zurich")
    s = read_settings(sim_paths.settings_csv, sim_paths.default_settings_csv)
    assert s["timezone"] == "Europe/Zurich"
    assert s["autoSystemTime"] == "True"
    assert read_kv(sim_paths.controls_root / "timezone.txt") == {"timezone": "Europe/Zurich"}
    assert sim.calls == [["python3", str(sim_paths.mothbox_root / "TimezoneUpdater.py")]]


def test_set_timezone_rejects_unknown(sim_paths):
    before = sim_paths.settings_csv.read_text()
    before_ctl = (sim_paths.controls_root / "timezone.txt").read_text()
    with pytest.raises(ValueError, match="bad_timezone"):
        set_timezone(sim_paths, SimRunner(), "Etc/Unknown")
    assert sim_paths.settings_csv.read_text() == before
    assert (sim_paths.controls_root / "timezone.txt").read_text() == before_ctl


def test_fix2_set_timezone_reloads_process_zone(sim_paths, monkeypatch):
    called = []
    monkeypatch.setattr("webui.clock.time.tzset", lambda: called.append(1))
    set_timezone(sim_paths, SimRunner(), "Europe/Zurich")
    assert called == [1]
