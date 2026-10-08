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
