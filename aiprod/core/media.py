"""Tiện ích ffmpeg/ffprobe dùng chung (tìm binary, chạy lệnh, đọc thông tin, trích khung)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def _find(name: str) -> str:
    exe = shutil.which(name)
    if exe:
        return exe
    # chỗ cài thường gặp trên Windows khi chưa có trong PATH
    for d in [os.environ.get("AIPROD_FFMPEG_DIR", ""), os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg"),
              r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]:
        for cand in (Path(d) / f"{name}.exe", Path(d) / name):
            if d and cand.exists():
                return str(cand)
    raise MediaError(f"không tìm thấy {name}; cài ffmpeg và thêm vào PATH (hoặc đặt AIPROD_FFMPEG_DIR)")


def ffmpeg() -> str:
    return _find("ffmpeg")


def ffprobe() -> str:
    return _find("ffprobe")


def has_ffmpeg() -> bool:
    try:
        ffmpeg()
        ffprobe()
        return True
    except MediaError:
        return False


def run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(args, capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise MediaError(" ".join(map(str, args))[:400] + "\n" + (r.stderr or "")[-1500:])
    return r


def probe(path: str | Path) -> dict:
    r = run([ffprobe(), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise MediaError(f"{path}: không có luồng video")
    num, _, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    dur = float(data.get("format", {}).get("duration") or v.get("duration") or 0)
    return {"width": int(v["width"]), "height": int(v["height"]), "fps": round(fps, 3), "duration": dur,
            "size_mb": round(float(data.get("format", {}).get("size", 0)) / 1e6, 2)}


def frame_at(path: str | Path, t: float, out: str | Path, width: int | None = None, vf: str = "") -> Path:
    filters = [f for f in [vf, f"scale={width}:-2" if width else ""] if f]
    args = [ffmpeg(), "-y", "-v", "error", "-ss", f"{max(t, 0):.4f}", "-i", str(path), "-frames:v", "1"]
    if filters:
        args += ["-vf", ",".join(filters)]
    run(args + [str(out)])
    return Path(out)


def frame_index(path: str | Path, n: int, out: str | Path, width: int | None = None) -> Path:
    """Khung thứ n (đếm từ 0) theo đúng thứ tự giải mã — dùng để so khớp chính xác từng khung."""
    vf = f"select=eq(n\\,{n})" + (f",scale={width}:-2" if width else "")
    run([ffmpeg(), "-y", "-v", "error", "-i", str(path), "-vf", vf, "-fps_mode", "passthrough", "-frames:v", "1", str(out)])
    return Path(out)


def cropdetect(path: str | Path, limit: int = 24, round_to: int = 2) -> str | None:
    """Crop phổ biến nhất theo cropdetect (chuỗi w:h:x:y) hoặc None."""
    r = subprocess.run([ffmpeg(), "-v", "info", "-i", str(path), "-vf", f"cropdetect={limit}:{round_to}:0",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    counts: dict[str, int] = {}
    for line in r.stderr.splitlines():
        i = line.find("crop=")
        if i >= 0:
            c = line[i + 5:].split()[0]
            counts[c] = counts.get(c, 0) + 1
    return max(counts, key=counts.get) if counts else None
