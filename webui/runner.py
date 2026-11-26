import subprocess
import threading
from dataclasses import dataclass


@dataclass
class RunResult:
    ok: bool
    stdout: str
    stderr: str


class Runner:
    def run(self, argv: list[str], timeout: float = 20) -> RunResult:
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return RunResult(False, "", "timeout")
        except OSError as e:
            return RunResult(False, "", str(e))
        return RunResult(p.returncode == 0, p.stdout, p.stderr)


class SimRunner:
    def __init__(self):
        self.calls: list[list[str]] = []
        self._rules: list[tuple[list[str], RunResult]] = []
        self.delay = 0.0
        self._lock = threading.Lock()

    def respond(self, prefix: list[str], stdout: str = "", ok: bool = True) -> None:
        self._rules.insert(0, (list(prefix), RunResult(ok, stdout, "" if ok else "sim failure")))

    def fail(self, prefix: list[str]) -> None:
        self.respond(prefix, ok=False)

    def run(self, argv: list[str], timeout: float = 20) -> RunResult:
        with self._lock:
            self.calls.append(list(argv))
        if self.delay:
            import time

            time.sleep(self.delay)
        for prefix, result in self._rules:
            if argv[: len(prefix)] == prefix:
                return result
        return RunResult(True, "", "")
