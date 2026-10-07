"""Pack video: QA clip (thời lượng, kích thước, viền đen → crop 16:9, contact sheet) và dựng thô bằng ffmpeg.

Dữ liệu dựng của mỗi đơn vị nằm trong specs/<id>.yaml:
    first_frame, frames      vị trí và độ dài trong phim (khung)
    camera                   camera giả cho ảnh tĩnh: push-in / pull-back / truck L→R / tilt-up / ... ("mạnh" = zoom 30%)
    transition_in            cut | fade từ đen 10f | light burst 6f | flash vàng 4f | flash trắng 4f | dissolve 8f | whip 4f
    transition_out           (tùy) flash trắng 6f | fade ra đen 12f
    cut: {start_frame, crop} khung bắt đầu trong clip; crop do `aiprod qa` ghi
Nguồn: tầng video đã duyệt → cắt clip; không có → ảnh tầng image + camera giả.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ..core import log
from ..core.media import cropdetect, ffmpeg, probe, run
from ..core.project import Project
from ..core.sheet import video_sheet

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
DISSOLVE_DEFAULT = 8


# ---------------------------------------------------------------- QA

def crop_16x9(detected: str | None, width: int, height: int, target=(16, 9)) -> str:
    """Từ crop của cropdetect (chỉ cắt viền), suy ra crop đúng tỉ lệ target, căn giữa, kích thước chẵn.

    Không có viền: cắt đều trên dưới cho đúng 16:9 (vd 1920x1088 → 1920:1080:0:4).
    """
    tw, th = target
    if detected:
        w, h, x, y = (int(v) for v in detected.split(":"))
    else:
        w, h, x, y = width, height, 0, 0
    if w * th > h * tw:  # rộng quá: giữ cao, cắt ngang
        nw = round(h * tw / th / 4) * 4  # bội 4 gần nhất (khớp crop đã dùng: 1036→1840, 992→1764)
        return f"{nw}:{h}:{x + (w - nw) // 2}:{y}"
    nh = round(w * th / tw / 4) * 4  # cao quá: giữ rộng, cắt dọc
    return f"{w}:{nh}:{x}:{y + (h - nh) // 2}"


def qa(p: Project, row: dict, path: Path, apply: bool = True) -> list[dict]:
    checks: list[dict] = []
    if path.suffix.lower() not in VIDEO_EXT:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
        ratio = w / h
        checks.append({"check": "ảnh 16:9", "ok": abs(ratio - 16 / 9) < 0.02, "detail": f"{w}x{h} (tỉ lệ {ratio:.3f})"})
        checks.append({"check": "độ phân giải", "ok": w >= 1280, "detail": f"rộng {w}px (cần ≥ 1280)"})
        return checks

    info = probe(path)
    spec = p.spec(row["id"])
    fps = float(p.meta.get("fps") or 30)
    need = (int(spec.get("frames") or 0) + int((spec.get("cut") or {}).get("start_frame") or 0)) / fps
    checks.append({"check": "thời lượng", "ok": info["duration"] >= need,
                   "detail": f"{info['duration']:.2f}s, shot cần {need:.2f}s (kể cả start_frame)"})
    checks.append({"check": "kích thước", "ok": info["width"] >= 1280, "detail": f"{info['width']}x{info['height']} @ {info['fps']}fps"})
    detected = cropdetect(path)
    crop = crop_16x9(detected, info["width"], info["height"])
    cw, ch = (int(v) for v in crop.split(":")[:2])
    scale = cw / int((p.meta.get("size") or [1920, 1080])[0])
    checks.append({"check": "viền đen → crop 16:9", "ok": scale >= 0.85,
                   "detail": f"cropdetect {detected} → crop {crop} (giữ {scale:.0%} chiều rộng)"})
    sheet = p.root / "review" / f"{row['id']}_{row['stage']}_qa.jpg"
    video_sheet(path, sheet, title=f"{row['id']}:{row['stage']} {path.name} crop {crop}", vf=f"crop={crop}")
    checks.append({"check": "contact sheet 3×3 (0.2–5.8s)", "ok": True, "detail": str(sheet.relative_to(p.root)),
                   "sheet": str(sheet.relative_to(p.root))})
    if apply:
        spec.setdefault("cut", {})["crop"] = crop
        p.save_spec(row["id"], spec)
    return checks


# ---------------------------------------------------------------- assemble

def _frames_of(s: str | None, default: int) -> int:
    m = re.search(r"(\d+)\s*f", s or "")
    return int(m.group(1)) if m else default


def still_filter(cam: str, n: int, fps: int, size=(1920, 1080)) -> str:
    """Camera giả cho ảnh tĩnh (zoompan trên ảnh phóng 2x để chuyển động mượt)."""
    cam = (cam or "").lower()
    if "mạnh" in cam:
        z0, z1 = 1.0, 1.30
    elif "push" in cam or "zoom" in cam:
        z0, z1 = 1.0, 1.12
    elif "pull" in cam:
        z0, z1 = 1.12, 1.0
    else:
        z0, z1 = 1.12, 1.12
    zx = f"{z0}+({z1}-{z0})*on/{n}"
    x, y = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    if "l→r" in cam or "l->r" in cam:
        x = f"(iw-iw/zoom)*on/{n}"
    elif "r→l" in cam or "r->l" in cam:
        x = f"(iw-iw/zoom)*(1-on/{n})"
    elif "tilt-up" in cam:
        zx, y = "1.12", f"(ih-ih/zoom)*(1-on/{n})"
    elif "tilt-down" in cam:
        zx, y = "1.12", f"(ih-ih/zoom)*on/{n}"
    W, H = size
    return (f"scale={2 * W}:{2 * H}:force_original_aspect_ratio=increase,crop={2 * W}:{2 * H},"
            f"zoompan=z='{zx}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={fps},setsar=1")


def fx_in(ti: str, fps: int) -> list[str]:
    ti = (ti or "").lower()
    n = _frames_of(ti, 0)
    if ti.startswith("fade từ đen") or ti.startswith("fade in"):
        return [f"fade=t=in:st=0:d={n / fps:.4f}:color=black"]
    if ti.startswith("light burst"):
        return [f"fade=t=in:st=0:d={n / fps:.4f}:color=white"]
    if ti.startswith("flash vàng"):
        return [f"fade=t=in:st=0:d={n / fps:.4f}:color=0xFFD966"]
    if ti.startswith("flash trắng"):
        return [f"fade=t=in:st=0:d={n / fps:.4f}:color=white"]
    return []  # cut, whip (chưa làm hiệu ứng whip: cắt thẳng như v4)


def fx_out(to: str, total: int, fps: int) -> list[str]:
    to = (to or "").lower()
    if not to:
        return []
    n = _frames_of(to, 6)
    color = "white" if "trắng" in to or "white" in to else ("0xFFD966" if "vàng" in to else "black")
    return [f"fade=t=out:st={(total - n) / fps:.4f}:d={n / fps:.4f}:color={color}"]


def _resolve(p: Project, rel: str) -> Path:
    f = Path(rel)
    return f if f.is_absolute() else p.root / f


def shot_sources(p: Project, draft: bool = False) -> list[dict]:
    """Danh sách shot theo thứ tự phim, mỗi shot kèm nguồn (clip hoặc ảnh)."""
    ok = {"approved", "assembled"} | ({"picked", "qa_pass", "qa_fail", "candidates"} if draft else set())
    shots = []
    for uid in p.unit_ids():
        spec = p.spec(uid)
        rows = {r["stage"]: r for r in p.unit_rows(uid)}
        v, im = rows.get("video"), rows.get("image")
        src, kind = None, None
        if v and v["status"] in ok and v["output"]:
            src, kind = _resolve(p, v["output"]), "clip"
        elif im and im["status"] in ok and im["output"]:
            src, kind = _resolve(p, im["output"]), "still"
        shots.append({"id": uid, "spec": spec, "src": src, "kind": kind,
                      "frames": int(spec.get("frames") or 0), "first": int(spec.get("first_frame") or 0)})
    shots.sort(key=lambda s: (s["first"], s["id"]))
    return shots


def assemble(p: Project, redo: set[str] | None = None, draft: bool = False, out: Path | None = None) -> Path:
    """Dựng thô: render từng segment (cache trong renders/_seg), ghép concat."""
    fps = int(p.meta.get("fps") or 30)
    W, H = (p.meta.get("size") or [1920, 1080])
    seg_dir = p.root / "renders" / "_seg"
    seg_dir.mkdir(parents=True, exist_ok=True)
    redo = redo or set()
    shots = shot_sources(p, draft)
    missing = [s["id"] for s in shots if not s["src"] or not s["frames"]]
    if missing and not draft:
        raise RuntimeError(f"thiếu nguồn hoặc frames cho: {', '.join(missing)}")
    enc = ["-an", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(fps)]
    segs = []
    for i, s in enumerate(shots):
        n = s["frames"]
        spec = s["spec"]
        ti = (spec.get("transition_in") or "").lower()
        nxt = shots[i + 1] if i + 1 < len(shots) else None
        ext = _frames_of(nxt["spec"].get("transition_in"), DISSOLVE_DEFAULT) \
            if nxt and (nxt["spec"].get("transition_in") or "").lower().startswith("dissolve") else 0
        seg = seg_dir / f"{s['id']}_seg.mp4"
        core = seg_dir / f"{s['id']}_core.mp4"
        if seg.exists() and core.exists() and s["id"] not in redo:
            segs.append(seg)
            continue
        if not s["src"]:  # bản nháp: khung đen thay chỗ shot chưa có
            run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={fps}",
                 "-frames:v", str(n + ext)] + enc + [str(core)])
        elif s["kind"] == "clip":
            cut = spec.get("cut") or {}
            crop = cut.get("crop")
            vf = (f"crop={crop},scale={W}:{H}:flags=lanczos," if crop else f"crop={W}:{H}:0:4,") + f"setsar=1,fps={fps}"
            run([ffmpeg(), "-y", "-v", "error", "-ss", f"{int(cut.get('start_frame') or 0) / fps:.4f}", "-i", str(s["src"]),
                 "-vf", vf, "-frames:v", str(n + ext)] + enc + [str(core)])
        else:
            vf = still_filter(spec.get("camera") or "", n + ext, fps, (W, H))
            run([ffmpeg(), "-y", "-v", "error", "-loop", "1", "-i", str(s["src"]), "-vf", vf,
                 "-frames:v", str(n + ext)] + enc + [str(core)])
        if ti.startswith("dissolve") and i > 0:
            prev = shots[i - 1]
            d = _frames_of(ti, DISSOLVE_DEFAULT)
            pcore, pext = seg_dir / f"{prev['id']}_core.mp4", seg_dir / f"{prev['id']}_ext.mp4"
            run([ffmpeg(), "-y", "-v", "error", "-i", str(pcore), "-vf",
                 f"select='gte(n,{prev['frames']})',setpts=N/{fps}/TB"] + enc + [str(pext)])
            fl = f"[0:v][1:v]xfade=transition=fade:duration={d / fps:.4f}:offset=0,format=yuv420p[v]"
            run([ffmpeg(), "-y", "-v", "error", "-i", str(pext), "-i", str(core), "-filter_complex", fl,
                 "-map", "[v]", "-frames:v", str(n)] + enc + [str(seg)])
        else:
            flt = fx_in(ti, fps) + fx_out(spec.get("transition_out"), n, fps)
            args = [ffmpeg(), "-y", "-v", "error", "-i", str(core)]
            if flt:
                args += ["-vf", ",".join(flt)]
            run(args + ["-frames:v", str(n)] + enc + [str(seg)])
        segs.append(seg)
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    out = out or p.root / "renders" / ("rough_draft.mp4" if draft else "rough.mp4")
    run([ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264",
         "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(out)])
    if not draft:
        for r in p.units:
            if r["status"] == "approved":
                r["status"] = "assembled"
        p.save_units()
    info = probe(out)
    log.write(p.root, action="assemble" + (":draft" if draft else ""), file=str(out.relative_to(p.root)),
              result="ok", note=f"{len(segs)} shot, {info['duration']:.2f}s")
    return out


def deliver(p: Project, max_mb: float = 30, src: Path | None = None) -> Path:
    """Nén preview: thử crf 26 → 28 (rồi giảm cỡ) tới khi < max_mb."""
    src = src or p.root / "renders" / "rough.mp4"
    if not src.exists():
        raise FileNotFoundError(f"{src} chưa có — chạy aiprod assemble trước")
    out = src.with_name(src.stem + "_preview.mp4")
    tries = [(26, None), (27, None), (28, None), (28, 1280), (30, 1280)]
    for crf, w in tries:
        args = [ffmpeg(), "-y", "-v", "error", "-i", str(src), "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
        if w:
            args += ["-vf", f"scale={w}:-2"]
        run(args + [str(out)])
        mb = out.stat().st_size / 1e6
        if mb < max_mb:
            log.write(p.root, action="deliver", file=str(out.relative_to(p.root)), result="ok",
                      note=f"crf {crf}{f', {w}px' if w else ''}, {mb:.1f} MB")
            return out
    raise RuntimeError(f"không nén được dưới {max_mb} MB (bản cuối {mb:.1f} MB)")


# ---------------------------------------------------------------- import

def _pick_image(folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    for rule in (lambda f: "_OK" in f.stem, lambda f: "P7" in f.stem):
        hit = [f for f in files if rule(f)]
        if hit:
            return hit[0]
    return files[0] if len(files) == 1 else None


def _style_sentence(src: Path) -> str:
    f = src / "docs" / "STYLE_APPROVED.md"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("Cinematic"):
                return line.strip()
    return ""


def _rules(src: Path) -> list[str]:
    f = src / "docs" / "PLAN_V3.md"
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8")
    m = re.search(r"## 2\. Luật cứng.*?\n(.*?)\n\*\*", text, re.S)
    out = []
    for line in (m.group(1) if m else "").splitlines():
        mm = re.match(r"\d+\.\s+(.*)", line.strip())
        if mm:
            out.append(re.sub(r"\*\*|`", "", mm.group(1)).split(". ")[0].rstrip("."))
    return out


def import_project(source: Path, dest: Path, picks: Path | None = None) -> str:
    """Nhập một dự án phim dạng `docs/timeline.json` + `assets/` thành dự án aiprod.

    Chỉ ĐỌC thư mục nguồn: file nguồn được tham chiếu bằng đường dẫn tuyệt đối, không chép, không sửa.
    """
    from ..core.scaffold import new_project

    tl = json.loads((source / "docs" / "timeline.json").read_text(encoding="utf-8"))
    pk = yaml.safe_load(picks.read_text(encoding="utf-8")) if picks else {}
    vids, starts, outs = pk.get("video") or {}, pk.get("start_frame") or {}, pk.get("transition_out") or {}
    assets = source / "assets"
    if dest.exists() and (dest / "PROJECT.md").exists():
        raise FileExistsError(f"{dest} đã là dự án aiprod — không ghi đè")
    new_project(dest, "video", tl.get("label") or source.name)
    p = Project.load(dest)
    p.meta.update(
        fps=tl["fps"], size=[tl["width"], tl["height"]], duration_frames=tl["duration_frames"],
        source=str(source), groups=[s["label"] for s in tl.get("sections", [])],
        style={"sentence": _style_sentence(source), "mj_suffix": "--ar 16:9 --s 250 --sw 100", "sref": {},
               "mj_no": "text, watermark, logo, 3d, photorealistic, hair bun, ponytail, visible face, kiss",
               "grok_suffix": "Keep the vivid 2D anime cel-shaded look, clean line art, glowing saturated colors, "
                              "no 3D, no photorealism."},
        rules=_rules(source),
    )
    p.meta["gates"]["G1"] = {"status": "passed", "by": "import", "at": log.now()}
    p.save_meta()
    problems = []
    for order, s in enumerate(tl["shots"], 1):
        uid = s["id"]
        img = _pick_image(assets / "img" / uid)
        vid = assets / vids[uid] if uid in vids else None
        if vid and not vid.exists():
            problems.append(f"{uid}: không thấy {vid}")
            vid = None
        p.units.append({"id": uid, "group": s["section"], "order": str(order), "depends_on": "", "stage": "image",
                        "status": "approved" if img else "todo", "worker": "", "spec_file": "", "pick": "1" if img else "",
                        "output": str(img) if img else "", "note": "" if img else "chưa có ảnh"})
        if vid:
            p.units.append({"id": uid, "group": s["section"], "order": str(order), "depends_on": f"{uid}:image",
                            "stage": "video", "status": "approved", "worker": "", "spec_file": "", "pick": "1",
                            "output": str(vid), "note": ""})
        spec = {k: s.get(k) for k in ("section", "look", "first_frame", "frames", "camera", "transition_in", "content")}
        spec["source"] = "GROK" if vid else "STILL"
        if uid in outs:
            spec["transition_out"] = outs[uid]
        spec["cut"] = {"start_frame": int(starts.get(uid, 0))}
        p.save_spec(uid, spec)
        if not img:
            problems.append(f"{uid}: không chọn được ảnh trong assets/img/{uid}")
    p.save_units()
    log.write(dest, action="import", file=str(source), result="ok", note=f"{len(tl['shots'])} shot")
    n_vid = sum(1 for u in p.units if u["stage"] == "video")
    msg = f"Nhập {len(tl['shots'])} shot ({n_vid} clip, {len(tl['shots']) - n_vid} ảnh tĩnh) vào {dest}"
    return msg + ("".join(f"\n⚠ {x}" for x in problems) if problems else "")
