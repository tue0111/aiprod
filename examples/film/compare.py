"""So bản dựng với một bản tham chiếu: khung đầu (và khung giữa) của từng shot.

    python examples/film/compare.py <dự án aiprod> <video của mình> <video tham chiếu>

Mỗi shot: trích khung first_frame và first_frame + frames//2 ở cả hai video, thu nhỏ 320x180,
tính sai khác tuyệt đối trung bình (0–255). Dưới ngưỡng (mặc định 4) là khớp.
In bảng markdown và lưu contact sheet so sánh vào review/compare_v4.jpg.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from aiprod.core.media import frame_index, probe
from aiprod.core.project import Project
from aiprod.core.sheet import grid


def mad(a: Path, b: Path) -> float:
    A = Image.open(a).convert("RGB").resize((320, 180))
    B = Image.open(b).convert("RGB").resize((320, 180))
    return sum(ImageStat.Stat(ImageChops.difference(A, B)).mean) / 3


def main(project: str, mine: str, ref: str, threshold: float = 4.0) -> int:
    p = Project.load(project)
    shots = sorted(((p.spec(u), u) for u in p.unit_ids()), key=lambda x: int(x[0].get("first_frame") or 0))
    im, rf = probe(mine), probe(ref)
    print(f"Của mình: {im['duration']:.3f}s {im['width']}x{im['height']} {im['fps']}fps {im['size_mb']} MB")
    print(f"Tham chiếu: {rf['duration']:.3f}s {rf['width']}x{rf['height']} {rf['fps']}fps {rf['size_mb']} MB\n")
    print("| Shot | Khung | Sai khác khung đầu | Sai khác khung giữa | Khớp |")
    print("|---|---|---|---|---|")
    bad, pics, labels = [], [], []
    with tempfile.TemporaryDirectory() as td:
        T = Path(td)
        for spec, uid in shots:
            f0, n = int(spec["first_frame"]), int(spec["frames"])
            d = []
            for tag, k in (("a", f0), ("m", f0 + n // 2)):
                x = frame_index(mine, k, T / f"{uid}_{tag}_mine.png", width=320)
                y = frame_index(ref, k, T / f"{uid}_{tag}_ref.png", width=320)
                d.append(mad(x, y))
            ok = max(d) < threshold
            bad += [] if ok else [uid]
            print(f"| {uid} | {f0} | {d[0]:.2f} | {d[1]:.2f} | {'✓' if ok else '✗'} |")
            for side in ("mine", "ref"):
                pics.append(T / f"{uid}_a_{side}.png")
                labels.append(f"{uid} {'mới' if side == 'mine' else 'v4'}")
        out = p.root / "review" / "compare_v4.jpg"
        grid(pics, labels, out, cols=8, cell_w=240, title="Khung đầu mỗi shot: mới | v4")
    print(f"\n{len(shots) - len(bad)}/{len(shots)} shot khớp (ngưỡng {threshold}). Contact sheet: {out}")
    if bad:
        print("Lệch: " + ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(*sys.argv[1:4]))
