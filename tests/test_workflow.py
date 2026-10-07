"""Tên file, ingest, thẻ việc, duyệt/cổng, bot, bài học."""
import json

import pytest

from aiprod.adapters.bot_file import simulate, sync
from aiprod.core import actions, log
from aiprod.core.ingest import dest_for, ingest, match, normalize_id
from aiprod.core.lessons import add_lesson, list_lessons
from aiprod.core.project import Project
from aiprod.core.tasks import render_prompt

TWO = "A1,g,1,,image,todo,,,,,\nA1,g,1,,video,todo,,,,,\nB2,g,2,,image,todo,,,,,\n"


def reload(p):
    return Project.load(p.root)


# ---------------------------------------------------------------- tên file

def test_normalize_id(proj):
    p = proj("H01,g,1,,image,todo,,,,,\nD12,g,2,,image,todo,,,,,\n")
    assert normalize_id(p, "H01") == "H01"
    assert normalize_id(p, "h1") == "H01"
    assert normalize_id(p, "D-12") == "D12"
    assert normalize_id(p, "X9") is None


@pytest.mark.parametrize("name,expect", [
    ("A1_image_mjA.png", ("A1", "image", "mjA", 1)),
    ("A1_image_mjA_t3.png", ("A1", "image", "mjA", 3)),
    ("a1_video.mp4", ("A1", "video", "x", 1)),
    ("A1_video_web take!1_t2.mp4", ("A1", "video", "web-take-1", 2)),
])
def test_match_standard_names(proj, name, expect):
    m = match(proj(TWO), name)
    assert (m["id"], m["stage"], m["tag"], m["n"]) == expect


def test_match_ignores_unrelated(proj):
    p = proj(TWO)
    for name in ["photo.png", "A1_paint_x.png", "Z9_image_x.png", "report.pdf"]:
        assert match(p, name) is None


def test_match_custom_pattern(proj):
    p = proj("H01,g,1,,image,todo,,,,,\nH01,g,1,,video,todo,,,,,\n",
             meta={"ingest": {"patterns": [{"regex": r"^G-(?P<id>[A-Z]+\d+)_(?P<tag>.+)\.mp4$", "stage": "video"}]}})
    m = match(p, "G-H1_P7_t1.mp4")
    assert (m["id"], m["stage"], m["tag"], m["n"]) == ("H01", "video", "P7", 1)


def test_dest_never_overwrites(proj):
    p = proj(TWO)
    info = {"id": "A1", "stage": "image", "tag": "mj", "n": 1, "ext": ".png"}
    d1 = dest_for(p.root, info)
    d1.parent.mkdir(parents=True)
    d1.write_text("x")
    d2 = dest_for(p.root, info)
    assert d1.name == "A1_image_mj_t1.png" and d2.name == "A1_image_mj_t2.png"


# ---------------------------------------------------------------- ingest

def test_ingest_moves_renames_and_updates(proj, tmp_path):
    p = proj(TWO)
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "A1_image_mj.png").write_bytes(b"1")
    (dl / "A1_image_mj_t1.png").write_bytes(b"2")      # trùng tên đích → _t2
    (dl / "A1_image_dl.png.crdownload").write_bytes(b"3")  # đang tải dở
    (dl / "A1_image_empty.png").write_bytes(b"")        # rỗng
    (dl / "holiday.png").write_bytes(b"4")              # không thuộc dự án
    res = ingest(p, [dl])
    assert sorted(m["rel"] for m in res["moved"]) == ["assets/A1/A1_image_mj_t1.png", "assets/A1/A1_image_mj_t2.png"]
    assert len(res["skipped"]) == 2
    assert (dl / "holiday.png").exists() and not (dl / "A1_image_mj.png").exists()
    assert reload(p).row("A1", "image")["status"] == "candidates"
    assert [r["action"] for r in log.read(p.root)].count("ingest") == 2


def test_ingest_dry_run_and_copy(proj, tmp_path):
    p = proj(TWO)
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "B2_image_a.png").write_bytes(b"1")
    assert ingest(p, [dl], dry_run=True)["moved"] and not (p.root / "assets" / "B2").exists()
    ingest(p, [dl], copy=True)
    assert (dl / "B2_image_a.png").exists() and (p.root / "assets/B2/B2_image_a_t1.png").exists()


def test_ingest_unknown_stage_row_skipped(proj, tmp_path):
    p = proj("A1,g,1,,image,todo,,,,,\n")
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "A1_video_x.mp4").write_bytes(b"1")
    res = ingest(p, [dl])
    assert not res["moved"] and "không có dòng" in res["skipped"][0][1]


# ---------------------------------------------------------------- thẻ việc

def test_render_prompt_missing_and_punctuation():
    text, missing = render_prompt("{a}. {b}. Static. {c}", {"a": "Hair sways.", "b": ""})
    assert text == "Hair sways. Static." and missing == ["b", "c"]


def test_task_card_contents(proj):
    p = proj(TWO, meta={"style": {"sentence": "Anime style.", "sref": {"g": "URL1"}, "mj_suffix": "--ar 16:9",
                                   "mj_no": "text"}, "characters": {"woman": "long loose hair"}})
    p.body = p.body.replace("## Luật cứng\n\n- …", "## Luật cứng\n\n- Tóc nữ luôn xõa")
    p.save_meta()
    p.save_spec("A1", {"content": "Girl at window", "video": {"motion": "Hair sways"}})
    r = actions.task(reload(p), "A1", "image")
    card = r["path"].read_text(encoding="utf-8")
    for needle in ["Unit: A1 | Stage: image | Worker: mj", "Girl at window", "--sref URL1", "Anime style.",
                   "Tóc nữ luôn xõa", "A1_image_<tag>_t<n>.png", "aiprod ingest", "## Thẻ năng lực: mj",
                   "## QA checklist (image)"]:
        assert needle in card, needle
    assert reload(p).row("A1", "image")["status"] == "spec_ready"


def test_task_blocked_until_previous_stage_approved(proj):
    p = proj(TWO)
    with pytest.raises(actions.ActionError, match="tầng trước"):
        actions.task(p, "A1", "video")


def test_task_keeps_hand_edits(proj):
    p = proj(TWO)
    path = actions.task(p, "A1", "image")["path"]
    path.write_text("sửa tay", encoding="utf-8")
    actions.task(reload(p), "A1", "image")
    assert path.read_text(encoding="utf-8") == "sửa tay"
    actions.task(reload(p), "A1", "image", force=True)
    assert path.read_text(encoding="utf-8") != "sửa tay"


# ---------------------------------------------------------------- duyệt / cổng

def _to_picked(p, uid="A1", stage="image"):
    actions.task(p, uid, stage)
    f = p.root / "assets" / uid / f"{uid}_{stage}_x_t1.png"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"1")
    actions.collect(reload(p), uid, stage)
    actions.pick(reload(p), uid, stage, 1, "owner")
    return reload(p)


def test_submit_blocked_by_g1(proj):
    p = proj(TWO, g1=False)
    with pytest.raises(actions.ActionError, match="G1"):
        actions.submit(p, "A1", "image")


def test_gate_only_human(proj):
    p = proj(TWO, g1=False)
    with pytest.raises(actions.ActionError):
        actions.gate(p, "G1", True, "claude")
    actions.gate(p, "G1", True, "owner")
    assert reload(p).gate_passed("G1")


def test_g3_requires_everything_approved(proj):
    with pytest.raises(actions.ActionError, match="G3"):
        actions.gate(proj(TWO), "G3", True, "owner")


def test_pick_out_of_range(proj):
    p = proj(TWO)
    with pytest.raises(actions.ActionError, match="không có số 5"):
        actions.pick(_to_picked(p), "A1", "image", 5, "owner")


def test_approve_requires_qa(proj):
    p = _to_picked(proj(TWO))
    with pytest.raises(actions.ActionError, match="qa_pass"):
        actions.approve(p, "A1", "image", "owner")


def test_g2_stage_needs_human_or_delegation(proj):
    p = _to_picked(proj(TWO))
    actions.qa_verdict(p, "A1", "image", True, "ok", "claude")
    with pytest.raises(actions.ActionError, match="G2"):
        actions.approve(reload(p), "A1", "image", "claude")
    p = reload(p)
    p.meta["gates"]["G2"]["delegated"] = True
    p.save_meta()
    actions.approve(reload(p), "A1", "image", "claude")
    assert reload(p).row("A1", "image")["status"] == "approved"


def test_non_g2_stage_agent_can_approve(proj):
    p = proj("A1,g,1,,image,approved,,,1,x.png,\nA1,g,1,,video,todo,,,,,\n")
    p = _to_picked(p, "A1", "video")
    actions.qa_verdict(p, "A1", "video", True, "", "claude")
    actions.approve(reload(p), "A1", "video", "claude")
    assert reload(p).row("A1", "video")["status"] == "approved"


def test_qa_fail_then_respec(proj):
    p = _to_picked(proj(TWO))
    actions.qa_verdict(p, "A1", "image", False, "thiếu ly", "owner")
    p = reload(p)
    assert p.row("A1", "image")["status"] == "qa_fail" and p.row("A1", "image")["note"] == "thiếu ly"
    actions.task(p, "A1", "image")
    assert reload(p).row("A1", "image")["status"] == "spec_ready"


def test_skip_qa_only_human(proj):
    p = _to_picked(proj(TWO))
    with pytest.raises(actions.ActionError):
        actions.approve(p, "A1", "image", "claude", skip_qa=True)
    actions.approve(reload(p), "A1", "image", "owner", skip_qa=True)
    assert "[bỏ qua QA]" in reload(p).row("A1", "image")["note"]


# ---------------------------------------------------------------- bot

def test_bot_round_trip(proj):
    p = proj(TWO, meta={"adapters": {"mj": "bot_file"}, "bot": {"max_candidates": 2}})
    p.save_spec("A1", {"content": "Girl"})
    p.save_spec("B2", {"content": "Boy"})
    actions.submit(p, "A1", "image")
    actions.submit(reload(p), "B2", "image")
    job = json.loads((p.root / "queue/inbox/A1_image.json").read_text(encoding="utf-8"))
    assert job["protocol"] == "aiprod-bot/1" and job["output_name"] == "A1_image_<tag>_t<n>.png"
    with pytest.raises(actions.ActionError, match="spec_ready"):
        actions.submit(reload(p), "A1", "image")  # đang generating
    simulate(reload(p), fail={"B2:image"})
    lines = sync(reload(p))
    p = reload(p)
    assert len(lines) == 2
    assert p.row("A1", "image")["status"] == "candidates"
    assert p.row("B2", "image")["status"] == "spec_ready"
    assert len(list((p.root / "assets/A1").glob("A1_image_bot_t*.png"))) == 2
    assert not list((p.root / "queue/inbox").glob("*.json"))
    assert len(list((p.root / "queue/done").glob("*.json"))) == 4


def test_bot_result_without_files_is_failure(proj):
    p = proj(TWO, meta={"adapters": {"mj": "bot_file"}})
    actions.submit(p, "A1", "image")
    (p.root / "queue/outbox/A1_image.json").write_text(json.dumps({"job": "A1_image", "status": "done", "files": []}))
    sync(reload(p))
    assert reload(p).row("A1", "image")["status"] == "spec_ready"


# ---------------------------------------------------------------- bài học

def test_lessons(proj):
    p = proj(TWO)
    add_lesson(p, "grok", "Camera đứng yên")
    add_lesson(p, "grok", "Camera đứng yên")  # không ghi trùng
    add_lesson(p, "newtool", "Luật mới", section="Lỗi hay gặp")
    text = (p.root / "tools/grok.md").read_text(encoding="utf-8")
    assert text.count("Camera đứng yên (") == 1
    out = list_lessons(p)
    assert "[Lỗi hay gặp] Luật mới" in out and "## newtool" in out
