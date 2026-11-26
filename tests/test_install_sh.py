import subprocess
from pathlib import Path


def test_install_script():
    script = Path(__file__).with_name("test_install.sh")
    r = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().endswith("OK")
