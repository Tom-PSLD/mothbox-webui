import json
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "webui" / "static"
WEBUI = STATIC.parent

ERROR_CODES = {
    "no_day", "no_hour", "bad_minute", "bad_runtime", "bad_hour", "bad_weekday",
    "bad_time", "bad_timezone", "bad_output", "hardware_error", "camera_error", "camera_busy",
    "bad_request", "bad_name", "bad_battery", "debug_still_on", "not_found", "network",
}


def i18n():
    return json.loads((STATIC / "i18n.json").read_text(encoding="utf-8"))


def test_i18n_same_keys_fr_en():
    data = i18n()
    assert set(data) == {"fr", "en"}
    assert set(data["fr"]) == set(data["en"])
    assert all(v.strip() for lang in data.values() for v in lang.values())


def test_every_error_code_translated():
    keys = set(i18n()["fr"])
    missing = {c for c in ERROR_CODES if f"error.{c}" not in keys}
    assert not missing


def test_error_codes_list_is_complete():
    produced = set()
    for py in WEBUI.glob("*.py"):
        text = py.read_text()
        produced |= set(re.findall(r'(?:ApiError|ValueError|RuntimeError|BlockingIOError)\("([a-z_]+)"', text))
        produced |= set(re.findall(r'error\("([a-z_]+)"', text))
        produced |= set(re.findall(r'errors\.append\("([a-z_]+)"\)', text))
    assert produced <= ERROR_CODES


def test_every_data_i18n_key_exists():
    keys = set(i18n()["fr"])
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    used = set(re.findall(r'data-i18n(?:-[a-z]+)?="([^"]+)"', html))
    used |= set(re.findall(r'\bt\("([^"]+)"', js))
    assert used
    assert not (used - keys)


def test_no_external_urls():
    for f in STATIC.iterdir():
        if f.suffix in {".html", ".js", ".css", ".json"}:
            urls = re.findall(r"https?://[^\s\"')]+", f.read_text(encoding="utf-8"))
            assert all(u.startswith("http://192.168.50.5") for u in urls), (f.name, urls)


def test_index_served(sim_paths):
    from webui.app import create_app
    from webui.runner import SimRunner

    app = create_app(sim_paths, SimRunner(), start_threads=False)
    r = app.test_client().get("/")
    assert r.status_code == 200
    assert b"app.js" in r.data
