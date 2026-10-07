# mj (Midjourney)
Loại: image       Điều khiển: web runbook (midjourney.com)
Giỏi: style điện ảnh, ánh sáng, nhất quán tông khi dùng --sref       Dở: tay, chữ, đếm vật, logic hành động
Đầu vào: prompt + --sref (URL ảnh đã duyệt)       Đầu ra: 4 ảnh/job (0_0 … 0_3), PNG       Chi phí / tốc độ: ~1 phút/job

Luật dùng:
- Vật cần cho hành động phải nằm sẵn trong ảnh gốc (ly, thìa, quầy, sofa). Tầng video không được tự sinh vật mới.
- Bố cục phải logic với hành động: muốn "đặt ly rồi đi lại chỗ nam" thì quầy và nam cùng khung, có lối đi.
- Các đơn vị cùng nhóm dùng `--sref` là ảnh đầu tiên đã duyệt của nhóm, `--sw 100`.
- Ảnh tham chiếu người đưa là để lấy bố cục, không lấy màu/style. Màu và style luôn theo style đã duyệt.
- Không đổi màu khi đang sửa lỗi vật lý.

Runbook:
1. Gõ prompt bằng JS: native setter trên `textarea` + dispatch sự kiện `input`, rồi bấm Return ở một thao tác riêng (gõ phím thật hay timeout).
2. Feed là danh sách ảo hóa: muốn lấy job id thì cuộn container, gom `img.src` theo regex UUID, ghép với đoạn prompt gần nhất. Không in URL có query string.
3. Tải ảnh: `fetch(cdn…/<job>/0_<n>.png)` ngay trong trang MJ rồi tạo `a[download]`. Máy ngoài không tải thẳng CDN được.
4. Đặt tên theo thẻ việc: `<id>_image_<tag>_t<n>.png` (tag = job id rút gọn), rồi `aiprod ingest`.

Lỗi hay gặp → cách xử lý:
- Thiếu vật / bố cục sai hành động → sửa prompt nêu vật và vị trí; 2 lần không được thì đổi sang worker sửa ảnh (gpt, grok edit).
- Tóc nhân vật bị búi → thêm vào `--no` (hair bun, ponytail) và nêu "ALWAYS loose".
