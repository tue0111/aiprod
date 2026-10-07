"""Đọc PROJECT.md (frontmatter YAML) và units.csv; kiểm plan; tính việc làm được ngay."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import states

UNIT_FIELDS = ["id", "group", "order", "depends_on", "stage", "status", "worker",
               "spec_file", "pick", "output", "note"]


class ProjectError(Exception):
    pass


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ProjectError("PROJECT.md thiếu frontmatter YAML (mở đầu bằng ---)")
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")


def join_frontmatter(meta: dict, body: str) -> str:
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{fm}---\n\n{body}"


def parse_deps(raw: str) -> list[tuple[str, str | None]]:
    """'H01:image; B02' -> [('H01','image'), ('B02', None)]. None = tầng cuối của đơn vị đó."""
    out = []
    for part in (raw or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        uid, _, stage = part.partition(":")
        out.append((uid.strip(), stage.strip() or None))
    return out


@dataclass
class Project:
    root: Path
    meta: dict
    body: str
    units: list[dict] = field(default_factory=list)

    # ---------- nạp / lưu ----------
    @classmethod
    def load(cls, root: str | Path) -> "Project":
        root = Path(root)
        pm = root / "PROJECT.md"
        if not pm.exists():
            raise ProjectError(f"{pm} không tồn tại — đây chưa phải dự án aiprod")
        meta, body = split_frontmatter(pm.read_text(encoding="utf-8"))
        units = []
        uc = root / "units.csv"
        if uc.exists():
            with uc.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    units.append({k: (row.get(k) or "").strip() for k in UNIT_FIELDS})
        return cls(root=root, meta=meta, body=body, units=units)

    def save_units(self) -> None:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=UNIT_FIELDS, lineterminator="\n")
        w.writeheader()
        for u in self.units:
            w.writerow({k: u.get(k, "") for k in UNIT_FIELDS})
        (self.root / "units.csv").write_text(buf.getvalue(), encoding="utf-8")

    def save_meta(self) -> None:
        (self.root / "PROJECT.md").write_text(join_frontmatter(self.meta, self.body), encoding="utf-8")

    # ---------- ghi trạng thái ----------
    def set_status(self, row: dict, new: str, force: bool = False) -> str:
        """Đổi trạng thái theo state machine. force=True bỏ qua kiểm chuyển (vẫn kiểm tên)."""
        old = row["status"]
        if force:
            states.check_state(new)
        else:
            states.transition(old, new)
        row["status"] = new
        return old

    def worker_of(self, row: dict) -> str:
        return row.get("worker") or (self.meta.get("workers") or {}).get(row["stage"], "")

    def is_g2_stage(self, stage: str) -> bool:
        return stage in (self.gates.get("G2", {}).get("stages") or [])

    def g2_delegated(self) -> bool:
        return bool(self.gates.get("G2", {}).get("delegated"))

    def set_gate(self, gate: str, status: str, by: str, at: str) -> None:
        g = self.meta.setdefault("gates", {}).setdefault(gate, {})
        g.update(status=status, by=by, at=at)
        self.save_meta()

    # ---------- spec của đơn vị ----------
    def spec_path(self, uid: str) -> Path:
        return self.root / "specs" / f"{uid}.yaml"

    def spec(self, uid: str) -> dict:
        p = self.spec_path(uid)
        if not p.exists():
            return {}
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    def save_spec(self, uid: str, data: dict) -> None:
        p = self.spec_path(uid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")

    def body_section(self, title: str) -> str:
        """Nội dung một mục `## <title>` trong phần thân PROJECT.md."""
        out, on = [], False
        for line in self.body.splitlines():
            if line.startswith("## "):
                on = line[3:].strip().lower() == title.lower()
                continue
            if on:
                out.append(line)
        return "\n".join(out).strip()

    def rules(self) -> list[str]:
        sec = self.body_section("Luật cứng")
        rules = [l[2:].strip() for l in sec.splitlines() if l.startswith("- ") and l[2:].strip() not in ("", "…")]
        return rules + [str(r) for r in (self.meta.get("rules") or [])]

    def prev_output(self, row: dict) -> str:
        """Đầu ra đã duyệt của tầng ngay trước (đầu vào cho tầng này)."""
        rows = self.unit_rows(row["id"])
        idx = self._stage_idx(row["stage"])
        prev = [r for r in rows if self._stage_idx(r["stage"]) < idx]
        return prev[-1]["output"] if prev and states.is_done(prev[-1]["status"]) else ""

    # ---------- truy vấn ----------
    @property
    def stages(self) -> list[str]:
        return list(self.meta.get("stages") or [])

    @property
    def gates(self) -> dict:
        return self.meta.get("gates") or {}

    def gate_passed(self, gate: str) -> bool:
        return str(self.gates.get(gate, {}).get("status", "pending")) == "passed"

    def row(self, uid: str, stage: str) -> dict:
        for u in self.units:
            if u["id"] == uid and u["stage"] == stage:
                return u
        raise ProjectError(f"không có đơn vị {uid}:{stage}")

    def unit_rows(self, uid: str) -> list[dict]:
        return sorted((u for u in self.units if u["id"] == uid), key=lambda u: self._stage_idx(u["stage"]))

    def _stage_idx(self, stage: str) -> int:
        return self.stages.index(stage) if stage in self.stages else len(self.stages)

    def dep_done(self, uid: str, stage: str | None) -> bool:
        rows = self.unit_rows(uid)
        if not rows:
            return False
        target = rows[-1] if stage is None else next((r for r in rows if r["stage"] == stage), None)
        return target is not None and states.is_done(target["status"])

    def blockers(self, u: dict) -> list[str]:
        """Lý do (đơn vị, tầng) chưa làm được. Rỗng = làm được ngay."""
        why = []
        if not self.gate_passed("G1"):
            why.append("cổng G1 (brief + plan) chưa duyệt")
        idx = self._stage_idx(u["stage"])
        for prev in self.unit_rows(u["id"]):
            if self._stage_idx(prev["stage"]) < idx and not states.is_done(prev["status"]):
                why.append(f"tầng trước {u['id']}:{prev['stage']} chưa approved ({prev['status']})")
        for dep_id, dep_stage in parse_deps(u["depends_on"]):
            if dep_id == u["id"] and dep_stage and self._stage_idx(dep_stage) < idx:
                continue  # đã tính ở luật "tầng trước"
            if not self.dep_done(dep_id, dep_stage):
                why.append(f"phụ thuộc {dep_id}{':' + dep_stage if dep_stage else ''} chưa xong")
        return why

    def next_actions(self) -> tuple[list[dict], list[dict]]:
        ready, blocked = [], []
        for u in sorted(self.units, key=lambda u: (_int(u["order"]), u["id"], self._stage_idx(u["stage"]))):
            if states.is_done(u["status"]):
                continue
            b = self.blockers(u)
            item = {**u, "blockers": b,
                    "action": states.NEXT_ACTION[u["status"]].format(id=u["id"], stage=u["stage"])}
            (blocked if b else ready).append(item)
        return ready, blocked

    def assemble_ready(self) -> bool:
        if not self.units or not self.gate_passed("G1"):
            return False
        return all(states.is_done(r[-1]["status"]) for r in (self.unit_rows(i) for i in self.unit_ids()))

    def unit_ids(self) -> list[str]:
        seen: dict[str, None] = {}
        for u in self.units:
            seen.setdefault(u["id"], None)
        return list(seen)

    # ---------- kiểm plan ----------
    def check_plan(self) -> list[str]:
        errs = []
        if not self.stages:
            errs.append("PROJECT.md thiếu `stages`")
        workers = self.meta.get("workers") or {}
        seen = set()
        ids = set(self.unit_ids())
        for n, u in enumerate(self.units, start=2):
            key = (u["id"], u["stage"])
            where = f"units.csv dòng {n} ({u['id']}:{u['stage']})"
            if not u["id"]:
                errs.append(f"units.csv dòng {n}: thiếu id")
            if key in seen:
                errs.append(f"{where}: mã trùng")
            seen.add(key)
            if self.stages and u["stage"] not in self.stages:
                errs.append(f"{where}: tầng lạ {u['stage']!r} (có: {', '.join(self.stages)})")
            if u["status"] not in states.STATES:
                errs.append(f"{where}: trạng thái lạ {u['status']!r}")
            if not (u["worker"] or workers.get(u["stage"])):
                errs.append(f"{where}: thiếu worker (cột worker hoặc workers.{u['stage']} trong PROJECT.md)")
            for dep_id, dep_stage in parse_deps(u["depends_on"]):
                if dep_id not in ids:
                    errs.append(f"{where}: phụ thuộc vào đơn vị không tồn tại {dep_id}")
                elif dep_stage and (dep_id, dep_stage) not in {(x["id"], x["stage"]) for x in self.units}:
                    errs.append(f"{where}: phụ thuộc vào tầng không tồn tại {dep_id}:{dep_stage}")
        errs += [f"phụ thuộc vòng: {' → '.join(c)}" for c in self._cycles()]
        return errs

    def _cycles(self) -> list[list[str]]:
        graph: dict[str, set[str]] = {i: set() for i in self.unit_ids()}
        for u in self.units:
            for dep_id, _ in parse_deps(u["depends_on"]):
                # phụ thuộc vào tầng khác của chính nó (H01:image) không phải vòng
                if dep_id in graph and dep_id != u["id"]:
                    graph[u["id"]].add(dep_id)
        color, stack, cycles = {}, [], []

        def visit(n: str) -> None:
            color[n] = 1
            stack.append(n)
            for m in sorted(graph[n]):
                if color.get(m) == 1:
                    cycles.append(stack[stack.index(m):] + [m])
                elif not color.get(m):
                    visit(m)
            stack.pop()
            color[n] = 2

        for n in graph:
            if not color.get(n):
                visit(n)
        return cycles


def _int(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 10**9
