"""Lệnh `aiprod ...`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.project import Project, ProjectError


def _p(a) -> Project:
    return Project.load(a.project)


# ---------- pha 1 ----------
def cmd_new(a) -> int:
    from .core.scaffold import new_project

    res = new_project(a.dir, a.pack, a.name)
    for p in res["created"]:
        print(f"tạo  {p.relative_to(Path(a.dir))}")
    print(f"Tạo {len(res['created'])} file, bỏ qua {len(res['skipped'])} file đã có (không ghi đè).")
    return 0


def cmd_plan(a) -> int:
    p = _p(a)
    errs = p.check_plan()
    if errs:
        print(f"Plan có {len(errs)} lỗi:")
        print("\n".join(f"- {e}" for e in errs))
        return 1
    print(f"Plan OK: {len(p.unit_ids())} đơn vị, {len(p.units)} dòng (đơn vị × tầng).")
    return 0


def cmd_next(a) -> int:
    from .core.status import next_table

    print(next_table(_p(a), a.all))
    return 0


def cmd_status(a) -> int:
    from .core.status import status_table

    print(status_table(_p(a)))
    return 0


# ---------- pha 2 ----------
def _targets(p: Project, a) -> list[tuple[str, str]]:
    if a.id == "all":
        return [(u["id"], u["stage"]) for u in p.units if (a.stage in (None, u["stage"]))]
    return [(a.id, a.stage or s) for s in ([a.stage] if a.stage else [r["stage"] for r in p.unit_rows(a.id)])]


def cmd_task(a) -> int:
    from .core import actions

    p = _p(a)
    explicit = a.id != "all" and a.stage
    for uid, stage in _targets(p, a):
        if not explicit and not a.force and p.blockers(p.row(uid, stage)):
            print(f"{uid}:{stage} bỏ qua: " + "; ".join(p.blockers(p.row(uid, stage))))
            continue
        why = actions.lock_reason(p, uid, stage)
        if why and not explicit:
            print(f"{uid}:{stage} bỏ qua: {why}")
            continue
        r = actions.task(p, uid, stage, force=a.force)
        rel = r["path"].relative_to(p.root)
        print(f"{uid}:{stage} → {rel} ({'ghi mới' if r['written'] else 'giữ thẻ đã có, --force để sinh lại'}; "
              f"{r['status'][0]}→{r['status'][1]})")
        if r["missing"]:
            print(f"  ⚠ thiếu: {', '.join(r['missing'])} (điền vào specs/{uid}.yaml)")
        if a.print:
            print(r["path"].read_text(encoding="utf-8"))
    return 0


def cmd_submit(a) -> int:
    from .core import actions

    r = actions.submit(_p(a), a.id, a.stage)
    print(r["result"].message)
    print(f"\n[{r['adapter']}] {a.id}:{a.stage} → generating")
    return 0 if r["result"].ok else 1


def cmd_collect(a) -> int:
    from .core import actions

    r = actions.collect(_p(a), a.id, a.stage)
    res = r["result"]
    print(f"[{r['adapter']}] {a.id}:{a.stage}: {res.message} → {r['status']}")
    for i, f in enumerate(actions.candidates(_p(a), a.id, a.stage), 1):
        print(f"  {i}. {f}")
    return 0


def cmd_approve(a) -> int:
    from .core import actions

    p = _p(a)
    if actions.is_human(p, a.by) and not (a.quote or "").strip():
        raise actions.ActionError(
            f"--by {a.by} là người duyệt: cần --quote \"<câu của người trong chat>\" "
            "(vd --quote \"ảnh #2 ok\"). Không có lời của người thì đừng chạy --by owner")
    if a.pick is not None:
        r = actions.pick(p, a.id, a.stage, a.pick, a.by, quote=a.quote or "")
        print(f"{a.id}:{a.stage} chọn #{a.pick}: {r['output']} → picked. Bước tiếp: aiprod qa {a.id} {a.stage}")
        if not a.skip_qa:
            return 0
        p = _p(a)
    actions.approve(p, a.id, a.stage, a.by, skip_qa=a.skip_qa, note=a.note or "",
                    quote=a.quote or "")
    print(f"{a.id}:{a.stage} → approved (by {a.by})")
    return 0


def cmd_qa(a) -> int:
    from .core import actions

    p = _p(a)
    if a.passed or a.failed:
        r = actions.qa_verdict(p, a.id, a.stage, a.passed, a.note or "", a.by)
        print(f"{a.id}:{a.stage} → {r['status']}")
        return 0
    from .core.qa import run_qa

    ids = [u["id"] for u in p.units if u["stage"] == a.stage] if a.id == "all" else [a.id]
    bad = 0
    for uid in ids:
        r = run_qa(p, uid, a.stage, apply=not a.dry_run)
        print(r["report"] + "\n")
        bad += not r["ok"]
    return 1 if bad else 0


def cmd_gate(a) -> int:
    from .core import actions

    r = actions.gate(_p(a), a.gate, not a.reopen, a.by)
    print(f"Cổng {r['gate']}: {r['status']}")
    return 0


def cmd_set(a) -> int:
    from .core import actions

    r = actions.set_state(_p(a), a.id, a.stage, a.status, a.by, a.force)
    print(f"{a.id}:{a.stage}: {r['old']} → {r['new']}")
    return 0


def cmd_note(a) -> int:
    from .core import actions

    actions.add_note(_p(a), a.id, a.stage, a.text, a.by)
    print(f"{a.id}:{a.stage}: đã ghi ghi chú của người; qa_fail tính lại từ 0")
    return 0


def cmd_log(a) -> int:
    from .core import log

    print(log.table(log.read(Path(a.project), a.unit, a.last)))
    return 0


# ---------- pha 3 ----------
def cmd_ingest(a) -> int:
    from .core.ingest import ingest

    p = _p(a)
    res = ingest(p, [Path(s) for s in a.src] if a.src else None, dry_run=a.dry_run, copy=a.copy)
    verb = "sẽ chuyển" if a.dry_run else ("chép" if a.copy else "chuyển")
    for m in res["moved"]:
        print(f"{verb} {m['src']} → {m['rel']}")
    for f, why in res["skipped"]:
        print(f"bỏ qua {f}: {why}")
    for uid, stage, old, new in res["status"]:
        print(f"{uid}:{stage}: {old} → {new}")
    print(f"{len(res['moved'])} file nhận, {len(res['skipped'])} bỏ qua.")
    return 0


def cmd_sheet(a) -> int:
    from .core.sheet import sheet_for

    out = sheet_for(_p(a), a.id, a.stage, Path(a.out) if a.out else None)
    print(out)
    return 0


def cmd_assemble(a) -> int:
    from .packs import pack_module

    p = _p(a)
    mod = pack_module(p.meta.get("pack", ""))
    if not mod or not hasattr(mod, "assemble"):
        print(f"pack {p.meta.get('pack')} chưa có assemble", file=sys.stderr)
        return 2
    if not p.assemble_ready() and not a.draft:
        print("Còn đơn vị chưa approved (hoặc G1 chưa qua). Dùng --draft để dựng thử.", file=sys.stderr)
        return 1
    out = mod.assemble(p, redo=set(filter(None, (a.redo or "").upper().split(","))), draft=a.draft)
    print(out)
    return 0


def cmd_deliver(a) -> int:
    from .packs import pack_module

    p = _p(a)
    mod = pack_module(p.meta.get("pack", ""))
    if not mod or not hasattr(mod, "deliver"):
        print(f"pack {p.meta.get('pack')} chưa có deliver", file=sys.stderr)
        return 2
    print(mod.deliver(p, max_mb=a.max_mb))
    return 0


def cmd_import(a) -> int:
    from .packs import pack_module

    mod = pack_module(a.pack)
    if not mod or not hasattr(mod, "import_project"):
        print(f"pack {a.pack} không có import", file=sys.stderr)
        return 2
    res = mod.import_project(Path(a.source), Path(a.dest), picks=Path(a.picks) if a.picks else None)
    print(res)
    return 0


# ---------- pha 4 ----------
def cmd_bot(a) -> int:
    from .adapters.bot_file import simulate

    print(simulate(_p(a), worker=a.worker, fail=set(filter(None, (a.fail or "").split(",")))))
    return 0


def cmd_sync(a) -> int:
    from .adapters.bot_file import sync

    lines = sync(_p(a))
    print("\n".join(lines) if lines else "không có việc nào đang chờ bot")
    return 0


# ---------- pha 5 ----------
def cmd_lessons(a) -> int:
    from .core.lessons import add_lesson, list_lessons

    p = _p(a)
    if a.action == "add":
        path = add_lesson(p, a.tool, a.text, section=a.section)
        print(f"đã ghi vào {path.relative_to(p.root)}")
    else:
        print(list_lessons(p, a.tool))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="aiprod", description="Bộ máy ráp nhiều AI làm một dự án")
    ap.add_argument("-C", "--project", default=".", help="thư mục dự án (mặc định: thư mục hiện tại)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, func, help_):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(func=func)
        return s

    def unit(s, stage_optional=False):
        s.add_argument("id")
        s.add_argument("stage", nargs="?" if stage_optional else None)

    s = add("new", cmd_new, "tạo dự án từ template")
    s.add_argument("dir")
    s.add_argument("--pack", default="video")
    s.add_argument("--name")

    add("plan", cmd_plan, "kiểm units.csv: mã trùng, phụ thuộc vòng, thiếu worker")
    s = add("next", cmd_next, "việc làm được ngay")
    s.add_argument("--all", action="store_true", help="hiện cả việc đang chờ và lý do")
    add("status", cmd_status, "bảng trạng thái (markdown)")

    s = add("task", cmd_task, "sinh thẻ việc tasks/<id>_<stage>.md (id=all cho mọi đơn vị)")
    unit(s, stage_optional=True)
    s.add_argument("--force", action="store_true", help="sinh lại, ghi đè thẻ đã có")
    s.add_argument("--print", action="store_true", help="in nội dung thẻ")

    s = add("submit", cmd_submit, "giao việc cho worker qua adapter")
    unit(s)
    s = add("collect", cmd_collect, "lấy kết quả từ worker qua adapter")
    unit(s)

    s = add("approve", cmd_approve, "chọn ứng viên (--pick n) hoặc duyệt (sau qa_pass)")
    unit(s)
    s.add_argument("--pick", type=int)
    s.add_argument("--by", default="owner", help="ai duyệt: owner (người) hoặc tên agent")
    s.add_argument("--skip-qa", action="store_true", help="người duyệt thẳng, không qua QA")
    s.add_argument("--note")
    s.add_argument("--quote", help="nguyên văn câu của người duyệt trong chat; bắt buộc khi --by là người")

    s = add("qa", cmd_qa, "QA tự động của pack, hoặc ghi kết luận tay (--pass/--fail)")
    unit(s)
    g = s.add_mutually_exclusive_group()
    g.add_argument("--pass", dest="passed", action="store_true")
    g.add_argument("--fail", dest="failed", action="store_true")
    s.add_argument("--note")
    s.add_argument("--by", default="owner")
    s.add_argument("--dry-run", action="store_true", help="chỉ báo cáo, không đổi trạng thái")

    s = add("gate", cmd_gate, "đặt cổng G1/G3 (người)")
    s.add_argument("gate", choices=["G1", "G3"])
    s.add_argument("--reopen", action="store_true", help="đưa cổng về pending")
    s.add_argument("--by", default="owner")

    s = add("set", cmd_set, "đổi trạng thái tay (sửa lỗi dữ liệu)")
    unit(s)
    s.add_argument("status")
    s.add_argument("--force", action="store_true")
    s.add_argument("--by", default="owner")

    s = add("note", cmd_note, "ghi chú của người cho một (đơn vị, tầng); mở khoá khi đã qa_fail 3 lần")
    unit(s)
    s.add_argument("text")
    s.add_argument("--by", default="owner")

    s = add("log", cmd_log, "xem log.csv")
    s.add_argument("--unit")
    s.add_argument("--last", type=int, default=20)

    s = add("ingest", cmd_ingest, "nhận file mới từ Downloads / queue/outbox, đặt tên, gắn vào đơn vị")
    s.add_argument("--from", dest="src", action="append", help="thư mục nguồn (lặp được)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--copy", action="store_true", help="chép thay vì chuyển")

    s = add("sheet", cmd_sheet, "contact sheet ứng viên của một đơn vị")
    unit(s)
    s.add_argument("--out")

    s = add("assemble", cmd_assemble, "ghép sản phẩm theo pack")
    s.add_argument("--redo", help="dựng lại các đơn vị, vd H01,E02")
    s.add_argument("--draft", action="store_true", help="dựng thử khi chưa duyệt hết")

    s = add("deliver", cmd_deliver, "nén và xuất file giao")
    s.add_argument("--max-mb", type=float, default=30)

    s = add("import", cmd_import, "nhập dự án có sẵn (vd timeline phim) thành dự án aiprod")
    s.add_argument("source")
    s.add_argument("dest")
    s.add_argument("--pack", default="video")
    s.add_argument("--picks", help="file YAML ghi clip/ảnh đã chọn cho từng đơn vị")

    s = add("bot", cmd_bot, "bot giả lập: xử lý queue/inbox, trả queue/outbox (để thử giao thức)")
    s.add_argument("--worker")
    s.add_argument("--fail", help="các việc giả lập lỗi, vd H01:video")

    add("sync", cmd_sync, "thu kết quả mọi việc đang generating của bot (adapter bot_file)")

    s = add("lessons", cmd_lessons, "bài học vào thẻ năng lực: lessons add <tool> \"<luật>\" | lessons list [tool]")
    s.add_argument("action", choices=["add", "list"])
    s.add_argument("tool", nargs="?")
    s.add_argument("text", nargs="?")
    s.add_argument("--section", default="Luật dùng", choices=["Luật dùng", "Lỗi hay gặp"])
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    a = build_parser().parse_args(argv)
    try:
        return a.func(a)
    except (ProjectError, KeyError, ValueError, FileNotFoundError) as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
