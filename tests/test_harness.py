"""Cổng cơ học của HARNESS.md."""
import pytest

from aiprod.core import actions
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
