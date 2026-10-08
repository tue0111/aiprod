"""Adapter `bot_file` (mức L3): giao việc cho bot qua hàng đợi file JSON.

    queue/inbox/<unit>_<stage>.json    aiprod ghi (submit)       → bot đọc
    queue/outbox/<file kết quả>         bot ghi file đúng tên
    queue/outbox/<unit>_<stage>.json   bot ghi kết quả           → aiprod đọc (collect / sync)
    queue/done/                        aiprod lưu lại job và kết quả đã xử lý

Giao thức chi tiết: skills/bot/BOT_PROTOCOL.md. Bot chỉ làm đúng thẻ việc, không tự chọn, không tự duyệt.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from ..core import log
from ..core.project import Project
from ..core.tasks import context, output_pattern, render_prompt, stage_ext, stage_template
from .base import Adapter, CollectResult, SubmitResult

PROTOCOL = "aiprod-bot/1"


def job_name(row: dict) -> str:
    return f"{row['id']}_{row['stage']}"


class BotFileAdapter(Adapter):
    name = "bot_file"
    level = "L3"

    @property
    def inbox(self) -> Path:
        return self.p.root / "queue" / "inbox"

    @property
    def outbox(self) -> Path:
        return self.p.root / "queue" / "outbox"

    @property
    def done(self) -> Path:
        return self.p.root / "queue" / "done"

    def describe(self) -> str:
        return "Ghi job JSON vào queue/inbox; bot trả file + kết quả JSON vào queue/outbox."

    def submit(self, row: dict, task_path: Path) -> SubmitResult:
        self.inbox.mkdir(parents=True, exist_ok=True)
        ctx = context(self.p, row)
        prompt = ctx.get("prompt") or render_prompt(stage_template(self.p, row["stage"]), ctx)[0]
        inp = ctx.get("input") or ""
        job = {
            "protocol": PROTOCOL,
            "job": job_name(row),
            "unit": row["id"],
            "stage": row["stage"],
            "worker": self.p.worker_of(row),
            "prompt": prompt,
            "input": str(Path(inp) if Path(inp).is_absolute() else self.p.root / inp) if inp else "",
            "task_file": str(task_path.resolve()),
            "output_dir": str(self.outbox.resolve()),
            "output_name": output_pattern(self.p, row),
            "ext": stage_ext(self.p, row["stage"]),
            "max_candidates": int((self.p.meta.get("bot") or {}).get("max_candidates", 1)),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        path = self.inbox / f"{job['job']}.json"
        if path.exists():
            return SubmitResult(False, f"{path.name} đã có trong inbox — bot chưa xử lý xong việc trước")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # ghi nguyên tử: bot không bao giờ đọc phải file dở
        return SubmitResult(True, f"Đã xếp hàng {path}", ref=str(path.relative_to(self.p.root)))

    def collect(self, row: dict) -> CollectResult:
        from ..core.ingest import ingest

        res_path = self.outbox / f"{job_name(row)}.json"
        if not res_path.exists():
            return CollectResult(message="bot chưa trả kết quả")
        try:
            res = json.loads(res_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return CollectResult(message="kết quả đang ghi dở, thử lại sau")
        failed = res.get("status") != "done"
        moved: list[Path] = []
        if not failed:
            names = set(res.get("files") or [])
            r = ingest(self.p, [self.outbox], only=(row["id"], row["stage"]))
            moved = [Path(m["dest"]) for m in r["moved"] if Path(m["src"]).name in names or not names]
        self.done.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(res_path), str(self.done / f"{job_name(row)}_{stamp}_result.json"))
        job = self.inbox / f"{job_name(row)}.json"
        if job.exists():
            shutil.move(str(job), str(self.done / f"{job_name(row)}_{stamp}_job.json"))
        note = res.get("note", "")
        if failed:
            return CollectResult(failed=True, done=True, message=f"bot báo lỗi: {note or res.get('status')}")
        if not moved:
            return CollectResult(failed=True, done=True, message="bot báo xong nhưng không có file đúng tên trong outbox")
        return CollectResult(files=moved, done=True, message=f"{len(moved)} file từ bot. {note}".strip())


def sync(p: Project) -> list[str]:
    """Thu kết quả mọi việc đang `generating` của worker dùng bot_file. Trạng thái tự cập nhật."""
    from ..core import actions

    out = []
    for row in list(p.units):
        if row["status"] != "generating":
            continue
        if (p.meta.get("adapters") or {}).get(p.worker_of(row)) != "bot_file":
            continue
        try:
            r = actions.collect(Project.load(p.root), row["id"], row["stage"])
        except actions.ActionError as e:  # đơn vị bị khoá vì qa_fail
            out.append(f"{row['id']}:{row['stage']}: bỏ qua, {e}")
            continue
        out.append(f"{row['id']}:{row['stage']}: {r['result'].message} → {r['status']}")
    return out


# ------------------------------------------------------------ bot giả lập

def _fake_output(job: dict, dest: Path) -> None:
    """Tạo file giả đúng loại: ảnh PNG có chữ, hoặc clip 6s từ ảnh đầu vào (cần ffmpeg)."""
    from PIL import Image, ImageDraw

    if job["ext"] in ("png", "jpg", "jpeg", "webp"):
        im = Image.new("RGB", (1920, 1080), (40, 30, 60))
        ImageDraw.Draw(im).text((40, 40), f"FAKE {job['job']}\n{job['prompt'][:200]}", fill=(255, 220, 80))
        im.save(dest)
    elif job["ext"] in ("mp4", "mov", "webm"):
        from ..core.media import ffmpeg, has_ffmpeg, run

        if not has_ffmpeg():
            dest.write_bytes(b"fake video")
            return
        src = ["-loop", "1", "-i", job["input"]] if job.get("input") and Path(job["input"]).exists() else \
              ["-f", "lavfi", "-i", "color=c=0x302040:s=1920x1088:r=24"]
        run([ffmpeg(), "-y", "-v", "error", *src, "-t", "6", "-vf", "scale=1920:1088,setsar=1,fps=24",
             "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(dest)])
    else:
        dest.write_text(f"FAKE {job['job']}\n\n{job['prompt']}\n", encoding="utf-8")


def simulate(p: Project, worker: str | None = None, fail: set[str] | None = None) -> str:
    """Bot giả lập: đọc từng job trong inbox, tạo file đầu ra, ghi kết quả vào outbox.

    Dùng để thử giao thức và hướng dẫn người viết bot thật. Không đụng units.csv (đó là việc của aiprod).
    """
    inbox, outbox = p.root / "queue" / "inbox", p.root / "queue" / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    lines = []
    for jf in sorted(inbox.glob("*.json")):
        job = json.loads(jf.read_text(encoding="utf-8"))
        if job.get("protocol") != PROTOCOL or (worker and job.get("worker") != worker):
            continue
        if (outbox / f"{job['job']}.json").exists():
            continue  # đã làm, chờ aiprod thu
        key = f"{job['unit']}:{job['stage']}"
        if key in (fail or set()):
            result = {"job": job["job"], "status": "failed", "files": [], "note": "giả lập lỗi render"}
        else:
            files = []
            for i in range(1, int(job.get("max_candidates", 1)) + 1):
                name = job["output_name"].replace("<tag>", "bot").replace("<n>", str(i))
                _fake_output(job, outbox / name)
                files.append(name)
            result = {"job": job["job"], "status": "done", "files": files, "note": "bot giả lập"}
        result["finished"] = datetime.now().isoformat(timespec="seconds")
        tmp = outbox / f"{job['job']}.json.tmp"
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(outbox / f"{job['job']}.json")
        log.write(p.root, job["unit"], job["stage"], job.get("worker", ""), "bot:sim", ";".join(result["files"]),
                  result["status"], result["note"])
        lines.append(f"{key}: {result['status']} {', '.join(result['files'])}")
    return "\n".join(lines) or "inbox trống"
