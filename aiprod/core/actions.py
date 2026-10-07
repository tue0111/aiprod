"""Các thao tác đổi trạng thái: task, submit, collect, qa (tay), approve, gate, set.

Mọi thao tác đều ghi log.csv và lưu units.csv. Luật cổng:
- Không submit khi đơn vị còn bị chặn (G1, tầng trước, phụ thuộc).
- Duyệt tầng thuộc G2 chỉ người duyệt được, trừ khi PROJECT.md đặt `gates.G2.delegated: true`.
"""
from __future__ import annotations

from . import log, states
from .project import Project, ProjectError
from .tasks import write_task

HUMAN = {"owner", "human", "nguoi", "người"}


class ActionError(ProjectError):
    pass


def is_human(p: Project, by: str) -> bool:
    return by.lower() in HUMAN or by == str(p.meta.get("owner", "")) and by != ""


def task(p: Project, uid: str, stage: str, force: bool = False) -> dict:
    row = p.row(uid, stage)
    blockers = p.blockers(row)
    if blockers and not force:
        raise ActionError(f"{uid}:{stage} chưa viết thẻ được: " + "; ".join(blockers))
    path, written, missing = write_task(p, uid, stage, force=force)
    row["spec_file"] = str(path.relative_to(p.root)).replace("\\", "/")
    old = row["status"]
    if old in ("todo", "qa_fail"):
        p.set_status(row, "spec_ready")
    p.save_units()
    log.write(p.root, uid, stage, p.worker_of(row), "task", row["spec_file"],
              "ok" if not missing else "thiếu dữ liệu", ", ".join(missing))
    return {"path": path, "written": written, "missing": missing, "status": (old, row["status"])}


def submit(p: Project, uid: str, stage: str) -> dict:
    from ..adapters import adapter_for

    row = p.row(uid, stage)
    blockers = p.blockers(row)
    if blockers:
        raise ActionError(f"{uid}:{stage} chưa được làm: " + "; ".join(blockers))
    if row["status"] == "todo":
        task(p, uid, stage)
        row = p.row(uid, stage)
    if row["status"] != "spec_ready":
        raise ActionError(f"{uid}:{stage} đang {row['status']}, chỉ submit được khi spec_ready")
    path = p.root / row["spec_file"]
    if not path.exists():
        path = task(p, uid, stage)["path"]
    ad = adapter_for(p, p.worker_of(row))
    res = ad.submit(row, path)
    if res.ok:
        p.set_status(row, "generating")
        p.save_units()
    log.write(p.root, uid, stage, p.worker_of(row), f"submit:{ad.name}", res.ref, "ok" if res.ok else "lỗi",
              "" if res.ok else res.message)
    return {"adapter": ad.name, "result": res}


def collect(p: Project, uid: str, stage: str) -> dict:
    from ..adapters import adapter_for

    row = p.row(uid, stage)
    ad = adapter_for(p, p.worker_of(row))
    res = ad.collect(row)
    row = p.row(uid, stage) if not res.files else _reload_row(p, uid, stage)
    if res.failed and row["status"] == "generating":
        p.set_status(row, "spec_ready")
    elif res.files and row["status"] in ("spec_ready", "generating"):
        p.set_status(row, "candidates")
    p.save_units()
    rel = [str(f.relative_to(p.root)).replace("\\", "/") if f.is_relative_to(p.root) else str(f) for f in res.files]
    log.write(p.root, uid, stage, p.worker_of(row), f"collect:{ad.name}", ";".join(rel),
              "lỗi" if res.failed else ("ok" if res.files else "chưa có"), res.message)
    return {"adapter": ad.name, "result": res, "status": row["status"]}


def _reload_row(p: Project, uid: str, stage: str) -> dict:
    """Ingest có thể đã lưu units.csv: nạp lại để không ghi đè."""
    fresh = Project.load(p.root)
    p.units = fresh.units
    return p.row(uid, stage)


def candidates(p: Project, uid: str, stage: str) -> list[str]:
    from ..adapters.manual import candidate_files

    return candidate_files(p, p.row(uid, stage))


def pick(p: Project, uid: str, stage: str, n: int, by: str) -> dict:
    row = p.row(uid, stage)
    if row["status"] not in ("candidates", "qa_fail", "picked"):
        raise ActionError(f"{uid}:{stage} đang {row['status']}, chưa có ứng viên để chọn")
    files = candidates(p, uid, stage)
    if not 1 <= n <= len(files):
        raise ActionError(f"{uid}:{stage} có {len(files)} ứng viên, không có số {n}"
                          + ("".join(f"\n  {i}. {f}" for i, f in enumerate(files, 1))))
    row["pick"], row["output"] = str(n), files[n - 1]
    if row["status"] != "picked":
        p.set_status(row, "picked")
    p.save_units()
    log.write(p.root, uid, stage, p.worker_of(row), "pick", row["output"], f"#{n}", f"by {by}")
    return {"output": row["output"]}


def qa_verdict(p: Project, uid: str, stage: str, passed: bool, note: str, by: str) -> dict:
    row = p.row(uid, stage)
    if row["status"] not in ("picked", "qa_pass", "qa_fail"):
        raise ActionError(f"{uid}:{stage} đang {row['status']}; QA chạy sau khi đã chọn (picked)")
    new = "qa_pass" if passed else "qa_fail"
    if row["status"] != new:
        p.set_status(row, new, force=row["status"] in ("qa_pass", "qa_fail"))
    if note:
        row["note"] = note
    p.save_units()
    log.write(p.root, uid, stage, p.worker_of(row), "qa", row["output"], new, f"{note} (by {by})".strip())
    return {"status": new}


def approve(p: Project, uid: str, stage: str, by: str, skip_qa: bool = False, note: str = "") -> dict:
    row = p.row(uid, stage)
    if p.is_g2_stage(stage) and not is_human(p, by) and not p.g2_delegated():
        raise ActionError(f"{uid}:{stage} thuộc cổng G2: người phải duyệt (hoặc đặt gates.G2.delegated: true "
                          "khi người ủy quyền \"chọn giúp đi\")")
    if row["status"] == "qa_pass":
        p.set_status(row, "approved")
    elif skip_qa and row["status"] == "picked":
        if not is_human(p, by):
            raise ActionError("chỉ người được bỏ qua QA")
        p.set_status(row, "approved", force=True)
        note = (note + " ").strip() + "[bỏ qua QA]"
    else:
        raise ActionError(f"{uid}:{stage} đang {row['status']}; cần qa_pass trước khi duyệt "
                          f"(aiprod qa {uid} {stage}), hoặc --skip-qa nếu người duyệt thẳng")
    if note:
        row["note"] = note
    p.save_units()
    log.write(p.root, uid, stage, p.worker_of(row), "approve", row["output"], "approved",
              f"by {by}{' (G2)' if p.is_g2_stage(stage) else ''} {note}".strip())
    return {"status": "approved"}


def gate(p: Project, name: str, passed: bool, by: str) -> dict:
    if name not in ("G1", "G3"):
        raise ActionError("chỉ đặt G1 hoặc G3 bằng lệnh này; G2 duyệt theo từng đơn vị bằng aiprod approve")
    if not is_human(p, by):
        raise ActionError(f"cổng {name} chỉ người duyệt")
    if name == "G3" and passed and not p.assemble_ready():
        raise ActionError("chưa thể qua G3: còn đơn vị chưa approved")
    status = "passed" if passed else "pending"
    p.set_gate(name, status, by, log.now())
    log.write(p.root, action=f"gate:{name}", result=status, note=f"by {by}")
    return {"gate": name, "status": status}


def set_state(p: Project, uid: str, stage: str, new: str, by: str, force: bool) -> dict:
    row = p.row(uid, stage)
    old = p.set_status(row, new, force=force)
    p.save_units()
    log.write(p.root, uid, stage, p.worker_of(row), "set", "", f"{old}→{new}", f"by {by}{' force' if force else ''}")
    return {"old": old, "new": new}


__all__ = ["ActionError", "task", "submit", "collect", "pick", "qa_verdict", "approve", "gate", "set_state",
           "candidates", "states"]
