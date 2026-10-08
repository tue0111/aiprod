"""Cổng cơ học của HARNESS.md."""
import pytest

from aiprod.core import actions, log
from aiprod.core.project import Project

# tầng slide `outline` do claude làm, `illustration` do mj
CLAUDE_UNIT = "S1,g,1,,outline,todo,claude,,,,\nS1,g,1,,illustration,todo,mj,,,,\n"


def reload(p):
    return Project.load(p.root)


def collect_one(p, uid, stage, ext="md"):
    actions.task(p, uid, stage)
    f = p.root / "assets" / uid / f"{uid}_{stage}_x_t1.{ext}"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"1")
    actions.collect(reload(p), uid, stage)
    return reload(p)


# ---------------------------------------------------------------- cổng 1

def test_worker_cannot_pick_or_approve_own_work(proj):
    p = collect_one(proj(CLAUDE_UNIT, pack="slides"), "S1", "outline")
    with pytest.raises(actions.ActionError, match="Owner") as e:
        actions.pick(p, "S1", "outline", 1, "claude")
    assert "S1:outline" in str(e.value)
    actions.pick(reload(p), "S1", "outline", 1, "owner")
    actions.qa_verdict(reload(p), "S1", "outline", True, "", "owner")
    with pytest.raises(actions.ActionError, match="tự chọn/duyệt"):
        actions.approve(reload(p), "S1", "outline", "claude")
    actions.approve(reload(p), "S1", "outline", "owner")
    assert reload(p).row("S1", "outline")["status"] == "approved"


def test_worker_check_is_per_unit_stage(proj):
    p = proj("S1,g,1,,outline,approved,claude,,1,x.md,\nS1,g,1,,illustration,todo,mj,,,,\n", pack="slides")
    p = collect_one(p, "S1", "illustration", "png")
    actions.pick(p, "S1", "illustration", 1, "claude")  # tầng mj, claude không làm bài đó
    actions.qa_verdict(reload(p), "S1", "illustration", True, "", "claude")
    actions.approve(reload(p), "S1", "illustration", "claude")  # illustration không thuộc G2
    assert reload(p).row("S1", "illustration")["status"] == "approved"


def test_ingest_rows_count_as_making(proj):
    p = proj(CLAUDE_UNIT, pack="slides")
    actions.task(p, "S1", "outline")
    from aiprod.core import log
    log.write(p.root, "S1", "outline", "claude", "ingest", "assets/S1/x.md", "ok")
    assert actions.made_by(reload(p), "S1", "outline") == {"claude"}


# ---------------------------------------------------------------- cổng 2

def run(p, *args):
    from aiprod.cli import main
    return main(["-C", str(p.root), *args])


def test_cli_owner_approve_requires_quote(proj, capsys):
    p = collect_one(proj(CLAUDE_UNIT, pack="slides"), "S1", "outline")
    assert run(p, "approve", "S1", "outline", "--pick", "1") == 2  # --by mặc định là owner
    assert "--quote" in capsys.readouterr().err
    assert run(p, "approve", "S1", "outline", "--pick", "1", "--by", "owner", "--quote", "  ") == 2
    assert reload(p).row("S1", "outline")["status"] == "candidates"  # chưa đổi gì
    assert run(p, "approve", "S1", "outline", "--pick", "1", "--quote", "ảnh #1 ok") == 0
    actions.qa_verdict(reload(p), "S1", "outline", True, "", "owner")
    assert run(p, "approve", "S1", "outline") == 2
    assert run(p, "approve", "S1", "outline", "--quote", "outline ok thì duyệt") == 0
    notes = [r["note"] for r in log.read(p.root) if r["action"] in ("pick", "approve")]
    assert all('quote: "' in n for n in notes) and 'quote: "outline ok thì duyệt"' in notes[-1]


def test_cli_agent_approve_needs_no_quote(proj):
    p = proj("A1,g,1,,image,approved,mj,,1,x.png,\nA1,g,1,,video,todo,grok,,,,\n")
    p = collect_one(p, "A1", "video", "mp4")
    actions.pick(p, "A1", "video", 1, "claude")
    actions.qa_verdict(reload(p), "A1", "video", True, "", "claude")
    assert run(p, "approve", "A1", "video", "--by", "claude") == 0


# ---------------------------------------------------------------- cổng 3

def test_set_force_is_logged_and_shown_in_status(proj):
    from aiprod.core.status import status_table
    p = proj(CLAUDE_UNIT, pack="slides")
    assert "set --force" not in status_table(p)
    actions.set_state(p, "S1", "outline", "spec_ready", "owner", force=False)  # todo → spec_ready hợp lệ
    assert "set --force" not in status_table(reload(p))
    actions.set_state(reload(p), "S1", "outline", "approved", "owner", force=True)
    row = [r for r in log.read(p.root) if r["action"] == "set:force"]
    assert len(row) == 1 and row[0]["result"] == "spec_ready→approved" and "by owner force" in row[0]["note"]
    out = status_table(reload(p))
    assert "`set --force` đã dùng 1 lần" in out and "S1:outline spec_ready→approved" in out


# ---------------------------------------------------------------- cổng 4

def fail_once(p, uid="A1", stage="image"):
    """Một vòng: có ứng viên, chọn, qa_fail, quay về spec_ready."""
    p = collect_one(p, uid, stage, "png")
    actions.pick(p, uid, stage, 1, "owner")
    actions.qa_verdict(reload(p), uid, stage, False, "lỗi", "owner")
    return reload(p)


def test_third_qa_fail_locks_attempts_until_human_note(proj):
    p = proj("A1,g,1,,image,todo,mj,,,,\n")
    for _ in range(2):
        p = fail_once(p)
        assert actions.qa_fail_count(p, "A1", "image") in (1, 2) and not actions.lock_reason(p, "A1", "image")
        p.root.joinpath("assets/A1/A1_image_x_t1.png").unlink()
        # task quay về spec_ready, ứng viên cũ xoá để vòng sau nhận file mới
    p = fail_once(p)
    assert actions.qa_fail_count(p, "A1", "image") == 3
    for fn in (lambda: actions.task(p, "A1", "image"), lambda: actions.task(p, "A1", "image", force=True),
               lambda: actions.submit(p, "A1", "image"), lambda: actions.collect(p, "A1", "image")):
        with pytest.raises(actions.ActionError, match="qa_fail 3 lần"):
            fn()
    actions.pick(p, "A1", "image", 1, "owner")  # approve --pick không bị khoá
    with pytest.raises(actions.ActionError, match="chỉ người"):
        actions.add_note(reload(p), "A1", "image", "đổi nguồn", "claude")
    assert actions.lock_reason(reload(p), "A1", "image")
    actions.add_note(reload(p), "A1", "image", "ảnh gốc sai bố cục, sửa nguồn", "owner")
    assert not actions.lock_reason(reload(p), "A1", "image") and actions.qa_fail_count(reload(p), "A1", "image") == 0
    actions.task(reload(p), "A1", "image")


def test_lock_is_per_unit_stage(proj):
    p = proj("A1,g,1,,image,todo,mj,,,,\nB2,g,2,,image,todo,mj,,,,\n")
    for _ in range(3):
        log.write(p.root, "A1", "image", "mj", "qa", "", "qa_fail")
    assert actions.lock_reason(p, "A1", "image") and not actions.lock_reason(p, "B2", "image")
    actions.task(p, "B2", "image")


def test_ingest_skips_locked_unit_with_warning(proj, tmp_path):
    from aiprod.core.ingest import ingest
    p = proj("A1,g,1,,image,todo,mj,,,,\nB2,g,2,,image,todo,mj,,,,\n")
    for _ in range(3):
        log.write(p.root, "A1", "image", "mj", "qa:auto", "", "qa_fail")
    src = tmp_path / "dl"
    src.mkdir()
    (src / "A1_image_a_t1.png").write_bytes(b"1")
    (src / "B2_image_a_t1.png").write_bytes(b"1")
    res = ingest(p, [src])
    assert [m["id"] for m in res["moved"]] == ["B2"]
    assert len(res["skipped"]) == 1 and "qa_fail 3 lần" in res["skipped"][0][1]
    assert (src / "A1_image_a_t1.png").exists()


def test_note_cli_and_approve_resets_count(proj, capsys):
    p = proj("A1,g,1,,image,todo,mj,,,,\n")
    for _ in range(3):
        log.write(p.root, "A1", "image", "mj", "qa", "", "qa_fail")
    assert run(p, "note", "A1", "image", "x", "--by", "claude") == 2
    assert run(p, "note", "A1", "image", "đổi nguồn") == 0
    assert not actions.lock_reason(p, "A1", "image")
    for _ in range(3):
        log.write(p.root, "A1", "image", "mj", "qa", "", "qa_fail")
    log.write(p.root, "A1", "image", "mj", "approve", "", "approved")
    assert actions.qa_fail_count(p, "A1", "image") == 0


# ---------------------------------------------------------------- cổng 5

def test_task_card_has_four_contract_sections(proj):
    p = proj("A1,g,1,,image,todo,mj,,,,\n")
    p.save_spec("A1", {"content": "Girl"})
    text = actions.task(p, "A1", "image")["path"].read_text(encoding="utf-8")
    for head in ("Đầu ra: assets/A1/A1_image_<tag>_t<n>.png", "Ràng buộc:", "Ngoài phạm vi: Không đổi bố cục", "Xong khi:"):
        assert head in text


def test_out_of_scope_from_spec_overrides_pack_default(proj):
    p = proj("A1,g,1,,image,todo,mj,,,,\n")
    p.save_spec("A1", {"content": "Girl", "out_of_scope": ["đổi màu tóc", "thêm chữ"]})
    text = actions.task(p, "A1", "image")["path"].read_text(encoding="utf-8")
    assert "Ngoài phạm vi: đổi màu tóc; thêm chữ" in text and "Không đổi bố cục" not in text


def test_plan_warns_but_does_not_fail_when_contract_data_missing(proj, capsys):
    p = proj("A1,g,1,,image,todo,mj,,,,\n")
    assert not p.rules()  # dự án mới chưa có `## Luật cứng`
    assert run(p, "plan") == 0
    out = capsys.readouterr().out
    assert "Plan OK" in out and "Cảnh báo (2), không chặn" in out and "ràng buộc" in out


def test_contract_warnings_name_the_missing_item(proj):
    from aiprod.core.tasks import contract_warnings
    p = proj("A1,g,1,,image,todo,mj,,,,\n")
    p.meta["stages"] = ["image", "custom"]
    p.meta["workers"]["custom"] = "mj"
    image, custom = [w for w in contract_warnings(p)]
    assert image.startswith("tầng image") and "sản phẩm giao" not in image and "ngoài phạm vi" not in image
    assert custom.startswith("tầng custom")
    for item in ("sản phẩm giao", "ngoài phạm vi", "tiêu chí nghiệm thu"):
        assert item in custom
