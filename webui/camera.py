import io
import threading
from pathlib import Path

SAMPLE = Path(__file__).with_name("sim_sample.jpg")


def _picamera_capture() -> bytes:
    from picamera2 import Picamera2

    cam = Picamera2()
    try:
        cam.configure(cam.create_still_configuration(main={"size": (1280, 960)}))
        cam.start()
        buf = io.BytesIO()
        cam.capture_file(buf, format="jpeg")
        return buf.getvalue()
    finally:
        cam.close()


class TestCamera:
    __test__ = False

    def __init__(self, outputs, capture_fn=_picamera_capture):
        self._outputs = outputs
        self._capture_fn = capture_fn
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
    def __init__(self, outputs):
        super().__init__(outputs, capture_fn=SAMPLE.read_bytes)
