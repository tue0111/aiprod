# claude
Loại: text, code       Điều khiển: chat (Orchestrator) hoặc CLI (Claude Code)
Giỏi: chia đơn vị, viết spec/prompt, dàn ý, nội dung, QA bằng mắt qua contact sheet, viết code assemble
Dở: không tự tạo ảnh/video; không nên làm việc máy làm được (đặt tên, ghép) bằng tay
Đầu vào: thẻ việc       Đầu ra: file .md/.txt đặt tên theo thẻ việc       Chi phí / tốc độ: nhanh

Luật dùng:
- Viết đầu ra thành file đúng tên trong thẻ việc rồi `aiprod ingest`, không chỉ trả lời trong chat.
- Văn bản cho slide: tiêu đề ≤ 8 từ, thân ≤ 40 từ.

Runbook:
1. `aiprod task <id> <stage> --print` để đọc thẻ.
2. Viết file vào `assets/<id>/<id>_<stage>_claude_t1.md` (hoặc Downloads rồi `aiprod ingest`).

Lỗi hay gặp → cách xử lý:
- …
