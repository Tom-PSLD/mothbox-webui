import io
import threading
import time
from pathlib import Path

from .config import Paths
from .controls import read_kv
from .settings_csv import read_settings

SAMPLE = Path(__file__).with_name("sim_sample.jpg")
DEFAULT_LENS = 6.0
SETTLE_S = 1.0


def _num(value, default):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def camera_controls(paths: Paths) -> tuple[dict, bool]:
    csv_path = paths.custom_root / "camera_settings.csv"
    cam = read_settings(csv_path, csv_path) if csv_path.is_file() else {}
    autocal = int(_num(cam.get("AutoCalibration"), 1)) != 0
    if autocal:
        lens = _num(read_kv(paths.controls_root / "aflensposition.txt").get("aflensposition"), DEFAULT_LENS)
    else:
        lens = _num(cam.get("LensPosition"), DEFAULT_LENS)
    vflip = int(_num(cam.get("VerticalFlip"), 0)) == 1
    return {"AfMode": 0, "LensPosition": lens}, vflip


def picamera_capture(paths: Paths) -> bytes:
    from libcamera import Transform
    from picamera2 import Picamera2

    controls, vflip = camera_controls(paths)
    cam = Picamera2()
    try:
        transform = Transform(vflip=True, hflip=True) if vflip else Transform()
        cam.configure(cam.create_still_configuration(main={"size": (1280, 960)}, transform=transform))
        cam.set_controls(controls)
        cam.start()
        time.sleep(SETTLE_S)
        buf = io.BytesIO()
        cam.capture_file(buf, format="jpeg")
        return buf.getvalue()
    finally:
        cam.close()


class TestCamera:
    __test__ = False

    def __init__(self, outputs, paths: Paths = None, capture_fn=None):
        self._outputs = outputs
        self._capture_fn = capture_fn or (lambda: picamera_capture(paths))
        self._lock = threading.Lock()

    def capture(self) -> bytes:
        if not self._lock.acquire(blocking=False):
            raise BlockingIOError("camera_busy")
        try:
            self._outputs.set("flash", True)
            try:
                return self._capture_fn()
            except Exception as e:
                raise RuntimeError("camera_error") from e
            finally:
                try:
                    self._outputs.set("flash", False)
                except Exception:
                    pass
        finally:
            self._lock.release()


class SimCamera(TestCamera):
    def __init__(self, outputs, paths: Paths = None):
        super().__init__(outputs, capture_fn=SAMPLE.read_bytes)
