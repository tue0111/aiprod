"""Pack = cấu hình riêng cho một loại dự án (tầng, worker mặc định, cổng G2, QA, assemble)."""
from __future__ import annotations

PACKS: dict[str, dict] = {
    "video": {
        "unit": "shot",
        "stages": ["image", "video"],
        "workers": {"image": "mj", "video": "grok"},
        "g2_stages": ["image"],  # tầng rẻ quyết định chất lượng: người duyệt trước khi chạy tầng đắt
        "format": "1920x1080, 30fps",
    },
    "slides": {
        "unit": "slide",
        "stages": ["outline", "content", "illustration"],
        "workers": {"outline": "claude", "content": "claude", "illustration": "mj"},
        "g2_stages": ["outline"],
        "format": "16:9",
    },
    "images": {
        "unit": "image",
        "stages": ["image", "edit"],
        "workers": {"image": "mj", "edit": "gpt"},
        "g2_stages": ["image"],
        "format": "2048x2048",
    },
}


def get_pack(name: str) -> dict:
    if name not in PACKS:
        raise KeyError(f"pack lạ {name!r}; có: {', '.join(PACKS)}")
    return PACKS[name]
