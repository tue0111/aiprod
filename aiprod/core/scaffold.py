"""`aiprod new`: tạo dự án từ template. Không ghi đè file có sẵn."""
from __future__ import annotations

import json
from pathlib import Path

from ..packs import get_pack

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
DIRS = ["tasks", "tools", "qa", "specs", "templates", "assets", "queue/inbox", "queue/outbox", "renders"]


def new_project(root: str | Path, pack: str, name: str | None = None) -> dict:
    root = Path(root)
    p = get_pack(pack)
    name = name or root.name
    created, skipped = [], []

    def put(rel: str, text: str) -> None:
        path = root / rel
        if path.exists():
            skipped.append(path)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        created.append(path)

    fmt = {
        "name": name,
        "pack": pack,
        "unit": p["unit"],
        "stages": json.dumps(p["stages"]),
        "workers": json.dumps(p["workers"]),
        "g2_stages": json.dumps(p["g2_stages"]),
        "format": p["format"],
        "stages_arrow": " → ".join(p["stages"]),
    }
    put("PROJECT.md", (TEMPLATES / "PROJECT.md").read_text(encoding="utf-8").format(**fmt))
    for f in ["units.csv", "log.csv", "assemble.yaml"]:
        put(f, (TEMPLATES / f).read_text(encoding="utf-8"))
    for stage in p["stages"]:
        put(f"qa/{stage}.md", (TEMPLATES / "qa.md").read_text(encoding="utf-8"))
    for stage, tpl in p.get("templates", {}).items():
        put(f"templates/{stage}.txt", tpl + "\n")
    for tool in sorted(set(p["workers"].values())):
        put(f"tools/{tool}.md", (TEMPLATES / "tool.md").read_text(encoding="utf-8").replace("{tool}", tool))
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    return {"created": created, "skipped": skipped}
