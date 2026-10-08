# aiprod

Bộ máy ráp nhiều AI làm một dự án sản xuất nội dung: phim, slide, truyện tranh, bộ ảnh, website.

`aiprod` không gọi AI thay bạn. Nó giữ **trạng thái** của dự án trong file (không trong lịch sử chat), sinh **thẻ việc** đủ để bất kỳ agent hay người nào làm tiếp, chặn bước đắt khi bước rẻ phía trước chưa duyệt, nhận file về đúng tên, QA kỹ thuật và ghép thành sản phẩm. Đổi session, đổi agent hay đổi người vẫn làm tiếp được.

Đã kiểm chứng trên dự án thật: nhập phim montage anime 36 shot (22 clip Grok, 14 ảnh tĩnh), tự tính crop, dựng lại khớp bản dựng tay 36/36 shot ([examples/film](examples/film)).

## Ý tưởng

```
BRIEF ──► PLAN ──► PRODUCE (lặp theo từng đơn vị) ──► ASSEMBLE ──► DELIVER
 [G1]      [G1]      spec → generate → QA → duyệt [G2]    [G3]
```

- **Đơn vị (unit):** phần nhỏ nhất tạo, kiểm và duyệt riêng được. Phim là shot, slide là trang, website là section.
- **Tầng (stage):** một đơn vị có thể qua nhiều tầng, ví dụ `image → video`. Tầng sau chỉ bắt đầu khi tầng trước đã `approved`.
- **Cổng duyệt:** G1 sau brief và plan, G2 sau tầng rẻ quyết định chất lượng, G3 sau khi ghép. Luật: **không chạy bước đắt khi bước rẻ chưa duyệt.**
- **Worker** (MJ, Grok, GPT, Claude, bot) nối qua **adapter**: `manual` (in thẻ việc cho người/agent làm theo runbook) hoặc `bot_file` (hàng đợi JSON cho bot).
- **Vai và cổng cơ học:** ai ra việc, ai làm, ai kiểm, ai duyệt được tách vai trong [HARNESS.md](HARNESS.md).

Vòng đời mỗi (đơn vị, tầng):

```
todo → spec_ready → generating → candidates → picked → qa_pass → approved → assembled
                                                     └► qa_fail → spec_ready
```

## Cài đặt

Cần Python 3.11 trở lên. Pack `video` cần [ffmpeg](https://ffmpeg.org/download.html) (trong PATH, hoặc đặt `AIPROD_FFMPEG_DIR`).

```bash
git clone https://github.com/tue0111/aiprod.git
cd aiprod
pip install -e ".[test]"
```

## Dùng nhanh

```bash
aiprod new my-film --pack video --name "Phim cưới"
cd my-film
# sửa PROJECT.md (brief, luật cứng, style), units.csv (đơn vị × tầng), specs/<id>.yaml (dữ liệu prompt)
aiprod plan                       # kiểm mã trùng, phụ thuộc vòng, thiếu worker
aiprod gate G1                    # người duyệt brief + plan
aiprod next                       # việc làm được ngay
aiprod task H01 image --print     # thẻ việc: prompt dán được ngay, luật, runbook, QA, tên file trả về
aiprod submit H01 image           # giao qua adapter của worker
aiprod ingest                     # nhận file từ Downloads / queue/outbox, đặt tên, gắn vào đơn vị
aiprod sheet H01 image            # contact sheet ứng viên đánh số
aiprod approve H01 image --pick 2 # chọn
aiprod qa H01 image               # QA máy + contact sheet; rồi --pass/--fail sau khi xem
aiprod approve H01 image          # duyệt (tầng G2: chỉ người, trừ khi đã ủy quyền)
aiprod assemble && aiprod gate G3 && aiprod deliver
aiprod status                     # bảng markdown để dán vào chat
```

Mọi lệnh nhận `-C <thư mục dự án>` nếu không đứng trong thư mục đó. Xem `aiprod --help`.

## Lệnh

| Lệnh | Việc |
|---|---|
| `new <dir> --pack video\|slides\|images` | Tạo dự án từ template (không ghi đè) |
| `plan` | Kiểm `units.csv`: mã trùng, tầng/trạng thái lạ, phụ thuộc thiếu hoặc vòng, thiếu worker |
| `next [--all]` | Việc làm được ngay; `--all` kèm lý do việc đang chờ |
| `status` | Bảng trạng thái markdown |
| `task <id\|all> [stage] [--print] [--force]` | Sinh thẻ việc `tasks/<id>_<stage>.md` |
| `submit` / `collect <id> <stage>` | Giao / nhận qua adapter |
| `ingest [--from DIR] [--dry-run] [--copy]` | Nhận file mới, đặt tên `<id>_<stage>_<tag>_t<n>`, không ghi đè |
| `sync` | Thu kết quả mọi việc của bot đang `generating` |
| `sheet <id> <stage>` | Contact sheet ứng viên |
| `approve <id> <stage> [--pick n] [--by ai] [--quote "..."] [--skip-qa]` | Chọn ứng viên / duyệt; `--by owner` bắt buộc `--quote` |
| `qa <id\|all> <stage> [--pass\|--fail --note]` | QA máy của pack / kết luận tay |
| `gate G1\|G3 [--reopen]` | Cổng duyệt của người |
| `set <id> <stage> <status> [--force]` | Sửa trạng thái tay (`--force` được ghi log và hiện trong `status`) |
| `note <id> <stage> "..." --by owner` | Ghi chú của người; mở khoá đơn vị đã `qa_fail` 3 lần (khoá `task`/`submit`/`collect`/`ingest`) |
| `assemble [--draft] [--redo H01,E02]` / `deliver [--max-mb 30]` | Ghép / nén và giao |
| `import <nguồn> <đích> --pack video [--picks file.yaml]` | Nhập dự án phim có sẵn (`docs/timeline.json` + `assets/`) |
| `bot [--fail id:stage]` | Bot giả lập để thử giao thức hàng đợi |
| `lessons add <worker> "<luật>"` / `lessons list` | Bài học vào thẻ năng lực |
| `log [--unit id] [--last n]` | Xem `log.csv` |

## Cấu trúc một dự án

```
my-film/
  PROJECT.md      brief + frontmatter YAML: stages, workers, adapters, gates, style
  units.csv       một dòng cho mỗi (đơn vị, tầng)
  specs/<id>.yaml dữ liệu điền template prompt (+ dữ liệu dựng: frames, camera, transition, cut)
  templates/      template prompt cho từng tầng
  tasks/          thẻ việc <id>_<stage>.md
  tools/          thẻ năng lực của từng worker (runbook, luật, lỗi hay gặp)
  qa/             checklist QA từng tầng; qa/results/ kết quả QA máy
  queue/          inbox/ outbox/ done/ cho bot
  assets/<id>/    file của từng đơn vị
  review/         contact sheet
  renders/        bản ghép; log.csv nhật ký mọi việc
```

## Pack

| Pack | Đơn vị | Tầng | Cổng G2 | QA máy | Ghép |
|---|---|---|---|---|---|
| `video` | shot | image → video | image | thời lượng, kích thước, viền đen → crop 16:9, contact sheet 3×3 | ffmpeg: clip/ảnh tĩnh + camera giả, fade, flash, dissolve; preview < 30 MB |
| `slides` | slide | outline → content → illustration | outline | số ý, tiêu đề ≤ 8 từ, thân ≤ 40 từ | deck HTML + Markdown, zip |
| `images` | image | image → edit | image | tỉ lệ, độ phân giải | lưới + zip |

## Skill cho agent

- [`skills/claude/ai-production/SKILL.md`](skills/claude/ai-production/SKILL.md): dạy Claude làm Orchestrator bằng `aiprod`. Đã thử: một agent mới chỉ đọc file này ráp xong bộ slide 5 trang mà không cần hỏi.
- [`skills/bot/BOT_PROTOCOL.md`](skills/bot/BOT_PROTOCOL.md): giao thức hàng đợi `aiprod-bot/1` cho bot.
- [`skills/gpt/WORKER.md`](skills/gpt/WORKER.md): dán vào ChatGPT Project instructions để GPT làm worker.

Phiên bản này **không** tự thao tác web của dịch vụ bên thứ ba (Midjourney, Grok, …). Phần đó viết thành runbook trong thẻ năng lực cho người hoặc agent làm theo, hoặc giao cho bot qua `bot_file`. Hãy kiểm điều khoản dịch vụ trước khi tự động hóa. Module `aiprod.adapters` có sẵn interface để cắm thêm adapter (`api_*`, trình duyệt) sau này.

## Phát triển

```bash
pytest          # test cần ffmpeg tự bỏ qua nếu máy không có
```

CI chạy trên Ubuntu và Windows, Python 3.11 và 3.13.

## Giấy phép

[MIT](LICENSE)
