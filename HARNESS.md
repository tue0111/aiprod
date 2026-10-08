# HARNESS: hợp đồng vận hành của aiprod

Mục đích: tách rõ **ai ra việc, ai làm, ai kiểm, ai duyệt**. Một vai không được ôm hai bước liên tiếp của cùng một đơn vị. Luật nào quan trọng đều được mã hoá kép: viết bằng chữ ở đây, và có cổng cơ học chặn khi vi phạm (cột "Cổng").

Trạng thái: cột "Có sẵn?" ở mục 4 phản ánh đúng code hiện tại của repo. Cổng nào chưa có ghi "Chưa" và được cập nhật khi cổng đó được viết.

**Giới hạn cần biết:** `--by` do người gọi lệnh tự khai, `aiprod` không xác thực danh tính. Các cổng dưới đây chống nhầm lẫn (agent lỡ tự duyệt, lỡ lách cổng), không phải cơ chế xác thực hay bảo mật. Ai cố tình khai sai `--by` thì cổng không chặn được.

## 1. Bốn vai

| Vai | Ai đóng | Được làm | Không được làm |
|---|---|---|---|
| **Owner** (người duyệt) | Người | Duyệt G1, G2, G3. Đổi brief. Ủy quyền G2 có phạm vi | (không giới hạn) |
| **Orchestrator** (ra việc) | Claude | Chia đơn vị, viết spec, sinh thẻ việc, giao, nhận file, chạy `aiprod`, báo cáo | Tự sinh ảnh/video. Tự duyệt G1/G3. Tự duyệt G2 khi chưa có ủy quyền. Chạy `--by owner` khi Owner chưa nói rõ |
| **Worker** (thi hành) | MJ, Grok, GPT, bot, hoặc Claude khi thẻ ghi worker `claude` | Làm đúng một việc trong thẻ, trả đúng tên file, tự báo mục chưa kiểm | Đổi brief. Chọn giữa phương án lớn. Duyệt bài của mình. Sửa ngoài phạm vi thẻ |
| **Checker** (kiểm) | QA máy của pack, rồi mắt người hoặc agent khác | Ra pass/fail theo `qa/<stage>.md` | Là chính vai đã làm ra ứng viên |

Quy tắc ghép vai: nếu Claude vừa là Worker của một (đơn vị, tầng) thì Claude không được là Checker hay người chọn ứng viên của chính (đơn vị, tầng) đó. Việc chọn và duyệt chuyển sang Owner hoặc agent khác.

## 2. Nhiệm vụ: thẻ việc là hợp đồng

Mỗi thẻ việc `tasks/<id>_<stage>.md` phải có đủ bốn mục. `aiprod task` luôn sinh đủ bốn mục; nếu thiếu dữ liệu thì mục đó ghi mặc định của pack, và `aiprod plan` cảnh báo (không báo lỗi, để dự án cũ vẫn chạy).

1. **Sản phẩm giao**: tên file đúng mẫu `<id>_<stage>_<tag>_t<n>.<ext>`, định dạng, kích thước.
2. **Ràng buộc**: luật cứng từ `PROJECT.md`, style, thứ cần giữ nguyên.
3. **Ngoài phạm vi**: danh sách việc worker không được đụng (đổi bố cục, đổi màu, thêm vật, thêm chữ).
4. **Tiêu chí nghiệm thu**: điều kiện đo được để đóng thẻ, lấy từ `qa/<stage>.md`.

Không có hợp đồng thì worker tự quyết khi nào xong. Có hợp đồng thì tiêu chí quyết định.

Cổng: `aiprod plan` cảnh báo khi một tầng thiếu dữ liệu cho một trong bốn mục. (Có.) "Ngoài phạm vi" lấy từ `out_of_scope` trong spec của đơn vị, không có thì dùng mặc định của pack.

## 3. Thi hành: worker chỉ làm, báo, dừng

- Làm đúng một việc trong thẻ. Gặp thẻ mâu thuẫn hoặc thiếu dữ liệu thì hỏi lại, không đoán.
- Trả file kèm tự kiểm theo checklist: mục đạt và **mục chưa kiểm được**. "Chưa kiểm" là câu trả lời hợp lệ; "đạt" khi chưa kiểm thì không.
- Cần đổi phần ngoài phạm vi để hoàn thành: dừng, nói rõ, chờ Orchestrator.
- Worker không ghi vào `units.csv` và không chạy `approve`. Trạng thái do `aiprod` ghi.

## 4. Cổng cơ học

| Luật | Cổng | Có sẵn? |
|---|---|---|
| Tầng sau chỉ bắt đầu khi tầng trước `approved` | `Project.blockers()` (phụ thuộc trong `units.csv`) | Có |
| Không chạy bước đắt khi bước rẻ chưa duyệt | G1, G2, G3 | Có |
| Không lách cổng bằng `set --force` | `set --force` ghi log (`action=set:force`) và `aiprod status` liệt kê | Có |
| Chọn ứng viên trước, QA sau, duyệt sau cùng | Vòng đời trạng thái (`states.py`) | Có |
| Agent không duyệt bài do chính nó làm | `approve` và `approve --pick` đọc `log.csv`; từ chối nếu `--by` trùng cột `worker` của các dòng `collect`/`ingest`/`pick` cùng (đơn vị, tầng). Giới hạn: `worker` là worker được gán cho tầng, không phải người chạy lệnh thật. Tầng gán `mj` mà `--by claude` duyệt thì không bị chặn (Claude không làm bài đó). Áp dụng cho cả `approve` và `approve --pick` | Có |
| Agent không chấm `qa --pass` bài do chính nó làm | `qa --pass` so `--by` với cột `worker` của dòng `collect`/`ingest` cùng (đơn vị, tầng), cùng giới hạn như cổng trên. `qa --fail` vẫn cho phép | Có |
| `--by owner` chỉ chạy khi Owner nói rõ trong chat | `aiprod approve`, `gate`, `qa --pass/--fail` (CLI) bắt buộc `--quote "<câu của Owner>"` khi `--by` là người, ghi vào `note` trong `log.csv` dạng `quote: "..."`. API `actions` không đổi. Áp dụng cả `--pick`, `gate G1/G3` (kể cả `--reopen`) và `qa --pass/--fail`. Người duyệt tay cũng gõ `--quote`. QA máy (`qa` không `--pass/--fail`) không cần | Có |
| Hỏng 3 lần cùng đơn vị thì dừng | Đếm `qa_fail` theo (đơn vị, tầng) từ `log.csv`; lần thứ 3 khoá `task`, `submit`, `collect`; `ingest` bỏ qua đơn vị đang khoá và cảnh báo. Mở khoá bằng `aiprod note <id> <stage> "..." --by owner` (chỉ người). Không khoá `approve --pick`. Bộ đếm về 0 khi có ghi chú của người hoặc khi duyệt `approved`. Giới hạn: mỗi dòng `qa`/`qa:auto` có `result=qa_fail` được tính một lần, kể cả chạy lại QA máy trên bài đã `qa_fail` | Có |
| Ghi bài học sau mỗi lỗi mới | `aiprod lessons add` | Có |

## 5. Leo thang

- Cùng một lỗi hai lần: đổi cách (sửa nguồn thay vì viết lại prompt, đổi worker, chia nhỏ hành động).
- Lần ba: dừng, báo Owner nguyên nhân và phương án.
- Lỗi vật lý hoặc logic trong video thường là lỗi ảnh gốc: quay về tầng image, không chỉnh prompt video.
- Sửa theo thứ tự: logic/vật lý, rồi bố cục, rồi màu/style.

## 6. Định nghĩa "xong"

Một (đơn vị, tầng) xong khi và chỉ khi: file đúng tên đã `ingest`, QA máy pass, checklist mắt đã ghi `--pass --note`, và duyệt đúng vai theo mục 1. Báo cáo của Orchestrator luôn có dòng "Chưa kiểm: ...".

## 7. Bộ nhớ

- Trạng thái dự án nằm trong `PROJECT.md`, `units.csv`, `log.csv`, không nằm trong lịch sử chat.
- Phiên mới hoặc agent mới bắt đầu bằng: đọc `HARNESS.md`, rồi `aiprod status`, rồi `aiprod log --last 20`.
- Bài học đúng nơi: `tools/<worker>.md` qua `aiprod lessons add`.
