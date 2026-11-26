import threading
import time

from .config import Paths

SCRIPTS = {
    "attract": ("scripts/Attract_On_noBootLock.py", "scripts/Attract_Off_noBootLock.py"),
    "flash": ("Flash_On.py", "Flash_Off.py"),
    "12v": ("scripts/12vOn.py", "scripts/12vOff.py"),
}
AUTO_OFF_S = 300
HEARTBEAT_TIMEOUT_S = 30


class Outputs:
    def __init__(self, paths: Paths, runner, clock=time.monotonic):
        self._paths = paths
        self._runner = runner
        self._clock = clock
        self._lock = threading.Lock()
        self._on_since: dict[str, float] = {}
        self._last_beat = clock()

    def _run(self, name: str, on: bool) -> bool:
        rel = SCRIPTS[name][0 if on else 1]
        return self._runner.run(["python3", str(self._paths.mothbox_root / rel)]).ok

    def set(self, name: str, on: bool) -> None:
        if name not in SCRIPTS:
            raise ValueError("bad_output")
        with self._lock:
            if not self._run(name, on):
                raise RuntimeError("hardware_error")
            now = self._clock()
            self._last_beat = now
            if on:
                self._on_since[name] = now
            else:
                self._on_since.pop(name, None)

    def state(self) -> dict[str, bool]:
        with self._lock:
            return {name: name in self._on_since for name in SCRIPTS}

    def heartbeat(self) -> None:
        with self._lock:
            self._last_beat = self._clock()

    def tick(self) -> list[str]:
        with self._lock:
            now = self._clock()
            if now - self._last_beat >= HEARTBEAT_TIMEOUT_S:
                expired = list(self._on_since)
            else:
                expired = [n for n, t in self._on_since.items() if now - t >= AUTO_OFF_S]
            for name in expired:
                self._run(name, False)
                self._on_since.pop(name, None)
            return expired

    def all_off(self) -> None:
        with self._lock:
            for name in SCRIPTS:
                self._run(name, False)
            self._on_since.clear()
