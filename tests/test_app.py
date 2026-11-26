import os
import time

import pytest

from webui.app import create_app
from webui.camera import SimCamera
from webui.runner import SimRunner
from webui.settings_csv import read_settings


class BusyCamera:
    def __init__(self, outputs, paths=None):
        pass

    def capture(self):
        raise BlockingIOError("camera_busy")


@pytest.fixture
def ctx(sim_paths):
    sim = SimRunner()
    sim.respond(["python3", str(sim_paths.mothbox_root / "scripts/read_Vin.py")], stdout="Vin Voltage: 12.0 V")
    (sim_paths.controls_root / "switches.txt").write_text("Active=1\nDebug=1\nU1=0\nh19=1\nd1=1\n")
    app = create_app(sim_paths, sim, camera_factory=SimCamera, start_threads=False, reboot_delay=0)
    return app.test_client(), sim, sim_paths


def test_state_reference(ctx):
    client, _, _ = ctx
    r = client.get("/api/state")
    assert r.status_code == 200
    j = r.get_json()
    assert j["mode"] == "DEBUG"
    assert j["switches"] == {"Active": "1", "Debug": "1", "U1": "0"}
    assert j["source"] == "csv"
    assert j["schedule"] == {"weekdays": [1, 2, 3, 4, 5, 6, 7], "hours": [19, 21, 23, 2, 4], "minute": 0, "runtime": 59}
    assert j["switch_schedule"]["hours"] == [19]
    assert j["timezone"] == "America/Panama"
    assert j["name"] == "adultoAngu"
    assert j["autoname"] is True
    assert j["battery"]["bat_20perVolts"] == 10.5
    assert j["outputs"] == {"attract": False, "flash": False, "12v": False}
    assert j["next_session"] is not None


def test_state_source_switches(ctx):
    client, _, paths = ctx
    (paths.controls_root / "switches.txt").write_text("Debug=1\nU1=1\nh20=1\n")
    j = client.get("/api/state").get_json()
    assert j["source"] == "switches"
    assert j["switch_schedule"]["hours"] == [20]


def test_state_with_missing_csv(ctx):
    client, _, paths = ctx
    os.remove(paths.settings_csv)
    r = client.get("/api/state")
    assert r.status_code == 200
    assert r.get_json()["schedule"]["runtime"] == 59


def test_post_schedule_valid_then_state(ctx):
    client, _, paths = ctx
    r = client.post("/api/schedule", json={"weekdays": [1, 3], "hours": [22], "minute": 15, "runtime": 30})
    assert r.get_json() == {"ok": True}
    s = read_settings(paths.settings_csv, paths.default_settings_csv)
    assert (s["weekday"], s["hour"], s["minute"], s["runtime"]) == ("1;3", "22", "15", "30")
    assert client.get("/api/state").get_json()["schedule"]["hours"] == [22]


def test_post_schedule_invalid_400(ctx):
    client, _, _ = ctx
    r = client.post("/api/schedule", json={"weekdays": [], "hours": [22], "minute": 0, "runtime": 30})
    assert r.status_code == 400
    assert r.get_json() == {"ok": False, "error": "no_day"}


def test_post_schedule_malformed_400(ctx):
    client, _, _ = ctx
    r = client.post("/api/schedule", json={"weekdays": "lundi"})
    assert r.status_code == 400
    assert r.get_json()["error"] == "bad_request"


def test_post_clock(ctx):
    client, sim, _ = ctx
    r = client.post("/api/clock", json={"epoch_ms": int(time.time() * 1000), "timezone": "Europe/Zurich"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert ["hwclock", "-w"] in sim.calls


def test_post_clock_bad_timezone_400(ctx):
    client, sim, _ = ctx
    r = client.post("/api/clock", json={"epoch_ms": int(time.time() * 1000), "timezone": "Etc/Unknown"})
    assert r.status_code == 400
    assert r.get_json()["error"] == "bad_timezone"
    assert not any(c[0] == "date" for c in sim.calls)


def test_post_clock_bad_time_400(ctx):
    client, _, _ = ctx
    r = client.post("/api/clock", json={"epoch_ms": 0, "timezone": "Europe/Zurich"})
    assert r.get_json()["error"] == "bad_time"


def test_advanced_ok(ctx):
    client, _, paths = ctx
    body = {"autoname": False, "name": "Fauna-01", "bat_voltage": 12, "bat_Wh": 100,
            "bat_80perVolts": 12.5, "bat_20perVolts": 11}
    assert client.post("/api/advanced", json=body).get_json() == {"ok": True}
    s = read_settings(paths.settings_csv, paths.default_settings_csv)
    assert (s["autoname"], s["name"], s["bat_Wh"]) == ("False", "Fauna-01", "100")


def test_advanced_bad_name_400(ctx):
    client, _, _ = ctx
    body = {"autoname": False, "name": "Ma box!", "bat_voltage": 12, "bat_Wh": 100,
            "bat_80perVolts": 12.5, "bat_20perVolts": 11}
    r = client.post("/api/advanced", json=body)
    assert r.status_code == 400
    assert r.get_json()["error"] == "bad_name"


def test_advanced_bad_battery_400(ctx):
    client, _, _ = ctx
    body = {"autoname": True, "name": "x", "bat_voltage": 12, "bat_Wh": 100,
            "bat_80perVolts": 11, "bat_20perVolts": 12}
    assert client.post("/api/advanced", json=body).get_json()["error"] == "bad_battery"


def test_output_on(ctx):
    client, _, _ = ctx
    r = client.post("/api/output/attract", json={"on": True})
    assert r.get_json() == {"ok": True, "outputs": {"attract": True, "flash": False, "12v": True}}


def test_output_unknown_400(ctx):
    client, _, _ = ctx
    assert client.post("/api/output/laser", json={"on": True}).status_code == 400


def test_output_hardware_error_502(ctx):
    client, sim, paths = ctx
    sim.fail(["python3", str(paths.mothbox_root / "Flash_On.py")])
    r = client.post("/api/output/flash", json={"on": True})
    assert r.status_code == 502
    assert r.get_json() == {"ok": False, "error": "hardware_error"}


def test_heartbeat(ctx):
    client, _, _ = ctx
    assert client.post("/api/heartbeat").get_json() == {"ok": True}


def test_sensors(ctx):
    client, _, _ = ctx
    j = client.get("/api/sensors").get_json()
    assert j["voltage"] == 12.0
    assert j["percent"] == 80


def test_timezones(ctx):
    client, _, _ = ctx
    assert "Zurich" in client.get("/api/timezones").get_json()["Europe"]


def test_photo(ctx):
    client, _, _ = ctx
    r = client.post("/api/photo")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"
    assert r.data[:2] == b"\xff\xd8"


def test_photo_busy_409(sim_paths):
    app = create_app(sim_paths, SimRunner(), camera_factory=BusyCamera, start_threads=False)
    r = app.test_client().post("/api/photo")
    assert r.status_code == 409
    assert r.get_json()["error"] == "camera_busy"


def test_reboot_refused_when_debug_on(ctx):
    client, sim, _ = ctx
    r = client.post("/api/reboot")
    assert r.status_code == 409
    assert r.get_json()["error"] == "debug_still_on"
    assert ["systemctl", "reboot"] not in sim.calls


def test_reboot_calls_systemctl_when_debug_off(ctx):
    client, sim, paths = ctx
    (paths.controls_root / "switches.txt").write_text("Active=1\nDebug=0\n")
    client.post("/api/output/attract", json={"on": True})
    r = client.post("/api/reboot")
    assert r.get_json() == {"ok": True}
    for _ in range(50):
        if ["systemctl", "reboot"] in sim.calls:
            break
        time.sleep(0.02)
    assert sim.calls[-1] == ["systemctl", "reboot"]
    off = ["python3", str(paths.mothbox_root / "scripts/Attract_Off_noBootLock.py")]
    assert sim.calls.index(off) < sim.calls.index(["systemctl", "reboot"])


@pytest.mark.parametrize("url", ["/generate_204", "/gen_204", "/hotspot-detect.html",
                                 "/library/test/success.html", "/ncsi.txt", "/connecttest.txt",
                                 "/some/random/page"])
def test_captive_redirects(ctx, url):
    client, _, _ = ctx
    r = client.get(url)
    assert r.status_code == 302
    assert r.headers["Location"] == "http://192.168.50.5/"


def test_api_unknown_route_404_json(ctx):
    client, _, _ = ctx
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.get_json() == {"ok": False, "error": "not_found"}


def test_fix1_manual_name_shown_after_save(ctx):
    client, _, _ = ctx
    body = {"autoname": False, "name": "SiteA", "bat_voltage": 12, "bat_Wh": 100,
            "bat_80perVolts": 12.5, "bat_20perVolts": 11}
    client.post("/api/advanced", json=body)
    assert client.get("/api/state").get_json()["name"] == "SiteA"


def test_fix6_state_ready_flags(ctx):
    client, _, paths = ctx
    (paths.controls_root / "switches.txt").write_text("Active=0\nDebug=0\n")
    j = client.get("/api/state").get_json()
    assert j["switches"]["Active"] == "0"


def test_fix6_reboot_refused_when_active_off(ctx):
    client, sim, paths = ctx
    (paths.controls_root / "switches.txt").write_text("Active=0\nDebug=0\n")
    r = client.post("/api/reboot")
    assert r.status_code == 409
    assert r.get_json()["error"] == "active_off"
    assert ["systemctl", "reboot"] not in sim.calls
