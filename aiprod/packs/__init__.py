"""Pack = cấu hình riêng cho một loại dự án.

Mỗi pack khai báo: loại đơn vị, các tầng, worker mặc định, tầng nào qua cổng G2,
đuôi file đầu ra của từng tầng, và template prompt/spec cho từng tầng.
Pack có code riêng (QA tự động, assemble) đặt ở module con `aiprod.packs.<tên>`
với các hàm tùy chọn: `qa(project, row) -> dict`, `assemble(project, **kw) -> Path`,
`deliver(project, **kw) -> Path`.
"""
from __future__ import annotations

import importlib
from types import ModuleType

PACKS: dict[str, dict] = {
    "video": {
        "unit": "shot",
        "stages": ["image", "video"],
        "workers": {"image": "mj", "video": "grok"},
        "g2_stages": ["image"],  # tầng rẻ quyết định chất lượng: người duyệt trước khi chạy tầng đắt
        "format": "1920x1080, 30fps",
        "ext": {"image": "png", "video": "mp4"},
        "templates": {
            "image": "{content}. {characters}. {style} {sref} {mj_suffix} --no {mj_no}",
            "video": "{motion}. Static locked-off camera, no zoom, no pan. {grok_suffix}",
        },
        "done_when": {
            "image": "Đủ vật trong `objects` có sẵn trong ảnh; bố cục khớp hành động; đúng luật cứng; 16:9.",
            "video": "Một hành động nhỏ, camera đứng yên; không lỗi tay/chân/vật/phòng trôi/lộ mặt; crop hết viền đen.",
        },
        "out_of_scope": {
            "image": "Không đổi bố cục hay góc máy khác spec; không thêm vật ngoài `objects`; không thêm chữ/watermark; không đổi style.",
            "video": "Không zoom/pan; không thêm vật hay nhân vật; không đổi cảnh so với ảnh gốc.",
        },
    },
    "slides": {
        "unit": "slide",
        "stages": ["outline", "content", "illustration"],
        "workers": {"outline": "claude", "content": "claude", "illustration": "mj"},
        "g2_stages": ["outline"],
        "format": "16:9",
        "ext": {"outline": "md", "content": "md", "illustration": "png"},
        "templates": {
            "outline": "Viết dàn ý cho trang \"{title}\": ý chính {key_points}. Tối đa 5 gạch đầu dòng. Người xem: {audience}.",
            "content": "Viết nội dung trang \"{title}\" theo dàn ý đã duyệt ({input}). Tiêu đề ≤ 8 từ, ≤ 40 từ thân. Giọng: {tone}.",
            "illustration": "{visual}. {style} --ar 16:9",
        },
        "done_when": {
            "outline": "≤ 5 ý, mỗi ý một dòng, khớp mục tiêu trang.",
            "content": "Tiêu đề ≤ 8 từ, thân ≤ 40 từ, không tràn khung, không lỗi chính tả.",
            "illustration": "16:9, không chữ trong ảnh, đúng style.",
        },
        "out_of_scope": {
            "outline": "Không viết nội dung chi tiết; không chọn hình; không thêm trang ngoài kế hoạch.",
            "content": "Không đổi dàn ý đã duyệt; không thêm ý mới; không chọn hình.",
            "illustration": "Không chữ trong ảnh; không đổi nội dung trang.",
        },
    },
    "images": {
        "unit": "image",
        "stages": ["image", "edit"],
        "workers": {"image": "mj", "edit": "gpt"},
        "g2_stages": ["image"],
        "format": "2048x2048",
        "ext": {"image": "png", "edit": "png"},
        "templates": {
            "image": "{content}. {style}",
            "edit": "Sửa ảnh {input}: {fix}. Giữ nguyên bố cục, màu và ánh sáng.",
        },
        "done_when": {
            "image": "Đúng góc chụp trong spec, đúng kích thước, không chữ/watermark.",
            "edit": "Chỉ chỗ cần sửa thay đổi; phần còn lại giữ nguyên.",
        },
        "out_of_scope": {
            "image": "Không thêm chữ/watermark; không đổi góc chụp trong spec.",
            "edit": "Không đổi bố cục, màu, ánh sáng ngoài chỗ cần sửa.",
        },
    },
}


def get_pack(name: str) -> dict:
    if name not in PACKS:
        raise KeyError(f"pack lạ {name!r}; có: {', '.join(PACKS)}")
    return PACKS[name]


def pack_module(name: str) -> ModuleType | None:
    """Module code của pack (nếu có)."""
    get_pack(name)
    try:
        return importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as e:
        if e.name == f"{__name__}.{name}":
            return None
        raise
