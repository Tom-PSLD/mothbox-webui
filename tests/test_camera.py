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
