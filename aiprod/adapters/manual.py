"""Adapter `manual` (mức L0–L1): in thẻ việc để người hoặc agent có trình duyệt làm tay.

collect quét các chỗ worker hay để file (assets/<id>/, Downloads) tìm file đúng tên quy ước.
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, CollectResult, SubmitResult


class ManualAdapter(Adapter):
    name = "manual"
    level = "L1"

    def describe(self) -> str:
        return "In thẻ việc ra để người/agent làm tay theo runbook trong thẻ năng lực; nhận file theo tên quy ước."

    def submit(self, row: dict, task_path: Path) -> SubmitResult:
        text = task_path.read_text(encoding="utf-8")
        return SubmitResult(True, f"Giao tay cho {self.p.worker_of(row) or '?'} — thẻ việc: {task_path}\n\n{text}",
                            ref=str(task_path))

    def collect(self, row: dict) -> CollectResult:
        from ..core.ingest import ingest

        res = ingest(self.p, only=(row["id"], row["stage"]))
        files = [Path(m["dest"]) for m in res["moved"]]
        files += [Path(self.p.root, f) for f in candidate_files(self.p, row) if Path(self.p.root, f) not in files]
        return CollectResult(files=files, done=bool(files), message=f"{len(files)} file ứng viên")


def candidate_files(p, row: dict) -> list[str]:
    """Các file ứng viên đã nằm trong assets/<id>/ cho tầng này (đường dẫn tương đối, đã sắp xếp)."""
    d = p.root / "assets" / row["id"]
    if not d.is_dir():
        return []
    prefix = f"{row['id']}_{row['stage']}_"
    return sorted(str(f.relative_to(p.root)).replace("\\", "/") for f in d.iterdir()
                  if f.is_file() and f.name.startswith(prefix))
