import csv
import os
import shutil

import pytest

from conftest import FIXTURES, extract_scheduler_functions
from webui.settings_csv import read_settings, split_multi, write_settings


def rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def test_read_reference_csv(sim_paths):
    s = read_settings(sim_paths.settings_csv, sim_paths.default_settings_csv)
    assert s["hour"] == "19;21;23;2;4"
    assert s["weekday"] == "1;2;3;4;5;6;7"
    assert s["runtime"] == "59"
    assert s["timezone"] == "America/Panama"


def test_read_legacy_comma_csv(sim_paths):
    shutil.copy(FIXTURES / "legacy_comma_settings.csv", sim_paths.settings_csv)
    s = read_settings(sim_paths.settings_csv, sim_paths.default_settings_csv)
    assert s["hour"] == "19"
    assert s["weekday"] == "1"


def test_read_missing_falls_back_to_defaults(sim_paths):
    os.remove(sim_paths.settings_csv)
    s = read_settings(sim_paths.settings_csv, sim_paths.default_settings_csv)
    assert s["manualTime"] == "1986-04-06 11:11:11"
    assert s["weekday"] == "1;2;3;4;5;6;7"


def test_split_multi():
    assert split_multi("19;21") == [19, 21]
    assert split_multi("19,21") == [19, 21]
    assert split_multi(" 7 ") == [7]
    assert split_multi("") == []


def test_write_roundtrip_scheduler_compatible(sim_paths):
    write_settings(
        sim_paths.settings_csv,
        sim_paths.default_settings_csv,
        {"hour": [20, 22], "weekday": [1, 5], "minute": "15", "runtime": "30"},
    )
    ns = extract_scheduler_functions("SETTING_DEFAULTS", "load_settings")
    loaded = ns["load_settings"](str(sim_paths.settings_csv))
    assert loaded["hour"] == "20;22"
    assert loaded["weekday"] == "1;5"
    assert loaded["minute"] == "15"
    assert loaded["runtime"] == 30


def test_write_preserves_details_and_unknown_rows(sim_paths):
    before = {r[0]: r for r in rows(sim_paths.settings_csv)}
    write_settings(sim_paths.settings_csv, sim_paths.default_settings_csv, {"hour": [20]})
    after = {r[0]: r for r in rows(sim_paths.settings_csv)}
    assert after["hour"][2] == before["hour"][2]
    assert after["photo_interval"] == before["photo_interval"]
    assert list(after) == list(before)


def test_write_normalizes_legacy_comma_row(sim_paths):
    shutil.copy(FIXTURES / "legacy_comma_settings.csv", sim_paths.settings_csv)
    write_settings(sim_paths.settings_csv, sim_paths.default_settings_csv, {"hour": [19, 21]})
    hour = [r for r in rows(sim_paths.settings_csv) if r[0] == "hour"][0]
    assert len(hour) == 3
    assert hour[1] == "19;21"


def test_write_adds_missing_key(sim_paths):
    write_settings(sim_paths.settings_csv, sim_paths.default_settings_csv, {"newkey": "x"})
    last = rows(sim_paths.settings_csv)[-1]
    assert last == ["newkey", "x", ""]


def test_write_missing_csv_creates_from_defaults(sim_paths):
    os.remove(sim_paths.settings_csv)
    write_settings(sim_paths.settings_csv, sim_paths.default_settings_csv, {"hour": [3]})
    s = read_settings(sim_paths.settings_csv, sim_paths.default_settings_csv)
    assert s["hour"] == "3"
    assert s["manualTime"] == "1986-04-06 11:11:11"


def test_write_is_atomic(sim_paths, monkeypatch):
    original = sim_paths.settings_csv.read_text()

    def boom(src, dst):
        raise OSError("disk")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_settings(sim_paths.settings_csv, sim_paths.default_settings_csv, {"hour": [1]})
    assert sim_paths.settings_csv.read_text() == original
    assert not list(sim_paths.custom_root.glob("*.tmp"))


def test_write_legacy_row_keeps_help_text(sim_paths):
    shutil.copy(FIXTURES / "legacy_comma_settings.csv", sim_paths.settings_csv)
    write_settings(sim_paths.settings_csv, sim_paths.default_settings_csv, {"hour": [1, 2]})
    hour = [r for r in rows(sim_paths.settings_csv) if r[0] == "hour"][0]
    assert "24 timeframe" in hour[2]
