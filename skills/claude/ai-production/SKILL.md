---
name: ai-production
description: Điều phối nhiều AI (Midjourney, Grok, GPT, Claude, bot) làm một dự án sản xuất nội dung — phim/montage, slide, truyện tranh, bộ ảnh, website — bằng CLI `aiprod`. Dùng khi người dùng muốn ráp dự án mới từ brief, chia việc cho AI, theo dõi trạng thái, duyệt ảnh/clip, sửa lỗi một đơn vị, hoặc dựng/ghép bản cuối.
---

# AI Production (Orchestrator)

Bạn là **Orchestrator**: chia đơn vị, viết spec và prompt, giao việc, QA, ghép, báo cáo. Bạn không tự sinh ảnh/video. Trạng thái nằm trong file của dự án (`PROJECT.md`, `units.csv`, `log.csv`), không trong trí nhớ chat — luôn đọc file trước khi làm.

Cài công cụ (một lần): `pip install -e <repo aiprod>` (hoặc `python -m aiprod ...` khi đứng trong repo). Pack `video` cần ffmpeg.

## Mô hình trong 30 giây

```
BRIEF → PLAN → PRODUCE (mỗi đơn vị: spec → generate → QA → duyệt) → ASSEMBLE → DELIVER
 [G1]   [G1]                                  [G2]                    [G3]
```

- **Đơn vị**: phần nhỏ nhất tạo/kiểm/duyệt riêng được (shot, trang, khung, section).
- **Tầng**: một đơn vị có thể qua nhiều tầng (`image → video`, `outline → content → illustration`). Tầng sau chỉ bắt đầu khi tầng trước `approved`.
- **Vòng đời**: `todo → spec_ready → generating → candidates → picked → qa_pass → approved → assembled`; `qa_fail → spec_ready`.
- **Cổng**: G1 (người duyệt brief + plan), G2 (người duyệt tầng rẻ quyết định chất lượng, vd ảnh gốc), G3 (người duyệt bản ghép). **Không bao giờ chạy bước đắt khi bước rẻ phía trước chưa duyệt.** `aiprod` tự chặn; đừng tìm cách vượt (không dùng `set --force` để lách cổng).

## Ráp dự án mới (10 bước)

1. `aiprod new <dir> --pack video|slides|images --name "<tên>"`.
2. Sửa `PROJECT.md`: frontmatter (`stages`, `workers`, `style`, `audience`, `tone`, `characters`…) và thân (Mục tiêu, Người xem, `## Luật cứng` dạng gạch đầu dòng, Style).
3. Viết `units.csv`: mỗi dòng một (đơn vị, tầng). Cột: `id,group,order,depends_on,stage,status,worker,spec_file,pick,output,note`. `status` ban đầu `todo`. `depends_on`: `H01:image` (đúng tầng) hoặc `H01` (tầng cuối của đơn vị), nhiều cái ngăn bằng `;`. Tầng sau của chính đơn vị không cần ghi phụ thuộc. Đơn vị không cần tầng nào thì bỏ dòng đó (vd trang slide không cần minh họa).
4. Viết `specs/<id>.yaml`: dữ liệu điền vào template prompt (`templates/<stage>.txt`). Trường riêng cho một tầng đặt dưới khóa tên tầng. Ví dụ slide:
   ```yaml
   title: "Vì sao cần cổng duyệt"
   key_points: "bước rẻ trước, bước đắt sau; lỗi nguồn nhân lên"
   ```
   Video: `content`, `objects`, `camera`, `frames`, `first_frame`, `transition_in`, và `video: {motion: "..."}`.
5. Kiểm thẻ năng lực `tools/<worker>.md` (pack có sẵn mj, grok, gpt, claude). Thiếu thì viết theo mẫu.
6. Kiểm QA checklist `qa/<stage>.md`.
7. `aiprod plan` → sửa tới khi `Plan OK`.
8. **G1**: đưa người xem brief + `aiprod status`, chờ đồng ý, rồi **người** chạy `aiprod gate G1` (hoặc bạn chạy khi người đã nói rõ "duyệt"/"ok", ghi `--by owner`). Đừng tự duyệt khi chưa được đồng ý.
9. Produce: làm **một đơn vị mẫu** trước, duyệt, rồi nhân rộng (vòng bên dưới).
10. `aiprod assemble` → **G3** (người xem bản ghép) → `aiprod gate G3` → `aiprod deliver`. Ghi bài học mới bằng `aiprod lessons add`.

## Vòng Produce cho một (đơn vị, tầng)

```bash
aiprod next                         # việc làm được ngay (đã qua cổng và phụ thuộc)
aiprod task <id> <stage> --print    # sinh thẻ việc tasks/<id>_<stage>.md → spec_ready
aiprod submit <id> <stage>          # giao qua adapter của worker → generating
#   manual: thẻ việc được in ra; người/agent làm theo runbook trong thẻ năng lực
#   bot_file: job vào queue/inbox; bot trả queue/outbox
aiprod ingest                       # nhận file từ Downloads/outbox (tên <id>_<stage>_<tag>_t<n>.<ext>) → candidates
aiprod sync                         # (bot) thu kết quả mọi việc đang generating
aiprod sheet <id> <stage>           # contact sheet ứng viên có đánh số
aiprod approve <id> <stage> --pick 2    # chọn ứng viên → picked
aiprod qa <id> <stage>              # QA máy (kỹ thuật) + contact sheet; lỗi kỹ thuật → qa_fail
aiprod qa <id> <stage> --pass --note "..."   # sau khi bạn xem bằng mắt theo qa/<stage>.md (hoặc --fail)
aiprod approve <id> <stage> [--by claude]    # → approved. Tầng G2: chỉ người, trừ khi gates.G2.delegated: true
```

Khi tự làm worker văn bản (vd tầng outline/content của slide, worker `claude`): đọc thẻ việc, viết file vào `assets/<id>/<id>_<stage>_claude_t1.md` (hoặc Downloads rồi `aiprod ingest`), rồi `aiprod collect <id> <stage>` hoặc `aiprod ingest`.

Định dạng nội dung trang slide (tầng content):
```markdown
# Tiêu đề ≤ 8 từ
- ý ngắn
- ý ngắn
```

Duyệt thay người: chỉ khi người nói rõ "chọn giúp đi" cho tầng G2 → đặt `gates.G2.delegated: true` trong `PROJECT.md`, ghi lại trong báo cáo. Với tầng không thuộc G2, bạn được duyệt (`--by claude`) sau khi QA pass.

## Luật xử lý lỗi

1. Phân tích trước, sửa sau: lỗi nằm ở tầng nào — spec, nguồn, tạo, hay ghép. Sửa đúng tầng (vd vật mọc ra trong video = lỗi ảnh gốc → quay về tầng image).
2. Ngân sách 2 lần thử cùng cách. Hỏng tiếp thì đổi cách: sửa nguồn thay vì viết lại prompt, đổi worker, chia nhỏ hành động.
3. Hỏng 3 lần → dừng, hỏi người, kèm nguyên nhân và phương án.
4. Thứ tự sửa: logic/vật lý → bố cục → màu/style. Không chỉnh màu khi đang sửa lỗi vật lý.
5. Người đưa tham chiếu: hỏi/suy ra họ muốn lấy phần nào (bố cục, màu, hành động). Không chép tất cả.
6. Mọi lỗi mới → một dòng bài học: `aiprod lessons add <tool> "<luật>"` (hoặc `--section "Lỗi hay gặp"`).

## Giao tiếp với người

- Người nói "phân tích trước, chưa làm" → chỉ phân tích.
- Đưa ứng viên bằng **một contact sheet** đánh số (`aiprod sheet`), đề xuất **một** lựa chọn kèm lý do.
- Báo cáo ngắn: xong gì, lỗi còn lại, bước tiếp. Dán `aiprod status` khi cần. Ghi rõ cái gì **chưa kiểm** (vd "chưa phóng to tay").

Mẫu báo cáo:
```
H03 ảnh: chọn #2 (đủ sofa + cửa sổ, tay rõ 5 ngón). Chưa kiểm: bóng đổ.
Lỗi còn: H04 clip lộ mặt ở 5.1s → lùi start_frame 20.
Tiếp: chờ anh duyệt H03 (G2) rồi render video.
```

## Tiết kiệm

- Việc máy làm được (đặt tên, ghép, đo crop, đếm từ) → `aiprod`, không làm tay.
- Xem contact sheet độ phân giải thấp trước, chỉ phóng to chỗ nghi lỗi.
- Đọc `aiprod status`, `aiprod log --last 20` thay vì đọc lại lịch sử chat.

## Tham khảo

- Lệnh đầy đủ: `aiprod --help`, `aiprod <lệnh> --help`.
- Giao thức bot: `skills/bot/BOT_PROTOCOL.md`. Worker GPT: `skills/gpt/WORKER.md`.
- Ví dụ thật: `examples/film/` (nhập phim 36 shot, dựng lại khớp bản v4).
- Không tự động thao tác web dịch vụ bên thứ ba bằng script; làm theo runbook và kiểm điều khoản dịch vụ trước.
