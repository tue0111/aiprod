"""Interface chung cho mọi worker adapter.

Adapter không tự quyết: submit giao thẻ việc, collect nhận file về. Chọn ứng viên,
QA và duyệt luôn do Orchestrator/người làm qua `aiprod approve`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core.project import Project


@dataclass
class SubmitResult:
    ok: bool
    message: str
    ref: str = ""  # mã việc phía worker (vd đường dẫn file inbox, job id)


@dataclass
class CollectResult:
    files: list[Path] = field(default_factory=list)
    done: bool = False  # worker báo đã xong (dù có thể 0 file)
    failed: bool = False
    message: str = ""


class Adapter:
    name = "base"
    level = "L0"

    def __init__(self, project: Project):
        self.p = project

    def describe(self) -> str:
        raise NotImplementedError

    def submit(self, row: dict, task_path: Path) -> SubmitResult:
        raise NotImplementedError

    def collect(self, row: dict) -> CollectResult:
        raise NotImplementedError
