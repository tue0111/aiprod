"""Pack slides: QA văn bản (số ý, số từ, tiêu đề) và ghép thành deck HTML + Markdown (không cần thư viện ngoài).

Đơn vị = trang. Tầng: outline → content → illustration (illustration tùy chọn: đơn vị nào
không có dòng illustration trong units.csv thì trang chỉ có chữ).
Nội dung trang (tầng content) là file Markdown: dòng `# Tiêu đề`, sau đó gạch đầu dòng.
"""
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

from ..core import log
from ..core.project import Project

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def _resolve(p: Project, rel: str) -> Path:
    f = Path(rel)
    return f if f.is_absolute() else p.root / f


def _words(s: str) -> int:
    return len(re.findall(r"\w+", s))


def parse_page(md: str) -> tuple[str, list[str]]:
    title, body = "", []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#") and not title:
            title = s.lstrip("#").strip()
        else:
            body.append(re.sub(r"^[-*•]\s*|^\d+[.)]\s*", "", s))
    return title, body


def qa(p: Project, row: dict, path: Path, apply: bool = True) -> list[dict]:
    stage = row["stage"]
    if path.suffix.lower() in IMG_EXT:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
        return [{"check": "ảnh 16:9", "ok": abs(w / h - 16 / 9) < 0.02, "detail": f"{w}x{h}"}]
    text = path.read_text(encoding="utf-8")
    title, body = parse_page(text)
    checks = []
    if stage == "outline":
        checks.append({"check": "≤ 5 ý", "ok": 0 < len(body) + bool(title) <= 6 and len(body) <= 5,
                       "detail": f"{len(body)} ý"})
    else:
        tw, bw = _words(title), sum(_words(b) for b in body)
        checks.append({"check": "có tiêu đề `# ...`", "ok": bool(title), "detail": title or "(thiếu)"})
        checks.append({"check": "tiêu đề ≤ 8 từ", "ok": 0 < tw <= 8, "detail": f"{tw} từ"})
        checks.append({"check": "thân ≤ 40 từ", "ok": bw <= 40, "detail": f"{bw} từ, {len(body)} dòng"})
    return checks


def _pages(p: Project, draft: bool) -> list[dict]:
    ok = {"approved", "assembled"} | ({"picked", "qa_pass", "qa_fail", "candidates", "spec_ready"} if draft else set())
    pages = []
    for uid in p.unit_ids():
        rows = {r["stage"]: r for r in p.unit_rows(uid)}
        c, ill = rows.get("content"), rows.get("illustration")
        title, body = uid, []
        if c and c["status"] in ok and c["output"] and _resolve(p, c["output"]).exists():
            title, body = parse_page(_resolve(p, c["output"]).read_text(encoding="utf-8"))
        img = _resolve(p, ill["output"]) if ill and ill["status"] in ok and ill["output"] else None
        order = int(rows[next(iter(rows))]["order"] or 0)
        pages.append({"id": uid, "order": order, "title": title, "body": body, "img": img})
    return sorted(pages, key=lambda x: (x["order"], x["id"]))


CSS = """
:root{--bg:#0f1115;--fg:#f2f2f2;--muted:#a9b0bb;--accent:#ffc857}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,Segoe UI,sans-serif}
.slide{width:min(100vw,177.78vh);height:min(56.25vw,100vh);margin:0 auto;display:none;padding:6% 7%;position:relative;overflow:hidden}
.slide.on{display:flex;flex-direction:column;justify-content:center}
.slide h1{font-size:clamp(24px,5vw,64px);margin:0 0 .6em;color:var(--accent)}
.slide ul{font-size:clamp(16px,2.4vw,32px);line-height:1.5;margin:0;padding-left:1.1em}
.slide.img{background-size:cover;background-position:center}
.slide.img::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.75),rgba(0,0,0,.2))}
.slide>*{position:relative}.n{position:absolute;right:3%;bottom:3%;color:var(--muted);font-size:14px}
"""

JS = """
let i=0;const s=[...document.querySelectorAll('.slide')];
function go(k){s[i].classList.remove('on');i=Math.max(0,Math.min(s.length-1,k));s[i].classList.add('on');}
s[0]&&s[0].classList.add('on');
addEventListener('keydown',e=>{if(['ArrowRight',' ','PageDown'].includes(e.key))go(i+1);if(['ArrowLeft','PageUp'].includes(e.key))go(i-1);});
addEventListener('click',e=>go(e.clientX>innerWidth/2?i+1:i-1));
"""


def assemble(p: Project, redo: set[str] | None = None, draft: bool = False, out: Path | None = None) -> Path:
    pages = _pages(p, draft)
    rd = p.root / "renders"
    (rd / "img").mkdir(parents=True, exist_ok=True)
    md, sl = [], []
    for k, pg in enumerate(pages, 1):
        md.append(f"# {pg['title']}\n\n" + "\n".join(f"- {b}" for b in pg["body"]))
        style, cls = "", "slide"
        if pg["img"] and pg["img"].exists():
            dest = rd / "img" / pg["img"].name
            shutil.copy2(pg["img"], dest)
            style, cls = f' style="background-image:url(img/{html.escape(dest.name)})"', "slide img"
            md[-1] += f"\n\n![]({'img/' + dest.name})"
        items = "".join(f"<li>{html.escape(b)}</li>" for b in pg["body"])
        sl.append(f'<section class="{cls}"{style}><h1>{html.escape(pg["title"])}</h1><ul>{items}</ul>'
                  f'<span class="n">{k}/{len(pages)}</span></section>')
    name = html.escape(str(p.meta.get("name", "Deck")))
    out = out or rd / ("deck_draft.html" if draft else "deck.html")
    out.write_text(f"<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
                   f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{name}</title>"
                   f"<style>{CSS}</style></head><body>{''.join(sl)}<script>{JS}</script></body></html>", encoding="utf-8")
    out.with_suffix(".md").write_text("\n\n---\n\n".join(md) + "\n", encoding="utf-8")
    if not draft:
        for r in p.units:
            if r["status"] == "approved":
                r["status"] = "assembled"
        p.save_units()
    log.write(p.root, action="assemble" + (":draft" if draft else ""), file=str(out.relative_to(p.root)),
              result="ok", note=f"{len(pages)} trang")
    return out


def deliver(p: Project, max_mb: float = 30, src: Path | None = None) -> Path:
    """Gói deck.html + ảnh + deck.md thành một file zip trong deliver/."""
    src = src or p.root / "renders" / "deck.html"
    if not src.exists():
        raise FileNotFoundError(f"{src} chưa có — chạy aiprod assemble trước")
    d = p.root / "deliver"
    d.mkdir(exist_ok=True)
    stage = d / "_pack"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for f in [src, src.with_suffix(".md")]:
        shutil.copy2(f, stage / f.name)
    if (src.parent / "img").is_dir():
        shutil.copytree(src.parent / "img", stage / "img")
    out = Path(shutil.make_archive(str(d / re.sub(r"\W+", "_", str(p.meta.get("name", "deck"))).strip("_")), "zip", stage))
    shutil.rmtree(stage)
    mb = out.stat().st_size / 1e6
    if mb >= max_mb:
        raise RuntimeError(f"{out.name} {mb:.1f} MB ≥ {max_mb} MB — giảm cỡ ảnh minh họa")
    log.write(p.root, action="deliver", file=str(out.relative_to(p.root)), result="ok", note=f"{mb:.2f} MB")
    return out
