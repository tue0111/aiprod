"""Bài học vào thẻ năng lực: mọi lỗi mới phải thành một dòng trong tools/<tool>.md (Phần 2, bước 10)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from .project import Project
from .scaffold import tool_card_text

HEADERS = {"Luật dùng": "Luật dùng:", "Lỗi hay gặp": "Lỗi hay gặp → cách xử lý:"}


def add_lesson(p: Project, tool: str, text: str, section: str = "Luật dùng") -> Path:
    if not tool or not text:
        raise ValueError('cần tên tool và nội dung: aiprod lessons add <tool> "<luật>"')
    path = p.root / "tools" / f"{tool}.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tool_card_text(tool), encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    head = HEADERS[section]
    entry = f"- {text.strip()} ({date.today().isoformat()})"
    if entry.split(" (")[0] in (l.split(" (")[0] for l in lines):
        return path  # đã có, không ghi trùng
    idx = next((i for i, l in enumerate(lines) if l.strip().startswith(head)), None)
    if idx is None:
        lines += ["", head, entry]
    else:
        j = idx + 1
        while j < len(lines) and lines[j].startswith("- "):
            j += 1
        # bỏ dòng mẫu "- …" của template khi ghi bài học đầu tiên
        if j == idx + 2 and lines[idx + 1].strip() in ("- …", "-"):
            lines[idx + 1] = entry
        else:
            lines.insert(j, entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    from . import log

    log.write(p.root, worker=tool, action="lesson", file=str(path.relative_to(p.root)), result=section, note=text)
    return path


def list_lessons(p: Project, tool: str | None = None) -> str:
    d = p.root / "tools"
    files = [d / f"{tool}.md"] if tool else sorted(d.glob("*.md"))
    out = []
    for f in files:
        if not f.exists():
            continue
        out.append(f"## {f.stem}")
        cur = None
        for l in f.read_text(encoding="utf-8").splitlines():
            for name, head in HEADERS.items():
                if l.strip().startswith(head):
                    cur = name
            if cur and l.startswith("- ") and l.strip() != "- …":
                out.append(f"[{cur}] {l[2:]}")
    return "\n".join(out) or "chưa có bài học"
