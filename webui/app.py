import re
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .camera import TestCamera
from .clock import MAX_EPOCH, MIN_EPOCH, is_valid_timezone, list_timezones, set_clock, set_timezone
from .config import Paths
from .controls import read_kv
from .outputs import Outputs
from .schedule import (
    Schedule,
    next_session,
    schedule_from_settings,
    schedule_from_switches,
    schedule_to_updates,
    validate,
)
from .sensors import read_sensors
from .settings_csv import read_settings, write_settings
from .switches import refresh_switches, schedule_source

PORTAL_URL = "http://192.168.50.5/"
STATIC = Path(__file__).with_name("static")
NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,24}$")
BATTERY_KEYS = ("bat_voltage", "bat_Wh", "bat_80perVolts", "bat_20perVolts")


class ApiError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _float(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("bad_request")
    return data


def _int_list(value) -> list[int]:
    if not isinstance(value, list) or not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
        raise ApiError("bad_request")
    return value


def _int(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ApiError("bad_request")
    return value


def create_app(paths: Paths, runner, camera_factory=TestCamera, start_threads: bool = True,
               reboot_delay: float = 2.0) -> Flask:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    outputs = Outputs(paths, runner)
    camera = camera_factory(outputs, paths)

    def settings() -> dict:
        return read_settings(paths.settings_csv, paths.default_settings_csv)

    def current_name(s: dict) -> str:
        if s.get("autoname", "").lower() != "true" and s.get("name", "").strip():
            return s["name"].strip()
        return read_kv(paths.controls_root / "name.txt").get("name", s.get("name", ""))

    def error(code: str, status: int):
        return jsonify({"ok": False, "error": code}), status

    @app.errorhandler(ApiError)
    def api_error(e):
        return error(e.code, e.status)

    @app.errorhandler(ValueError)
    def value_error(e):
        return error(str(e), 400)

    @app.errorhandler(BlockingIOError)
    def busy_error(e):
        return error("camera_busy", 409)

    @app.errorhandler(RuntimeError)
    def hardware_error(e):
        return error(str(e) or "hardware_error", 502)

    @app.errorhandler(HTTPException)
    def http_error(e):
        if request.path.startswith("/api/"):
            return error("not_found" if e.code == 404 else "bad_request", e.code)
        if e.code == 404:
            return redirect(PORTAL_URL, 302)
        return e

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/api/state")
    def state():
        s = settings()
        switches = refresh_switches(paths, runner)
        csv_schedule = schedule_from_settings(s)
        sw_schedule = schedule_from_switches(switches)
        source = schedule_source(switches)
        active = sw_schedule if source == "switches" else csv_schedule
        nxt = next_session(active, datetime.now())
        return jsonify({
            "mode": read_kv(paths.controls_root / "mode.txt").get("mode", ""),
            "switches": {k: switches.get(k, "0") for k in ("Active", "Debug", "U1")},
            "source": source,
            "schedule": csv_schedule.to_dict(),
            "switch_schedule": sw_schedule.to_dict(),
            "next_session": nxt.isoformat(timespec="minutes") if nxt else None,
            "timezone": s.get("timezone", ""),
            "box_time": datetime.now().isoformat(timespec="seconds"),
            "name": current_name(s),
            "autoname": s.get("autoname", "").lower() == "true",
            "battery": {k: _float(s.get(k)) for k in BATTERY_KEYS},
            "outputs": outputs.state(),
        })

    @app.get("/api/timezones")
    def timezones():
        return jsonify(list_timezones(paths))

    @app.post("/api/clock")
    def clock():
        body = _body()
        tz = body.get("timezone")
        if not isinstance(tz, str):
            raise ApiError("bad_timezone")
        epoch_ms = _int(body.get("epoch_ms"))
        if not is_valid_timezone(paths, tz):
            raise ApiError("bad_timezone")
        if not MIN_EPOCH <= epoch_ms // 1000 < MAX_EPOCH:
            raise ApiError("bad_time")
        set_timezone(paths, runner, tz)
        offset = set_clock(runner, epoch_ms)
        return jsonify({"ok": True, "offset_s": offset})

    @app.post("/api/schedule")
    def schedule():
        body = _body()
        s = Schedule(
            weekdays=sorted(set(_int_list(body.get("weekdays")))),
            hours=sorted(set(_int_list(body.get("hours")))),
            minute=_int(body.get("minute")),
            runtime=_int(body.get("runtime")),
        )
        errors = validate(s)
        if errors:
            raise ApiError(errors[0])
        write_settings(paths.settings_csv, paths.default_settings_csv, schedule_to_updates(s))
        return jsonify({"ok": True})

    @app.post("/api/advanced")
    def advanced():
        body = _body()
        autoname = body.get("autoname")
        if not isinstance(autoname, bool):
            raise ApiError("bad_request")
        updates = {"autoname": "True" if autoname else "False"}
        if not autoname:
            name = body.get("name")
            if not isinstance(name, str) or not NAME_RE.match(name):
                raise ApiError("bad_name")
            updates["name"] = name
        values = {k: _float(body.get(k)) for k in BATTERY_KEYS}
        if any(v is None or v <= 0 for v in values.values()):
            raise ApiError("bad_battery")
        if values["bat_20perVolts"] >= values["bat_80perVolts"]:
            raise ApiError("bad_battery")
        updates.update({k: f"{v:g}" for k, v in values.items()})
        write_settings(paths.settings_csv, paths.default_settings_csv, updates)
        return jsonify({"ok": True})

    @app.post("/api/output/<name>")
    def output(name):
        on = _body().get("on")
        if not isinstance(on, bool):
            raise ApiError("bad_request")
        outputs.set(name, on)
        return jsonify({"ok": True, "outputs": outputs.state()})

    @app.post("/api/heartbeat")
    def heartbeat():
        outputs.heartbeat()
        return jsonify({"ok": True})

    @app.get("/api/sensors")
    def sensors():
        return jsonify(read_sensors(paths, runner, settings()))

    @app.post("/api/photo")
    def photo():
        data = camera.capture()
        return app.response_class(data, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/api/reboot")
    def reboot():
        switches = refresh_switches(paths, runner)
        if switches.get("Debug", "1") != "0":
            raise ApiError("debug_still_on", 409)
        if switches.get("Active", "1") != "1":
            raise ApiError("active_off", 409)
        outputs.all_off()

        def later():
            time.sleep(reboot_delay)
            runner.run(["systemctl", "reboot"])

        threading.Thread(target=later, daemon=True).start()
        return jsonify({"ok": True})

    for url in ("/generate_204", "/gen_204", "/hotspot-detect.html", "/library/test/success.html",
                "/ncsi.txt", "/connecttest.txt"):
        app.add_url_rule(url, url, lambda: redirect(PORTAL_URL, 302))

    if start_threads:
        def ticker():
            while True:
                time.sleep(2)
                outputs.tick()

        threading.Thread(target=ticker, daemon=True).start()

    return app
