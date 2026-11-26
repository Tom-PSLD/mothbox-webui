import os
from pathlib import Path


def read_kv(path: Path) -> dict[str, str]:
    values = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    except (OSError, UnicodeDecodeError):
        return {}
    return values


def write_kv(path: Path, key: str, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
