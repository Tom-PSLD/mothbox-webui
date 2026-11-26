from webui.runner import SimRunner
from webui.sensors import battery_percent, read_sensors

SETTINGS = {"bat_20perVolts": "10.5", "bat_80perVolts": "12.0"}


def vin_runner(sim_paths, stdout="Vin Voltage: 12.100 V, Current: 0.120 A"):
    sim = SimRunner()
    sim.respond(["python3", str(sim_paths.mothbox_root / "scripts/read_Vin.py")], stdout=stdout)
    return sim


def test_voltage_and_percent(sim_paths, tmp_path):
    thermal = tmp_path / "temp"
    thermal.write_text("48312\n")
    r = read_sensors(sim_paths, vin_runner(sim_paths), SETTINGS, thermal_path=thermal)
    assert r["voltage"] == 12.1
    assert r["percent"] == 84
    assert r["cpu_temp"] == 48.3
    assert r["disk_free_gb"] > 0


def test_sensors_power_on_before_reading(sim_paths):
    sim = vin_runner(sim_paths)
    read_sensors(sim_paths, sim, SETTINGS)
    assert sim.calls[0] == ["python3", str(sim_paths.mothbox_root / "scripts/3v3SensorsOn.py")]
    assert sim.calls[1] == ["python3", str(sim_paths.mothbox_root / "scripts/read_Vin.py")]


def test_percent_bounds_and_none():
    assert battery_percent(13.0, 10.5, 12.0) == 100
    assert battery_percent(9.0, 10.5, 12.0) == 0
    assert battery_percent(12.0, 12.0, 12.0) is None
    assert battery_percent(None, 10.5, 12.0) is None


def test_percent_bad_settings(sim_paths):
    r = read_sensors(sim_paths, vin_runner(sim_paths), {"bat_20perVolts": "x"})
    assert r["voltage"] == 12.1
    assert r["percent"] is None


def test_vin_script_failure_gives_none(sim_paths, tmp_path):
    sim = SimRunner()
    sim.fail(["python3", str(sim_paths.mothbox_root / "scripts/read_Vin.py")])
    r = read_sensors(sim_paths, sim, SETTINGS, thermal_path=tmp_path / "missing")
    assert r["voltage"] is None
    assert r["percent"] is None
    assert r["cpu_temp"] is None


def test_gps_values(sim_paths):
    (sim_paths.controls_root / "lat.txt").write_text("lat=46.52\n")
    (sim_paths.controls_root / "lon.txt").write_text("lon=6.63\n")
    r = read_sensors(sim_paths, vin_runner(sim_paths), SETTINGS)
    assert (r["lat"], r["lon"]) == ("46.52", "6.63")


def test_gps_error_values_are_none(sim_paths):
    (sim_paths.controls_root / "lat.txt").write_text("lat=errolat\n")
    r = read_sensors(sim_paths, vin_runner(sim_paths), SETTINGS)
    assert r["lat"] is None
    assert r["lon"] is None
