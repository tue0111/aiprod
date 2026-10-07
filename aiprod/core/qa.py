"""QA tự động: kiểm kỹ thuật chung + QA riêng của pack.

QA máy chỉ bắt lỗi kỹ thuật (thiếu file, sai kích thước, viền đen, thời lượng). Lỗi phán
đoán (tay, mặt, vật xuất hiện) cần người/Orchestrator xem contact sheet rồi chạy
`aiprod qa <id> <stage> --pass|--fail`. Vì vậy:
- lỗi kỹ thuật → qa_fail
- kỹ thuật OK → giữ `picked`, báo bước xem tay
"""
from __future__ import annotations

import json
from pathlib import Path

from . import log
from .project import Project


def resolve(p: Project, rel: str) -> Path:
    f = Path(rel)
    return f if f.is_absolute() else p.root / f


def run_qa(p: Project, uid: str, stage: str, apply: bool = True) -> dict:
    from ..packs import pack_module

    row = p.row(uid, stage)
    checks: list[dict] = []
    out = row["output"]
    path = resolve(p, out) if out else None
    if not out:
        checks.append({"check": "có đầu ra", "ok": False, "detail": "chưa chọn ứng viên (aiprod approve --pick n)"})
    elif not path.exists():
        checks.append({"check": "có đầu ra", "ok": False, "detail": f"không thấy {out}"})
    else:
        checks.append({"check": "có đầu ra", "ok": True, "detail": out})
        mod = pack_module(p.meta.get("pack", ""))
        if mod and hasattr(mod, "qa"):
            checks += mod.qa(p, row, path, apply=apply)
    ok = all(c["ok"] for c in checks)
    sheet = next((c.get("sheet") for c in checks if c.get("sheet")), "")
    result = {"unit": uid, "stage": stage, "ok": ok, "checks": checks, "sheet": sheet}
    if apply:
        d = p.root / "qa" / "results"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{uid}_{stage}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if not ok and row["status"] in ("picked", "qa_pass"):
            p.set_status(row, "qa_fail", force=row["status"] == "qa_pass")
            p.save_units()
        log.write(p.root, uid, stage, p.worker_of(row), "qa:auto", out, "kỹ thuật OK" if ok else "qa_fail",
                  "; ".join(c["detail"] for c in checks if not c["ok"]))
    lines = [f"QA {uid}:{stage} — {'kỹ thuật OK' if ok else 'LỖI KỸ THUẬT'}"]
    lines += [f"- [{'x' if c['ok'] else ' '}] {c['check']}: {c['detail']}" for c in checks]
    if sheet:
        lines.append(f"Contact sheet: {sheet}")
    if ok:
        lines.append(f"Chưa kiểm (cần mắt người/Orchestrator): xem contact sheet theo qa/{stage}.md rồi "
                     f"`aiprod qa {uid} {stage} --pass` hoặc `--fail --note \"...\"`.")
    result["report"] = "\n".join(lines)
    return result
