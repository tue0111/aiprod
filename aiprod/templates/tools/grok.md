# grok (Grok Imagine)
Loại: video, edit       Điều khiển: web runbook (grok.com/imagine) hoặc bot (adapter bot_file)
Giỏi: image-to-video ngắn giữ đúng ảnh gốc, chuyển động vi mô (tóc, rèm, thở), sửa ảnh nhỏ (Edit)
Dở: camera di chuyển, đổi tư thế lớn, đoạn cuối clip hay cho nhân vật quay mặt ra camera
Đầu vào: ảnh đã duyệt + prompt chuyển động       Đầu ra: MP4 6s, 1080p (1920×1088, 24fps)       Chi phí / tốc độ: 40–50s/clip

Luật dùng:
- Camera đứng yên: "Static locked-off camera, no zoom, no pan". Orbit/zoom làm phòng trôi, lộ mặt, đổi chân tay.
- Mỗi clip một hành động nhỏ. Không đổi tư thế lớn (đứng → ngồi lên đùi): tư thế cuối phải là một ảnh gốc riêng.
- Shot kết: "giữ nguyên tư thế, chỉ thở, tóc lay, rèm lay" là sạch nhất.
- Clip 6s nhưng shot chỉ dùng 1,7–3s: chọn `cut.start_frame` tránh đoạn cuối.
- Chọn tỉ lệ 16:9 TRƯỚC khi upload ảnh (upload trước ra 2:3).

Runbook:
1. Trang mới: tìm `file input` trong form prompt (ref đổi 180–182), upload ảnh, bấm biểu tượng Video, bấm vào ô prompt.
2. Lần gõ đầu sau khi chuyển chế độ hay bị mất: gõ, chụp màn hình kiểm, mất thì gõ lại ở lượt sau.
3. Nút gửi dịch theo số dòng prompt (≈ y=428 khi 4 dòng, y=448–450 khi 5 dòng).
4. Tải video bằng `currentSrc` ĐẦY ĐỦ query của thẻ `<video>` có id trùng id trong URL trang (bỏ query → 404). Không lấy nhầm video cũ cùng trang.
5. Đặt tên `<id>_video_<tag>_t<n>.mp4`, rồi `aiprod ingest`. Windows: chuyển file bằng PowerShell `Move-Item` sau khi tải xong.

Lỗi hay gặp → cách xử lý:
- Viền đen trên/dưới → `aiprod qa` tự tính crop 16:9 (bội 4, căn giữa).
- "Bàn mọc ra", vật xuất hiện → lỗi ở ảnh gốc: quay về tầng image thêm vật, không viết lại prompt video.
- Lộ mặt ở cuối clip → lùi `cut.start_frame` hoặc rút ngắn shot.
