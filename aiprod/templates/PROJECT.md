---
name: "{name}"
pack: {pack}
unit: {unit}
stages: {stages}
workers: {workers}
groups: []
format: "{format}"
audience: ""
tone: ""
style: ""
style_ref: ""
gates:
  G1: {{status: pending, by: "", at: ""}}
  G2: {{stages: {g2_stages}, delegated: false}}
  G3: {{status: pending, by: "", at: ""}}
automation: L2
---

# {name}

Mục tiêu: …
Người xem: …
Định dạng: {format}

## Units

Đơn vị: {unit} | Tầng: {stages_arrow} | Nhóm: …

## Luật cứng

Mỗi gạch đầu dòng là một ràng buộc vào mọi thẻ việc. Ví dụ, sửa theo dự án:

- Chỉ dùng nội dung, nhân vật và thông tin có trong brief; không tự thêm.
- Không chữ, logo hay watermark lạ trong sản phẩm, trừ khi spec yêu cầu.
- Mọi đơn vị giữ cùng style ở mục Style bên dưới.

## Style

Câu style dán cuối mọi prompt: …
Tham chiếu style: …
