from webui.__main__ import build
from webui.camera import SimCamera
from webui.runner import Runner, SimRunner


def test_build_sim_creates_tree(tmp_path):
    app, port = build(sim=True, sim_root=tmp_path / "sim", port=None)
    assert port == 8080
    assert (tmp_path / "sim/boot/firmware/mothbox_custom/mothbox_settings.csv").is_file()
    assert (tmp_path / "sim/boot/firmware/mothbox_custom/system/controls/switches.txt").is_file()
    assert app.test_client().get("/api/state").status_code == 200


def test_build_sim_keeps_existing_tree(tmp_path):
    build(sim=True, sim_root=tmp_path / "sim", port=None)
    csv = tmp_path / "sim/boot/firmware/mothbox_custom/mothbox_settings.csv"
    csv.write_text(csv.read_text().replace("America/Panama", "Europe/Paris"))
    build(sim=True, sim_root=tmp_path / "sim", port=None)
    assert "Europe/Paris" in csv.read_text()


def test_build_real_port_80(monkeypatch):
    monkeypatch.setattr("webui.__main__.create_app", lambda paths, runner, **kw: (paths, runner, kw))
    (paths, runner, kw), port = build(sim=False, sim_root=None, port=None)
    assert port == 80
    assert str(paths.custom_root) == "/boot/firmware/mothbox_custom"
    assert isinstance(runner, Runner)
