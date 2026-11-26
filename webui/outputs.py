import threading
import time

from .config import Paths

SCRIPTS = {
    "attract": ("scripts/Attract_On_noBootLock.py", "scripts/Attract_Off_noBootLock.py"),
    "flash": ("Flash_On.py", "Flash_Off.py"),
    "12v": ("scripts/12vOn.py", "scripts/12vOff.py"),
}
RAIL_ON, RAIL_OFF = SCRIPTS["12v"]
AUTO_OFF_S = 300
HEARTBEAT_TIMEOUT_S = 30


class Outputs:
    def __init__(self, paths: Paths, runner, clock=time.monotonic):
        self._paths = paths
        self._runner = runner
        self._clock = clock
        self._lock = threading.Lock()
        self._on_since: dict[str, float] = {}
        self._rail = False
        self._last_beat = clock()

    def _script(self, rel: str) -> bool:
        return self._runner.run(["python3", str(self._paths.mothbox_root / rel)]).ok

    def _reconcile_rail(self) -> None:
        if self._on_since:
            self._script(RAIL_ON)
            self._rail = True
        else:
            self._script(RAIL_OFF)
            self._rail = False

    def _off(self, name: str) -> None:
        for other in ("attract", "flash"):
            if other in self._on_since:
                self._script(SCRIPTS[other][1])
        self._on_since.clear()
        self._script(RAIL_OFF)
        self._rail = False

    def set(self, name: str, on: bool) -> None:
        if name not in SCRIPTS:
            raise ValueError("bad_output")
        with self._lock:
            now = self._clock()
            self._last_beat = now
            if on:
                if not self._script(SCRIPTS[name][0]):
                    raise RuntimeError("hardware_error")
                self._on_since[name] = now
                self._rail = True
            elif name == "12v":
                self._off("12v")
            else:
                if not self._script(SCRIPTS[name][1]):
                    raise RuntimeError("hardware_error")
                self._on_since.pop(name, None)
                self._reconcile_rail()

    def state(self) -> dict[str, bool]:
        with self._lock:
            return {
                "attract": "attract" in self._on_since,
                "flash": "flash" in self._on_since,
                "12v": self._rail,
            }

    def heartbeat(self) -> None:
        with self._lock:
            self._last_beat = self._clock()

    def tick(self) -> list[str]:
        with self._lock:
            now = self._clock()
            if now - self._last_beat >= HEARTBEAT_TIMEOUT_S:
                expired = list(self._on_since)
                for name in ("attract", "flash"):
                    if name in self._on_since:
                        self._script(SCRIPTS[name][1])
                self._on_since.clear()
                self._script(RAIL_OFF)
                self._rail = False
                self._last_beat = now
                return expired
            expired = [n for n, t in self._on_since.items() if now - t >= AUTO_OFF_S]
            for name in expired:
                self._script(SCRIPTS[name][1])
                self._on_since.pop(name, None)
            if expired:
                self._reconcile_rail()
            return expired

    def all_off(self) -> None:
        with self._lock:
            for name in ("attract", "flash"):
                self._script(SCRIPTS[name][1])
            self._script(RAIL_OFF)
            self._on_since.clear()
            self._rail = False
