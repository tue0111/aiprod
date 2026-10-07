"""Chọn adapter cho worker.

PROJECT.md có thể khai báo `adapters: {grok: bot_file, mj: manual}`. Mặc định là `manual`.
Adapter `api_*` chỉ thêm khi tool có API chính thức.
"""
from __future__ import annotations

from ..core.project import Project
from .base import Adapter


def registry() -> dict[str, type[Adapter]]:
    from .manual import ManualAdapter

    reg: dict[str, type[Adapter]] = {"manual": ManualAdapter}
    try:
        from .bot_file import BotFileAdapter

        reg["bot_file"] = BotFileAdapter
    except ImportError:
        pass
    return reg


def adapter_for(p: Project, worker: str) -> Adapter:
    name = (p.meta.get("adapters") or {}).get(worker, "manual")
    reg = registry()
    if name not in reg:
        raise KeyError(f"adapter lạ {name!r} cho worker {worker}; có: {', '.join(reg)}")
    return reg[name](p)
