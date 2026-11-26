import threading

import pytest

from webui.camera import SimCamera, TestCamera


class FakeOutputs:
    def __init__(self):
        self.events = []

    def set(self, name, on):
        self.events.append((name, on))


def test_camera_returns_jpeg_with_flash():
    out = FakeOutputs()
    cam = TestCamera(out, capture_fn=lambda: b"\xff\xd8jpeg")
    assert cam.capture() == b"\xff\xd8jpeg"
    assert out.events == [("flash", True), ("flash", False)]


def test_camera_flash_off_even_on_error():
    out = FakeOutputs()

    def broken():
        raise OSError("no camera")

    cam = TestCamera(out, capture_fn=broken)
    with pytest.raises(RuntimeError, match="camera_error"):
        cam.capture()
    assert out.events[-1] == ("flash", False)


def test_camera_busy_raises():
    started = threading.Event()
    release = threading.Event()

    def slow():
        started.set()
        release.wait(2)
        return b"x"

    cam = TestCamera(FakeOutputs(), capture_fn=slow)
    t = threading.Thread(target=cam.capture)
    t.start()
    started.wait(2)
    with pytest.raises(BlockingIOError):
        cam.capture()
    release.set()
    t.join()


def test_sim_camera_returns_sample():
    assert SimCamera(FakeOutputs()).capture()[:2] == b"\xff\xd8"


from webui.camera import camera_controls


def write_cam(sim_paths, autocal, lens="6.5", vflip="0"):
    p = sim_paths.custom_root / "camera_settings.csv"
    text = p.read_text()
    import re
    text = re.sub(r"^AutoCalibration,[^,]*,", f"AutoCalibration,{autocal},", text, flags=re.M)
    text = re.sub(r"^LensPosition,[^,]*,", f"LensPosition,{lens},", text, flags=re.M)
    text = re.sub(r"^VerticalFlip,[^,]*,", f"VerticalFlip,{vflip},", text, flags=re.M)
    p.write_text(text)


def test_fix5_controls_use_calibrated_lens_when_autocalibration(sim_paths):
    write_cam(sim_paths, 1)
    controls, vflip = camera_controls(sim_paths)
    assert controls["AfMode"] == 0
    assert controls["LensPosition"] == 4.06994104385376
    assert vflip is False


def test_fix5_controls_use_csv_lens_when_manual(sim_paths):
    write_cam(sim_paths, 0, lens="7.25", vflip="1")
    controls, vflip = camera_controls(sim_paths)
    assert controls["LensPosition"] == 7.25
    assert vflip is True


def test_fix5_controls_defaults_when_files_missing(sim_paths):
    (sim_paths.custom_root / "camera_settings.csv").unlink()
    (sim_paths.controls_root / "aflensposition.txt").unlink()
    controls, vflip = camera_controls(sim_paths)
    assert controls == {"AfMode": 0, "LensPosition": 6.0}
    assert vflip is False
