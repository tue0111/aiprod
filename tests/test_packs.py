"""Pack video (crop, QA, assemble, import, deliver) và slides (QA, assemble, deliver)."""
import json
from pathlib import Path

import pytest

from aiprod.core import actions
from aiprod.core.media import ffmpeg, has_ffmpeg, probe, run
from aiprod.core.project import Project
from aiprod.core.qa import run_qa
from aiprod.packs import slides, video

needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason="cần ffmpeg")


@pytest.mark.parametrize("detected,expect", [
    ("1920:1036:0:26", "1840:1036:40:26"),   # H01 phim mẫu
    ("1920:992:0:48", "1764:992:78:48"),     # E01
    ("1920:1056:0:16", "1876:1056:22:16"),   # H03
    (None, "1920:1080:0:4"),                 # 1920x1088 không viền
    ("1440:1080:240:0", "1440:808:240:136"),  # quá cao → cắt dọc
])
def test_crop_16x9(detected, expect):
    assert video.crop_16x9(detected, 1920, 1088) == expect


def test_fx_parsing():
    assert video.fx_in("fade từ đen 10f", 30) == ["fade=t=in:st=0:d=0.3333:color=black"]
    assert "0xFFD966" in video.fx_in("flash vàng 4f", 30)[0]
    assert video.fx_in("cut", 30) == [] and video.fx_in("whip 4f", 30) == []
    assert video.fx_out("fade ra đen 12f", 60, 30) == ["fade=t=out:st=1.6000:d=0.4000:color=black"]


def _clip(path: Path, bars: int = 26, seconds: float = 2.5, color: str = "red"):
    """Clip 1920x1088 có viền đen trên/dưới `bars` px."""
    path.parent.mkdir(parents=True, exist_ok=True)
    h = 1088 - 2 * bars
    run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1920x{h}:r=24:d={seconds}",
         "-vf", f"pad=1920:1088:0:{bars}:black", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(path)])
    return path


def _film(src: Path) -> Path:
    """Dự án phim mẫu dạng E:\\Film: docs/timeline.json + assets/img + assets/grok."""
    from PIL import Image

    shots = [
        {"id": "H01", "section": "A", "look": "x", "first_frame": 0, "frames": 30, "source": "GROK",
         "camera": "giữ khung", "transition_in": "fade từ đen 10f", "content": "a"},
        {"id": "B01", "section": "B", "look": "x", "first_frame": 30, "frames": 15, "source": "STILL",
         "camera": "push-in", "transition_in": "light burst 6f", "content": "b"},
        {"id": "C01", "section": "C", "look": "x", "first_frame": 45, "frames": 30, "source": "GROK",
         "camera": "truck", "transition_in": "dissolve 8f", "content": "c"},
    ]
    tl = {"label": "Mini", "fps": 30, "width": 1920, "height": 1080, "duration_frames": 75, "shots": shots,
          "sections": [{"label": s} for s in "ABC"]}
    (src / "docs").mkdir(parents=True)
    (src / "docs/timeline.json").write_text(json.dumps(tl), encoding="utf-8")
    (src / "docs/STYLE_APPROVED.md").write_text("Cinematic 2D anime, test.\n", encoding="utf-8")
    for sid, col in [("H01", "blue"), ("B01", "green"), ("C01", "orange")]:
        d = src / "assets/img" / sid
        d.mkdir(parents=True)
        Image.new("RGB", (1456, 816), col).save(d / f"{sid}_mj1_OK.png")
    _clip(src / "assets/grok/G-H1/G-H1_P7_t1.mp4", bars=26)
    _clip(src / "assets/grok/G-C01/G-C01_take1_OK.mp4", bars=0)
    picks = src / "picks.yaml"
    picks.write_text("video:\n  H01: grok/G-H1/G-H1_P7_t1.mp4\n  C01: grok/G-C01/G-C01_take1_OK.mp4\n"
                     "start_frame:\n  H01: 5\ntransition_out:\n  C01: fade ra đen 6f\n", encoding="utf-8")
    return picks


@needs_ffmpeg
def test_import_qa_assemble_deliver(tmp_path):
    src, dest = tmp_path / "Film", tmp_path / "proj"
    picks = _film(src)
    before = {f: f.stat().st_mtime for f in src.rglob("*") if f.is_file()}

    msg = video.import_project(src, dest, picks)
    assert "3 shot (2 clip, 1 ảnh tĩnh)" in msg
    with pytest.raises(FileExistsError):
        video.import_project(src, dest, picks)
    p = Project.load(dest)
    assert p.check_plan() == [] and p.gate_passed("G1")
    assert p.spec("H01")["cut"]["start_frame"] == 5 and p.spec("C01")["transition_out"] == "fade ra đen 6f"
    assert [r["stage"] for r in p.unit_rows("B01")] == ["image"]

    r = run_qa(p, "H01", "video")
    assert r["ok"] and Project.load(dest).spec("H01")["cut"]["crop"] == "1840:1036:40:26"
    assert (dest / r["sheet"]).exists()
    run_qa(Project.load(dest), "C01", "video")
    assert Project.load(dest).spec("C01")["cut"]["crop"] == "1920:1080:0:4"

    out = video.assemble(Project.load(dest))
    info = probe(out)
    assert (info["width"], info["height"]) == (1920, 1080)
    assert abs(info["duration"] - 75 / 30) < 0.05
    assert all(r["status"] == "assembled" for r in Project.load(dest).units)

    prev = video.deliver(Project.load(dest), max_mb=30)
    assert prev.exists() and prev.stat().st_size < 30e6

    after = {f: f.stat().st_mtime for f in src.rglob("*") if f.is_file()}
    assert before == after  # import/qa/assemble chỉ đọc nguồn


@needs_ffmpeg
def test_video_qa_flags_short_clip(proj, tmp_path):
    p = proj("A1,g,1,,video,picked,,,1,assets/A1/A1_video_x_t1.mp4,\n")
    _clip(p.root / "assets/A1/A1_video_x_t1.mp4", bars=0, seconds=1)
    p.save_spec("A1", {"frames": 60})
    r = run_qa(Project.load(p.root), "A1", "video")
    assert not r["ok"] and Project.load(p.root).row("A1", "video")["status"] == "qa_fail"


def test_qa_missing_output(proj):
    p = proj("A1,g,1,,image,picked,,,1,assets/A1/nope.png,\n")
    r = run_qa(p, "A1", "image")
    assert not r["ok"] and "không thấy" in r["report"]


# ---------------------------------------------------------------- slides

def test_slides_flow(proj):
    p = proj("S1,a,1,,outline,todo,,,,,\nS1,a,1,,content,todo,,,,,\nS2,b,2,,outline,todo,,,,,\nS2,b,2,,content,todo,,,,,\n",
             pack="slides")
    texts = {"outline": "- ý một\n- ý hai\n", "content": "# Tiêu đề {u}\n- Ý một ngắn\n- Ý hai ngắn\n"}
    for u in ["S1", "S2"]:
        for st in ["outline", "content"]:
            p = Project.load(p.root)
            actions.task(p, u, st)
            f = p.root / "assets" / u / f"{u}_{st}_claude_t1.md"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(texts[st].format(u=u), encoding="utf-8")
            actions.collect(Project.load(p.root), u, st)
            actions.pick(Project.load(p.root), u, st, 1, "owner")
            assert run_qa(Project.load(p.root), u, st)["ok"]
            with pytest.raises(actions.ActionError, match="tự chấm pass"):  # worker không chấm pass bài mình
                actions.qa_verdict(Project.load(p.root), u, st, True, "", "claude")
            actions.qa_verdict(Project.load(p.root), u, st, True, "", "owner")
            actions.approve(Project.load(p.root), u, st, "owner")
    p = Project.load(p.root)
    assert p.assemble_ready()
    deck = slides.assemble(p)
    html = deck.read_text(encoding="utf-8")
    assert html.count('class="slide') == 2 and "Tiêu đề S2" in html
    assert slides.deliver(Project.load(p.root)).suffix == ".zip"


def test_slides_qa_limits(proj, tmp_path):
    p = proj("S1,a,1,,content,picked,,,1,assets/S1/c.md,\n", pack="slides")
    f = p.root / "assets/S1/c.md"
    f.parent.mkdir(parents=True)
    f.write_text("# Một tiêu đề quá dài vượt hẳn tám từ cho phép\n- " + "chữ " * 45, encoding="utf-8")
    checks = {c["check"]: c["ok"] for c in slides.qa(p, p.row("S1", "content"), f)}
    assert checks == {"có tiêu đề `# ...`": True, "tiêu đề ≤ 8 từ": False, "thân ≤ 40 từ": False}
