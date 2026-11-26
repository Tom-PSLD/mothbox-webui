import argparse
import shutil
from pathlib import Path

from .app import create_app
from .camera import SimCamera, TestCamera
from .config import Paths
from .runner import Runner, SimRunner

REFERENCE = Path(__file__).resolve().parent.parent / "reference_v5.2.1"
DEFAULT_SIM_ROOT = Path(__file__).resolve().parent.parent / "sim"


def build(sim: bool, sim_root, port):
    if sim:
        paths = Paths.under(sim_root or DEFAULT_SIM_ROOT)
        if not paths.settings_csv.exists():
            shutil.copytree(REFERENCE / "mothbox_custom", paths.custom_root, dirs_exist_ok=True)
            shutil.copytree(REFERENCE / "Mothbox", paths.mothbox_root, dirs_exist_ok=True)
        runner = SimRunner()
        runner.respond(["python3", str(paths.mothbox_root / "scripts/read_Vin.py")],
                       stdout="Vin Voltage: 12.10 V, Current: 0.12 A")
        return create_app(paths, runner, camera_factory=SimCamera), port or 8080
    return create_app(Paths.real(), Runner(), camera_factory=TestCamera), port or 80


def main():
    parser = argparse.ArgumentParser(prog="webui")
    parser.add_argument("--sim", action="store_true")
    parser.add_argument("--sim-root", type=Path)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    app, port = build(args.sim, args.sim_root, args.port)
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
