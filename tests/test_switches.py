from webui.runner import SimRunner
from webui.switches import refresh_switches, schedule_source


def test_schedule_source():
    assert schedule_source({"U1": "1"}) == "switches"
    assert schedule_source({"U1": "0"}) == "csv"
    assert schedule_source({}) == "csv"


def test_refresh_switches_reads_file(sim_paths):
    (sim_paths.controls_root / "switches.txt").write_text("Active=1\nDebug=0\nU1=1\n")
    sim = SimRunner()
    vals = refresh_switches(sim_paths, sim)
    assert vals == {"Active": "1", "Debug": "0", "U1": "1"}
    assert sim.calls == [["python3", str(sim_paths.mothbox_root / "GetConfigSwitches.py")]]


def test_refresh_switches_script_fails(sim_paths):
    (sim_paths.controls_root / "switches.txt").write_text("Debug=1\n")
    sim = SimRunner()
    sim.fail(["python3"])
    assert refresh_switches(sim_paths, sim) == {"Debug": "1"}


def test_refresh_switches_missing_file(sim_paths):
    (sim_paths.controls_root / "switches.txt").unlink()
    assert refresh_switches(sim_paths, SimRunner()) == {}
