"""Ghi và đọc log.csv: mọi việc giao, nhận, duyệt đều để lại một dòng."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

LOG_FIELDS = ["time", "unit", "stage", "worker", "action", "file", "result", "note"]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write(root: Path, unit: str = "", stage: str = "", worker: str = "", action: str = "",
          file: str = "", result: str = "", note: str = "") -> dict:
    path = Path(root) / "log.csv"
    new = not path.exists() or path.stat().st_size == 0
    row = dict(time=now(), unit=unit, stage=stage, worker=worker, action=action,
               file=str(file), result=result, note=note)
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow(row)
    return row


def read(root: Path, unit: str | None = None, last: int | None = None) -> list[dict]:
    path = Path(root) / "log.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if unit is None or r["unit"] == unit]
    return rows[-last:] if last else rows


def table(rows: list[dict]) -> str:
    out = ["| Lúc | Unit | Tầng | Worker | Việc | File | Kết quả | Ghi chú |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(k, "")).replace("|", "/") for k in LOG_FIELDS) + " |")
    return "\n".join(out)
