from pathlib import Path

import pytest

from aiprod.core.project import Project
from aiprod.core.scaffold import new_project

HEADER = "id,group,order,depends_on,stage,status,worker,spec_file,pick,output,note\n"


def make_project(root: Path, units: str, pack: str = "video", g1: bool = True, meta: dict | None = None) -> Project:
    new_project(root, pack, "Test")
    (root / "units.csv").write_text(HEADER + units, encoding="utf-8")
    p = Project.load(root)
    if g1:
        p.meta["gates"]["G1"] = {"status": "passed", "by": "owner", "at": ""}
    p.meta.update(meta or {})
    p.save_meta()
    return Project.load(root)


@pytest.fixture
def proj(tmp_path):
    def _make(units: str, **kw) -> Project:
        return make_project(tmp_path / "proj", units, **kw)

    return _make
