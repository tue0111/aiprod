from pathlib import Path

import pytest

from aiprod.cli import main
from aiprod.core import states
from aiprod.core.project import Project, parse_deps
from aiprod.core.scaffold import new_project

HEADER = "id,group,order,depends_on,stage,status,worker,spec_file,pick,output,note\n"
SAMPLE = HEADER + """\
H01,hook,1,,image,approved,mj,,1,,
H01,hook,1,H01:image,video,qa_pass,grok,,,,
H02,hook,2,H01:image,image,todo,,,,,
H02,hook,2,H02:image,video,todo,,,,,
B01,montage,3,,image,candidates,,,,,
E01,ending,4,H02,image,spec_ready,,,,,
"""


def make(tmp_path: Path, units: str = SAMPLE, g1: str = "passed") -> Project:
    new_project(tmp_path, "video", "Demo")
    (tmp_path / "units.csv").write_text(units, encoding="utf-8")
    pm = tmp_path / "PROJECT.md"
    pm.write_text(pm.read_text(encoding="utf-8").replace("G1: {status: pending", f"G1: {{status: {g1}"),
                  encoding="utf-8")
    return Project.load(tmp_path)


def ready_keys(p: Project) -> set[str]:
    return {f"{u['id']}:{u['stage']}" for u in p.next_actions()[0]}


# ---------- states ----------

def test_transitions():
    assert states.transition("todo", "spec_ready") == "spec_ready"
    assert states.can_transition("qa_fail", "spec_ready")
    with pytest.raises(states.TransitionError):
        states.transition("todo", "approved")
    with pytest.raises(ValueError):
        states.check_state("lol")


def test_every_state_has_transitions_or_is_terminal():
    for s in states.STATES:
        assert s in states.TRANSITIONS
        assert s in states.NEXT_ACTION or s in states.DONE


# ---------- deps ----------

def test_parse_deps():
    assert parse_deps("H01:image; B02, C03") == [("H01", "image"), ("B02", None), ("C03", None)]
    assert parse_deps("") == []


# ---------- new ----------

def test_new_does_not_overwrite(tmp_path):
    first = new_project(tmp_path, "video")
    (tmp_path / "PROJECT.md").write_text("---\nname: x\n---\nsửa tay", encoding="utf-8")
    second = new_project(tmp_path, "video")
    assert first["created"] and not second["created"]
    assert (tmp_path / "PROJECT.md").read_text(encoding="utf-8").endswith("sửa tay")
    assert (tmp_path / "queue" / "inbox").is_dir()


def test_new_unknown_pack(tmp_path):
    with pytest.raises(KeyError):
        new_project(tmp_path, "opera")


@pytest.mark.parametrize("pack", ["video", "slides", "images"])
def test_new_each_pack_loads(tmp_path, pack):
    new_project(tmp_path, pack)
    p = Project.load(tmp_path)
    assert p.meta["pack"] == pack and p.stages
    assert p.check_plan() == []  # units.csv rỗng vẫn hợp lệ


# ---------- next ----------

def test_g1_blocks_everything(tmp_path):
    p = make(tmp_path, g1="pending")
    assert ready_keys(p) == set()


def test_next_respects_stages_and_deps(tmp_path):
    p = make(tmp_path)
    assert ready_keys(p) == {"H01:video", "H02:image", "B01:image"}
    blocked = {f"{u['id']}:{u['stage']}": u["blockers"] for u in p.next_actions()[1]}
    assert "H02:video" in blocked and len(blocked["H02:video"]) == 1  # không báo trùng lý do
    assert any("H02" in b for b in blocked["E01:image"])


def test_dependency_released_when_approved(tmp_path):
    units = SAMPLE.replace("H02,hook,2,H01:image,image,todo", "H02,hook,2,H01:image,image,approved") \
                  .replace("H02,hook,2,H02:image,video,todo", "H02,hook,2,H02:image,video,approved")
    assert "E01:image" in ready_keys(make(tmp_path, units))


def test_assemble_ready(tmp_path):
    units = HEADER + "A,g,1,,image,approved,,,,,\nA,g,1,,video,assembled,,,,,\n"
    assert make(tmp_path, units).assemble_ready()
    units = HEADER + "A,g,1,,image,approved,,,,,\nA,g,1,,video,qa_pass,,,,,\n"
    assert not make(tmp_path / "b", units).assemble_ready()


# ---------- plan ----------

def test_plan_ok(tmp_path):
    assert make(tmp_path).check_plan() == []


def test_plan_errors(tmp_path):
    bad = SAMPLE + """\
H01,hook,1,,image,todo,,,,,
X1,x,9,X2,image,todo,,,,,
X2,x,9,X1,image,lol,,,,,
X3,x,9,Z9,paint,todo,,,,,
X4,x,9,H01:sound,image,todo,,,,,
"""
    errs = "\n".join(make(tmp_path, bad).check_plan())
    for needle in ["mã trùng", "trạng thái lạ 'lol'", "tầng lạ 'paint'", "không tồn tại Z9",
                   "tầng không tồn tại H01:sound", "phụ thuộc vòng", "thiếu worker"]:
        assert needle in errs


def test_self_stage_dep_is_not_cycle(tmp_path):
    assert not any("vòng" in e for e in make(tmp_path).check_plan())


# ---------- cli ----------

def test_cli_smoke(tmp_path, capsys):
    make(tmp_path)
    assert main(["-C", str(tmp_path), "plan"]) == 0
    assert main(["-C", str(tmp_path), "next", "--all"]) == 0
    assert main(["-C", str(tmp_path), "status"]) == 0
    out = capsys.readouterr().out
    assert "Plan OK" in out and "Đang chờ" in out and "| H01 |" in out


def test_cli_not_a_project(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "status"]) == 2
    assert "PROJECT.md" in capsys.readouterr().err
