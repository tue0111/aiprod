"""Nhận file mới (Downloads, queue/outbox, thư mục khác), đặt tên chuẩn, gắn vào đơn vị.

Tên chuẩn trong dự án: assets/<id>/<id>_<stage>_<tag>_t<n>.<ext>
- Không bao giờ ghi đè: trùng tên thì tăng n (_t2, _t3, ...).
- Bỏ qua file đang tải dở (.crdownload, .part, .tmp) và file rỗng.
- Đơn vị đang `spec_ready`/`generating` chuyển sang `candidates`.

Nhận diện file theo thứ tự:
1. Mẫu riêng trong PROJECT.md:
     ingest:
       patterns:
         - {regex: '^G-(?P<id>[A-Z]+\\d+)_(?P<tag>.+)\\.mp4$', stage: video}
2. Mẫu chuẩn: <ID>_<stage>[_<tag>][_t<n>].<ext>
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from . import log
from .project import Project

PARTIAL = {".crdownload", ".part", ".tmp", ".download"}
TAG_SAFE = re.compile(r"[^A-Za-z0-9-]+")
TRY = re.compile(r"_t(\d+)$")


def default_sources(p: Project) -> list[Path]:
    cfg = (p.meta.get("ingest") or {}).get("sources")
    if cfg:
        return [Path(os.path.expandvars(os.path.expanduser(s))) if Path(s).is_absolute() or s.startswith(("~", "$", "%"))
                else p.root / s for s in cfg]
    return [p.root / "queue" / "outbox", Path.home() / "Downloads"]


def normalize_id(p: Project, raw: str) -> str | None:
    """Khớp mã thô với mã trong units.csv: không phân biệt hoa thường, H1 ~ H01."""
    ids = p.unit_ids()
    if raw in ids:
        return raw
    up = {i.upper(): i for i in ids}
    if raw.upper() in up:
        return up[raw.upper()]
    m = re.fullmatch(r"([A-Za-z]+)-?0*(\d+)", raw)
    if m:
        for i in ids:
            n = re.fullmatch(r"([A-Za-z]+)-?0*(\d+)", i)
            if n and n.group(1).upper() == m.group(1).upper() and int(n.group(2)) == int(m.group(2)):
                return i
    return None


def match(p: Project, name: str) -> dict | None:
    """Đoán (id, stage, tag, n) từ tên file. None nếu không nhận ra."""
    stem, ext = os.path.splitext(name)
    for pat in (p.meta.get("ingest") or {}).get("patterns") or []:
        m = re.match(pat["regex"], name)
        if m:
            gd = m.groupdict()
            uid = normalize_id(p, gd.get("id", ""))
            if uid:
                return _finish(uid, gd.get("stage") or pat.get("stage"), gd.get("tag") or "", ext)
    parts = stem.split("_")
    if len(parts) >= 2:
        uid = normalize_id(p, parts[0])
        if uid and parts[1] in p.stages:
            return _finish(uid, parts[1], "_".join(parts[2:]), ext)
    return None


def _finish(uid: str, stage: str, tag: str, ext: str) -> dict:
    n = 1
    m = TRY.search(tag)
    if m:
        n, tag = int(m.group(1)), tag[: m.start()]
    tag = TAG_SAFE.sub("-", tag).strip("-") or "x"
    return {"id": uid, "stage": stage, "tag": tag, "n": n, "ext": ext.lower()}


def dest_for(root: Path, info: dict) -> Path:
    """Đường đích không trùng: tăng _t<n> tới khi chưa có file nào."""
    d = root / "assets" / info["id"]
    n = info["n"]
    while True:
        f = d / f"{info['id']}_{info['stage']}_{info['tag']}_t{n}{info['ext']}"
        if not f.exists():
            return f
        n += 1


def ingest(p: Project, sources: list[Path] | None = None, only: tuple[str, str] | None = None,
           dry_run: bool = False, copy: bool = False) -> dict:
    moved, skipped = [], []
    touched: set[tuple[str, str]] = set()
    for src in sources or default_sources(p):
        if not src.is_dir():
            continue
        for f in sorted(src.iterdir()):
            if not f.is_file() or f.name.startswith(".") or f.suffix.lower() == ".json":
                continue
            if f.suffix.lower() in PARTIAL or f.stat().st_size == 0:
                skipped.append((f, "đang tải dở hoặc rỗng"))
                continue
            info = match(p, f.name)
            if not info:
                continue  # Downloads chứa đủ thứ: im lặng bỏ qua file không thuộc dự án
            if only and (info["id"], info["stage"]) != only:
                continue
            try:
                row = p.row(info["id"], info["stage"])
            except Exception:
                skipped.append((f, f"không có dòng {info['id']}:{info['stage']} trong units.csv"))
                continue
            dest = dest_for(p.root, info)
            rel = str(dest.relative_to(p.root)).replace("\\", "/")
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():  # phòng chạy song song
                    skipped.append((f, f"đích đã có {rel}"))
                    continue
                (shutil.copy2 if copy else shutil.move)(str(f), str(dest))
                log.write(p.root, row["id"], row["stage"], p.worker_of(row), "ingest", rel, "ok", f"từ {f}")
            moved.append({"src": str(f), "dest": str(dest), "rel": rel, "id": row["id"], "stage": row["stage"]})
            touched.add((row["id"], row["stage"]))
    status_changes = []
    if not dry_run:
        for uid, stage in sorted(touched):
            row = p.row(uid, stage)
            if row["status"] in ("todo", "spec_ready", "generating"):
                old = p.set_status(row, "candidates", force=row["status"] == "todo")
                status_changes.append((uid, stage, old, "candidates"))
        if touched:
            p.save_units()
    return {"moved": moved, "skipped": skipped, "status": status_changes}
