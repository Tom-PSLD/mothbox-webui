import csv
import io
import os
from pathlib import Path

HEADER = ["SETTING", "VALUE", "DETAILS"]


def _source(path: Path, default_path: Path) -> Path:
    try:
        if Path(path).is_file() and Path(path).stat().st_size > 0:
            return Path(path)
    except OSError:
        pass
    return Path(default_path)


def _read_rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.reader(f) if r]


def read_settings(path: Path, default_path: Path) -> dict[str, str]:
    try:
        rows = _read_rows(_source(path, default_path))
    except (OSError, UnicodeDecodeError, csv.Error):
        rows = _read_rows(Path(default_path))
    result = {}
    for row in rows[1:]:
        key = row[0].strip()
        if key:
            result[key] = row[1].strip() if len(row) > 1 else ""
    return result


def split_multi(value: str) -> list[int]:
    parts = str(value).replace(",", ";").split(";")
    return [int(p.strip()) for p in parts if p.strip()]


def _format(value) -> str:
    if isinstance(value, (list, tuple)):
        return ";".join(str(v) for v in value)
    return str(value)


def write_settings(path: Path, default_path: Path, updates: dict) -> None:
    path = Path(path)
    try:
        rows = _read_rows(_source(path, default_path))
    except (OSError, UnicodeDecodeError, csv.Error):
        rows = _read_rows(Path(default_path))
    body = []
    seen = set()
    for row in rows[1:]:
        key = row[0].strip()
        value = row[1] if len(row) > 1 else ""
        details = row[2] if len(row) > 2 else ""
        if key in updates:
            value = _format(updates[key])
            if len(row) > 3:
                details = next(
                    (c for c in reversed(row[2:]) if c.strip() and not c.strip().isdigit()),
                    "",
                )
            seen.add(key)
        body.append([row[0], value, details])
    for key, value in updates.items():
        if key not in seen:
            body.append([key, _format(value), ""])
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(body)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
