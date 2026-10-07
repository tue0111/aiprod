# Giao thức bot `aiprod-bot/1`

Dành cho bất kỳ bot nào làm worker tự động (Grok Bot, bot render, bot sửa ảnh…). Bot chỉ **đọc hàng đợi, làm đúng thẻ việc, trả file đúng tên, ghi kết quả**. Bot **không** sửa `units.csv`, không chọn ứng viên, không duyệt, không đổi prompt.

## Thư mục

```
<dự án>/queue/
  inbox/<unit>_<stage>.json     aiprod ghi khi `aiprod submit`  → bot đọc
  outbox/<file đầu ra>           bot ghi
  outbox/<unit>_<stage>.json    bot ghi kết quả                → aiprod đọc khi `aiprod sync`
  done/                         aiprod lưu job + kết quả đã xử lý (bot không đụng)
```

## Job (inbox)

```json
{
  "protocol": "aiprod-bot/1",
  "job": "H03_video",
  "unit": "H03",
  "stage": "video",
  "worker": "grok",
  "prompt": "The woman slowly lowers her hand toward his; hair sways. Static locked-off camera, no zoom, no pan. Keep the vivid 2D anime cel-shaded look…",
  "input": "E:/…/assets/H03/H03_image_mjA_t2.png",
  "task_file": "E:/…/tasks/H03_video.md",
  "output_dir": "E:/…/queue/outbox",
  "output_name": "H03_video_<tag>_t<n>.mp4",
  "ext": "mp4",
  "max_candidates": 1,
  "created": "2026-10-07T19:58:46"
}
```

| Trường | Ý nghĩa |
|---|---|
| `prompt` | Dán nguyên văn vào tool. Không thêm, không bớt. |
| `input` | Ảnh/file đầu vào đã được người duyệt. Rỗng = tầng đầu, không có đầu vào. |
| `task_file` | Thẻ việc đầy đủ: luật cứng, thẻ năng lực (runbook), QA checklist. Đọc nếu cần làm thao tác web. |
| `output_name` | Mẫu tên file. Thay `<tag>` bằng nhãn ngắn của bot (chữ, số, `-`; vd `bot`, `web`, `P7`), `<n>` bằng 1, 2, … |
| `max_candidates` | Số file tối đa trả về cho job này. |

## Bot làm gì, theo thứ tự

1. Quét `inbox/*.json` có `"protocol": "aiprod-bot/1"`, đúng `worker` của mình. Bỏ qua job đã có `outbox/<job>.json`.
2. Làm việc: mở tool, nạp `input`, dán `prompt`, chờ kết quả. Tham số tool (tỉ lệ, độ dài…) theo thẻ năng lực trong `task_file`.
3. Lưu từng file vào `output_dir` với tên theo `output_name`, vd `H03_video_bot_t1.mp4`. Tải xong hẳn mới đổi sang tên cuối (đừng để file dở mang tên đúng).
4. Ghi kết quả **sau cùng**, ghi nguyên tử: viết `outbox/<job>.json.tmp` rồi đổi tên thành `outbox/<job>.json`.

```json
{"job": "H03_video", "status": "done", "files": ["H03_video_bot_t1.mp4"], "note": "render 45s", "finished": "2026-10-07T20:01:10"}
```

Lỗi (tool từ chối, timeout, hết lượt…):

```json
{"job": "H03_video", "status": "failed", "files": [], "note": "timeout sau 3 phút", "finished": "…"}
```

5. Không xóa job trong inbox. `aiprod sync` sẽ chuyển job và kết quả vào `done/`, đưa file vào `assets/<unit>/` và cập nhật trạng thái.

## aiprod làm gì với kết quả

| Kết quả | Trạng thái đơn vị |
|---|---|
| `done` + có file đúng tên | `generating → candidates` (chờ người/Orchestrator chọn bằng `aiprod approve --pick n`) |
| `failed`, hoặc `done` mà không có file đúng tên | `generating → spec_ready` (Orchestrator phân tích lỗi; ngân sách thử 2 lần rồi đổi cách) |

## Luật cho bot

- Một job = một hành động trong thẻ việc. Không gộp, không tự làm tầng sau.
- Không tự sửa prompt kể cả khi thấy "có thể đẹp hơn". Thấy prompt có vấn đề thì trả `failed` với `note` giải thích.
- Không tự sửa ảnh đầu vào, không tự chọn clip đẹp nhất: trả đủ ứng viên, người chọn.
- Không ghi đè file đã có trong `outbox` hay `assets`.
- Tôn trọng điều khoản dịch vụ của tool. Bot thao tác web chỉ chạy khi chủ dự án đã kiểm điều khoản.

## Thử giao thức không cần bot thật

```bash
aiprod submit A1 image          # adapter bot_file ghi queue/inbox/A1_image.json
aiprod bot                      # bot giả lập: tạo file + kết quả trong outbox
aiprod bot --fail A2:image      # giả lập lỗi
aiprod sync                     # thu kết quả, trạng thái tự cập nhật
```

Bật adapter cho worker trong `PROJECT.md`:

```yaml
adapters: {grok: bot_file, mj: manual}
bot: {max_candidates: 2}
```
