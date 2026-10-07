"""Contact sheet: ghép nhiều ảnh (hoặc khung video) thành một tấm có đánh số để người duyệt nhanh."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def _font(size: int):
    for name in ["arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grid(images: list[Path], labels: list[str], out: Path, cols: int | None = None, cell_w: int = 480,
         title: str = "") -> Path:
    """Ghép ảnh thành lưới. Ô giữ tỉ lệ ảnh đầu tiên; nhãn đánh ở góc trên trái."""
    if not images:
        raise ValueError("không có ảnh nào để ghép")
    cols = cols or min(len(images), 3 if len(images) in (3, 5, 6, 9) else 4)
    rows = math.ceil(len(images) / cols)
    with Image.open(images[0]) as im0:
        ratio = im0.height / im0.width
    cell_h = int(cell_w * ratio)
    pad, top = 6, (36 if title else 0)
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad, rows * (cell_h + pad) + pad + top), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    font = _font(max(14, cell_w // 22))
    if title:
        draw.text((pad + 4, 8), title, fill=(240, 240, 240), font=_font(20))
    for i, (path, label) in enumerate(zip(images, labels)):
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((cell_w, cell_h))
            x = pad + (i % cols) * (cell_w + pad)
            y = top + pad + (i // cols) * (cell_h + pad)
            sheet.paste(im, (x + (cell_w - im.width) // 2, y + (cell_h - im.height) // 2))
        tw = draw.textlength(label, font=font)
        draw.rectangle([x, y, x + tw + 12, y + font.size + 10], fill=(0, 0, 0))
        draw.text((x + 6, y + 4), label, fill=(255, 220, 80), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def video_times(duration: float, n: int = 9, start: float = 0.2, end: float = 5.8) -> list[float]:
    end = min(end, max(duration - 0.05, start))
    if n == 1:
        return [start]
    return [round(start + (end - start) * i / (n - 1), 3) for i in range(n)]


def video_sheet(path: Path, out: Path, n: int = 9, start: float = 0.2, end: float = 5.8, title: str = "",
                vf: str = "") -> Path:
    """Contact sheet 3×3 theo thời gian (mặc định 0.2–5.8s) của một clip."""
    from .media import frame_at, probe

    dur = probe(path)["duration"]
    times = video_times(dur, n, start, end)
    with tempfile.TemporaryDirectory() as td:
        frames = [frame_at(path, t, Path(td) / f"f{i:02d}.jpg", width=640, vf=vf) for i, t in enumerate(times)]
        return grid(frames, [f"{t:.1f}s" for t in times], out, cols=3, title=title or path.name)


def sheet_for(p, uid: str, stage: str, out: Path | None = None) -> Path:
    """Contact sheet các ứng viên của (đơn vị, tầng). Video: mỗi ứng viên một khung giữa clip."""
    from .actions import candidates
    from .media import frame_at, probe

    files = [p.root / f for f in candidates(p, uid, stage)]
    row = p.row(uid, stage)
    if not files and row["output"]:
        files = [Path(row["output"]) if Path(row["output"]).is_absolute() else p.root / row["output"]]
    if not files:
        raise ValueError(f"{uid}:{stage} chưa có ứng viên nào trong assets/{uid}/")
    out = out or p.root / "review" / f"{uid}_{stage}_sheet.jpg"
    if len(files) == 1 and files[0].suffix.lower() in VIDEO_EXT:
        return video_sheet(files[0], out, title=f"{uid}:{stage} {files[0].name}")
    with tempfile.TemporaryDirectory() as td:
        imgs = []
        for i, f in enumerate(files):
            if f.suffix.lower() in VIDEO_EXT:
                imgs.append(frame_at(f, probe(f)["duration"] / 2, Path(td) / f"c{i}.jpg", width=640))
            else:
                imgs.append(f)
        return grid(imgs, [f"{i}. {f.name}" for i, f in enumerate(files, 1)], out, title=f"{uid}:{stage} — ứng viên")
