"""Bảng markdown để dán vào chat."""
from __future__ import annotations

from collections import Counter

from . import log, states
from .project import Project


def _c(v) -> str:
    return str(v or "").replace("|", "/").replace("\n", " ")


def status_table(p: Project) -> str:
    stages = p.stages
    rows = ["| Unit | Nhóm | " + " | ".join(stages) + " | Ghi chú |",
            "|---|---|" + "---|" * len(stages) + "---|"]
    counts: Counter = Counter()
    for uid in p.unit_ids():
        by_stage = {r["stage"]: r for r in p.unit_rows(uid)}
        cells, notes, group = [], [], ""
        for st in stages:
            r = by_stage.get(st)
            if not r:
                cells.append("—")
                continue
            counts[r["status"]] += 1
            group = group or r["group"]
            cells.append(r["status"] + (f" (#{r['pick']})" if r["pick"] else ""))
            if r["note"]:
                n = r["note"] if len(r["note"]) <= 60 else r["note"][:57] + "…"
                notes.append(f"{st}: {n}")
        rows.append(f"| {uid} | {_c(group)} | " + " | ".join(cells) + f" | {_c('; '.join(notes))} |")
    gates = ", ".join(f"{g}: {p.gates.get(g, {}).get('status', '—')}" for g in ("G1", "G3"))
    summary = ", ".join(f"{s} {counts[s]}" for s in states.STATES if counts[s])
    out = "\n".join(rows) + f"\n\nCổng — {gates}. Tầng: {summary or 'chưa có đơn vị'}."
    forced = [r for r in log.read(p.root) if r["action"] == "set:force"]
    if forced:
        out += f"\n\n⚠ `set --force` đã dùng {len(forced)} lần (bỏ qua state machine):"
        out += "".join(f"\n- {r['time']} {r['unit']}:{r['stage']} {r['result']} ({r['note']})" for r in forced)
    return out


def next_table(p: Project, show_blocked: bool = False) -> str:
    ready, blocked = p.next_actions()
    out = ["## Làm được ngay", ""]
    out += [f"- {u['id']}:{u['stage']} ({u['status']}, {u['worker'] or (p.meta.get('workers') or {}).get(u['stage'], '?')}) → {u['action']}"
            for u in ready] or ["- (không có)"]
    if p.assemble_ready():
        out.append("- Mọi đơn vị đã approved → aiprod assemble, rồi cổng G3")
    if show_blocked and blocked:
        out += ["", "## Đang chờ", ""]
        out += [f"- {u['id']}:{u['stage']} ({u['status']}): " + "; ".join(u["blockers"]) for u in blocked]
    elif blocked:
        out += ["", f"({len(blocked)} việc đang chờ phụ thuộc/cổng — thêm --all để xem)"]
    return "\n".join(out)
