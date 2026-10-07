"""Pack images: QA kích thước/tỉ lệ; ghép = contact sheet + zip toàn bộ ảnh đã duyệt."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from ..core import log
from ..core.project import Project
from ..core.sheet import grid


def _size(p: Project) -> tuple[int, int]:
    m = re.match(r"(\d+)\s*x\s*(\d+)", str(p.meta.get("format", "")))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def qa(p: Project, row: dict, path: Path, apply: bool = True) -> list[dict]:
    from PIL import Image

    with Image.open(path) as im:
        w, h = im.size
    tw, th = _size(p)
    checks = [{"check": "đọc được ảnh", "ok": True, "detail": f"{w}x{h}"}]
    if tw and th:
        checks.append({"check": "đúng tỉ lệ", "ok": abs(w / h - tw / th) < 0.02, "detail": f"{w / h:.3f} vs {tw / th:.3f}"})
        checks.append({"check": "đủ độ phân giải", "ok": w >= tw * 0.9, "detail": f"rộng {w}px, cần ≈ {tw}px"})
    return checks


def _finals(p: Project, draft: bool) -> list[tuple[str, Path]]:
    ok = {"approved", "assembled"} | ({"picked", "qa_pass", "candidates"} if draft else set())
    out = []
    for uid in p.unit_ids():
        rows = [r for r in p.unit_rows(uid) if r["status"] in ok and r["output"]]
        if rows:
            f = Path(rows[-1]["output"])
            out.append((uid, f if f.is_absolute() else p.root / f))
    return out


def assemble(p: Project, redo: set[str] | None = None, draft: bool = False, out: Path | None = None) -> Path:
    finals = _finals(p, draft)
    if not finals:
        raise RuntimeError("chưa có ảnh nào đã duyệt")
    rd = p.root / "renders"
    out = out or rd / ("grid_draft.jpg" if draft else "grid.jpg")
    grid([f for _, f in finals], [u for u, _ in finals], out)
    if not draft:
        for r in p.units:
            if r["status"] == "approved":
                r["status"] = "assembled"
        p.save_units()
    log.write(p.root, action="assemble", file=str(out.relative_to(p.root)), result="ok", note=f"{len(finals)} ảnh")
    return out


def deliver(p: Project, max_mb: float = 30, src: Path | None = None) -> Path:
    d = p.root / "deliver"
    d.mkdir(exist_ok=True)
    out = d / "images.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        for uid, f in _finals(p, draft=False):
            z.write(f, f"{uid}{f.suffix}")
    mb = out.stat().st_size / 1e6
    log.write(p.root, action="deliver", file=str(out.relative_to(p.root)), result="ok", note=f"{mb:.1f} MB")
    if mb >= max_mb:
        log.write(p.root, action="deliver", result="cảnh báo", note=f"{mb:.1f} MB ≥ {max_mb} MB")
    return out


