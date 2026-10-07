"""Lệnh `aiprod ...`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.project import Project, ProjectError


def cmd_new(a) -> int:
    from .core.scaffold import new_project

    res = new_project(a.dir, a.pack, a.name)
    for p in res["created"]:
        print(f"tạo  {p.relative_to(Path(a.dir))}")
    print(f"Tạo {len(res['created'])} file, bỏ qua {len(res['skipped'])} file đã có (không ghi đè).")
    return 0


def cmd_plan(a) -> int:
    p = Project.load(a.project)
    errs = p.check_plan()
    if errs:
        print(f"Plan có {len(errs)} lỗi:")
        print("\n".join(f"- {e}" for e in errs))
        return 1
    print(f"Plan OK: {len(p.unit_ids())} đơn vị, {len(p.units)} dòng (đơn vị × tầng).")
    return 0


def cmd_next(a) -> int:
    from .core.status import next_table

    print(next_table(Project.load(a.project), a.all))
    return 0


def cmd_status(a) -> int:
    from .core.status import status_table

    print(status_table(Project.load(a.project)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="aiprod", description="Bộ máy ráp nhiều AI làm một dự án")
    ap.add_argument("-C", "--project", default=".", help="thư mục dự án (mặc định: thư mục hiện tại)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="tạo dự án từ template")
    s.add_argument("dir")
    s.add_argument("--pack", default="video")
    s.add_argument("--name")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("plan", help="kiểm units.csv: mã trùng, phụ thuộc vòng, thiếu worker")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("next", help="việc làm được ngay")
    s.add_argument("--all", action="store_true", help="hiện cả việc đang chờ và lý do")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("status", help="bảng trạng thái (markdown)")
    s.set_defaults(func=cmd_status)
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
