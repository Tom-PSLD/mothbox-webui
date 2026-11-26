import threading

import pytest

from webui.outputs import Outputs
from webui.runner import SimRunner


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(sim_paths, sim=None):
    clock = FakeClock()
    sim = sim or SimRunner()
    return Outputs(sim_paths, sim, clock=clock), sim, clock


def script(sim_paths, rel):
    return ["python3", str(sim_paths.mothbox_root / rel)]


def test_set_on_runs_script(sim_paths):
    out, sim, _ = make(sim_paths)
    out.set("attract", True)
    assert sim.calls == [script(sim_paths, "scripts/Attract_On_noBootLock.py")]
    assert out.state() == {"attract": True, "flash": False, "12v": True}


def test_scripts_for_each_output(sim_paths):
    out, sim, _ = make(sim_paths)
    out.set("flash", True)
    out.set("flash", False)
    assert sim.calls == [
        script(sim_paths, "Flash_On.py"),
        script(sim_paths, "Flash_Off.py"),
        script(sim_paths, "scripts/12vOff.py"),
    ]


def test_fix4_flash_on_powers_12v_rail(sim_paths):
    out, _, _ = make(sim_paths)
    out.set("flash", True)
    assert out.state() == {"attract": False, "flash": True, "12v": True}


def test_fix4_flash_off_cuts_12v_when_unused(sim_paths):
    out, sim, _ = make(sim_paths)
    out.set("flash", True)
    out.set("flash", False)
    assert sim.calls[-1] == script(sim_paths, "scripts/12vOff.py")
    assert out.state()["12v"] is False


def test_fix4_attract_off_restores_12v_for_flash(sim_paths):
    out, sim, _ = make(sim_paths)
    out.set("attract", True)
    out.set("flash", True)
    out.set("attract", False)
    assert sim.calls[-2:] == [
        script(sim_paths, "scripts/Attract_Off_noBootLock.py"),
        script(sim_paths, "scripts/12vOn.py"),
    ]
    assert out.state() == {"attract": False, "flash": True, "12v": True}


def test_fix4_12v_off_turns_everything_off(sim_paths):
    out, _, _ = make(sim_paths)
    out.set("attract", True)
    out.set("flash", True)
    out.set("12v", False)
    assert out.state() == {"attract": False, "flash": False, "12v": False}


def test_fix4_heartbeat_timeout_always_cuts_12v(sim_paths):
    out, sim, clock = make(sim_paths)
    clock.t = 30
    out.tick()
    assert script(sim_paths, "scripts/12vOff.py") in sim.calls


def test_unknown_output(sim_paths):
    out, _, _ = make(sim_paths)
    with pytest.raises(ValueError, match="bad_output"):
        out.set("laser", True)


def test_script_failure_keeps_state(sim_paths):
    sim = SimRunner()
    sim.fail(script(sim_paths, "Flash_On.py"))
    out, _, _ = make(sim_paths, sim)
    with pytest.raises(RuntimeError, match="hardware_error"):
        out.set("flash", True)
    assert out.state()["flash"] is False


def test_auto_off_after_300s(sim_paths):
    out, sim, clock = make(sim_paths)
    out.set("attract", True)
    clock.t = 299
    out.heartbeat()
    assert out.tick() == []
    clock.t = 300
    out.heartbeat()
    assert out.tick() == ["attract"]
    assert sim.calls[-2:] == [
        script(sim_paths, "scripts/Attract_Off_noBootLock.py"),
        script(sim_paths, "scripts/12vOff.py"),
    ]
    assert out.state()["attract"] is False


def test_heartbeat_timeout_30s(sim_paths):
    out, _, clock = make(sim_paths)
    out.set("attract", True)
    out.set("12v", True)
    clock.t = 29
    assert out.tick() == []
    clock.t = 30
    assert sorted(out.tick()) == ["12v", "attract"]


def test_set_on_counts_as_heartbeat(sim_paths):
    out, _, clock = make(sim_paths)
    clock.t = 100
    out.set("flash", True)
    clock.t = 120
    assert out.tick() == []


def test_all_off(sim_paths):
    out, _, _ = make(sim_paths)
    out.set("flash", True)
    out.all_off()
    assert out.state() == {"attract": False, "flash": False, "12v": False}


def test_concurrent_set_serialized(sim_paths):
    sim = SimRunner()
    sim.delay = 0.1
    active = []
    peak = []
    original = sim.run

    def tracking(argv, timeout=20):
        active.append(1)
        peak.append(len(active))
        try:
            return original(argv, timeout)
        finally:
            active.pop()

    sim.run = tracking
    out, _, _ = make(sim_paths, sim)
    threads = [threading.Thread(target=out.set, args=(n, True)) for n in ("attract", "flash")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert max(peak) == 1


def test_fix4_12v_off_runs_rail_off_once(sim_paths):
    out, sim, _ = make(sim_paths)
    out.set("12v", True)
    out.set("12v", False)
    assert sim.calls.count(script(sim_paths, "scripts/12vOff.py")) == 1
