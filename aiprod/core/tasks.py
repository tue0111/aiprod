"""Sinh thẻ việc `tasks/<id>_<stage>.md` từ template + dữ liệu đơn vị.

Thẻ việc phải đủ để một agent chưa từng thấy dự án vẫn làm được: nó chứa prompt
dán được ngay, đầu vào, luật cứng, thẻ năng lực worker, QA checklist, quy tắc tên
file trả về và lệnh báo xong.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..packs import get_pack
from .project import Project

PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def stage_ext(p: Project, stage: str) -> str:
    return (p.meta.get("ext") or {}).get(stage) or get_pack(p.meta.get("pack", "video")).get("ext", {}).get(stage, "bin")


def output_pattern(p: Project, row: dict) -> str:
    """Tên file worker phải trả về. <tag> tự do (vd mj job, P7), <n> là số lần thử."""
    return f"{row['id']}_{row['stage']}_<tag>_t<n>.{stage_ext(p, row['stage'])}"


def stage_template(p: Project, stage: str) -> str:
    f = p.root / "templates" / f"{stage}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    return get_pack(p.meta.get("pack", "video")).get("templates", {}).get(stage, "{prompt}")


def context(p: Project, row: dict) -> dict:
    """Biến dùng cho template. Thứ tự ưu tiên: spec của đơn vị > dòng units.csv > PROJECT.md."""
    meta = dict(p.meta)
    style = meta.get("style")
    ctx: dict = {}
    if isinstance(style, dict):  # style có thể là chuỗi hoặc {sentence, mj_suffix, sref, ...}
        ctx.update({k: v for k, v in style.items() if not isinstance(v, dict)})
        ctx["style"] = style.get("sentence", "")
        sref = (style.get("sref") or {})
        group_sref = sref.get(row["group"]) if isinstance(sref, dict) else None
        ctx["sref"] = f"--sref {group_sref}" if group_sref else ""
    else:
        ctx["style"] = style or ""
    chars = meta.get("characters")
    if isinstance(chars, dict):
        ctx["characters"] = "; ".join(f"{k}: {v}" for k, v in chars.items())
    for k, v in meta.items():
        if isinstance(v, (str, int, float)) and k not in ctx:
            ctx[k] = v
    ctx.update({k: v for k, v in row.items() if v})
    ctx["input"] = p.prev_output(row) or ctx.get("input", "")
    spec = p.spec(row["id"])
    ctx.update({k: v for k, v in spec.items() if not isinstance(v, dict)})
    ctx.update(spec.get(row["stage"]) or {})  # trường riêng cho tầng: specs/H01.yaml -> video: {motion: ...}
    return ctx


def render_prompt(template: str, ctx: dict) -> tuple[str, list[str]]:
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        v = ctx.get(m.group(1))
        if v in (None, ""):
            missing.append(m.group(1))
            return ""
        if isinstance(v, list):
            return ", ".join(map(str, v))
        return str(v)

    text = PLACEHOLDER.sub(sub, template)
    text = re.sub(r"\s+([.,])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()
    text = re.sub(r"(^|\s)[.,](?=\s|$)", r"\1", text).strip()
    text = re.sub(r"([.!?])\.+", r"\1", text)  # "câu.. " khi giá trị đã có dấu chấm
    return text, sorted(set(missing))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def build_task(p: Project, uid: str, stage: str) -> tuple[str, list[str]]:
    row = p.row(uid, stage)
    worker = p.worker_of(row)
    ctx = context(p, row)
    prompt = ctx.get("prompt") or render_prompt(stage_template(p, stage), ctx)[0]
    missing = [] if ctx.get("prompt") else render_prompt(stage_template(p, stage), ctx)[1]
    pack = get_pack(p.meta.get("pack", "video"))
    goal = ctx.get("goal") or ctx.get("content") or ctx.get("title") or row.get("note") or "(chưa ghi mục tiêu)"
    done_when = ctx.get("done_when") or pack.get("done_when", {}).get(stage, "Qua QA checklist bên dưới.")
    rules = p.rules()
    gate = "Có — người duyệt trước khi chạy tầng sau" if p.is_g2_stage(stage) else "Không"

    lines = [
        f"Unit: {uid} | Stage: {stage} | Worker: {worker or '?'} | Input: {ctx['input'] or '(không có)'}",
        f"Mục tiêu: {goal}",
        "Prompt / spec:",
        "```",
        prompt,
        "```",
        "Ràng buộc: " + ("; ".join(rules) if rules else "(xem PROJECT.md)"),
        f"Đầu ra: assets/{uid}/{output_pattern(p, row)} | Ghi log: log.csv",
        f"Xong khi: {done_when}",
        "",
        "## Cách nộp",
        f"1. Lưu file theo tên `{output_pattern(p, row)}` (vd `{uid}_{stage}_a_t1.{stage_ext(p, stage)}`), "
        "để trong `assets/<id>/`, Downloads hoặc `queue/outbox/`.",
        "2. Chạy `aiprod ingest` (hoặc `aiprod collect "
        f"{uid} {stage}`). Trạng thái chuyển sang `candidates`.",
        "3. Không tự duyệt. Người/Orchestrator chọn bằng "
        f"`aiprod approve {uid} {stage} --pick n`, chạy QA, rồi duyệt.",
        f"Cổng G2 ở tầng này: {gate}.",
    ]
    if missing:
        lines += ["", f"⚠ Template thiếu dữ liệu: {', '.join(missing)} — điền vào `specs/{uid}.yaml` rồi chạy lại `aiprod task`."]
    if row.get("note"):
        lines += ["", f"Ghi chú: {row['note']}"]
    tool = _read(p.root / "tools" / f"{worker}.md")
    if tool:
        lines += ["", f"## Thẻ năng lực: {worker}", "", tool]
    qa = _read(p.root / "qa" / f"{stage}.md")
    if qa:
        lines += ["", f"## QA checklist ({stage})", "", qa]
    return "\n".join(lines) + "\n", missing


def write_task(p: Project, uid: str, stage: str, force: bool = False) -> tuple[Path, bool, list[str]]:
    """Ghi thẻ việc. Không ghi đè thẻ đã sửa tay trừ khi force. Trả (đường dẫn, đã_ghi, thiếu)."""
    path = p.root / "tasks" / f"{uid}_{stage}.md"
    text, missing = build_task(p, uid, stage)
    written = False
    if force or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written = True
    return path, written, missing
