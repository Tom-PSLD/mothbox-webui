from webui.runner import Runner, RunResult, SimRunner


def test_runner_success():
    r = Runner().run(["echo", "hi"])
    assert r == RunResult(True, "hi\n", "")


def test_runner_failure_no_exception():
    r = Runner().run(["false"])
    assert r.ok is False


def test_runner_missing_binary():
    r = Runner().run(["/nonexistent/binary"])
    assert r.ok is False


def test_runner_timeout():
    r = Runner().run(["sleep", "5"], timeout=0.2)
    assert r.ok is False
    assert "timeout" in r.stderr


def test_sim_runner_records_and_responds():
    sim = SimRunner()
    sim.respond(["python3", "/x/read_Vin.py"], stdout="Vin Voltage: 12.1 V")
    sim.fail(["hwclock"])
    assert sim.run(["python3", "/x/read_Vin.py"]).stdout == "Vin Voltage: 12.1 V"
    assert sim.run(["hwclock", "-w"]).ok is False
    assert sim.run(["date"]).ok is True
    assert sim.calls == [["python3", "/x/read_Vin.py"], ["hwclock", "-w"], ["date"]]
