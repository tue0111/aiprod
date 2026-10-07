# aiprod

Bộ máy ráp nhiều AI làm một dự án sản xuất nội dung: phim, slide, truyện tranh, bộ ảnh, website.

`aiprod` không gọi AI thay bạn. Nó giữ **trạng thái** của dự án trong file (không trong lịch sử chat), chặn bước đắt khi bước rẻ phía trước chưa duyệt, và cho biết việc nào làm được ngay. Đổi session, đổi agent hay đổi người vẫn làm tiếp được.

> Trạng thái: **alpha, pha 1/6**. Lệnh `new`, `plan`, `next`, `status` đã chạy được. Các lệnh còn lại đang thi công (xem [Lộ trình](#lộ-trình)).

## Ý tưởng

```
BRIEF ──► PLAN ──► PRODUCE (lặp theo từng đơn vị) ──► ASSEMBLE ──► DELIVER
 [G1]      [G1]      spec → generate → QA → duyệt [G2]    [G3]
```

- **Đơn vị (unit):** phần nhỏ nhất tạo, kiểm và duyệt riêng được. Phim là shot, slide là trang, website là section.
- **Tầng (stage):** một đơn vị có thể qua nhiều tầng, ví dụ `image → video`. Tầng sau chỉ bắt đầu khi tầng trước đã `approved`.
- **Cổng duyệt:** G1 sau brief và plan, G2 sau tầng rẻ quyết định chất lượng, G3 sau khi ghép. Luật: **không chạy bước đắt khi bước rẻ chưa duyệt.**

Vòng đời mỗi (đơn vị, tầng):

```
todo → spec_ready → generating → candidates → picked → qa_pass → approved → assembled
                                                     └► qa_fail → spec_ready
```

## Cài đặt

Cần Python 3.11 trở lên. Pack `video` cần thêm [ffmpeg](https://ffmpeg.org/download.html) trên PATH.

```bash
git clone https://github.com/tue0111/aiprod.git
cd aiprod
pip install -e ".[test]"
```

## Dùng nhanh

```bash
aiprod new my-film --pack video --name "Phim cưới"
cd my-film
# sửa PROJECT.md (brief, luật cứng, style) và units.csv (danh sách đơn vị)
aiprod plan          # kiểm mã trùng, phụ thuộc vòng, thiếu worker
aiprod next --all    # việc làm được ngay, và lý do việc khác đang chờ
aiprod status        # bảng markdown để dán vào chat
```

Mọi lệnh nhận `-C <thư mục dự án>` nếu không đứng trong thư mục đó.

## Cấu trúc một dự án

```
my-film/
  PROJECT.md      brief + frontmatter YAML: stages, workers, gates
  units.csv       một dòng cho mỗi (đơn vị, tầng)
  log.csv         nhật ký mọi việc giao và nhận
  assemble.yaml   cấu hình ghép
  tasks/          thẻ việc <id>_<stage>.md
  tools/          thẻ năng lực của từng worker (MJ, Grok, GPT, ...)
  qa/             checklist QA cho từng tầng
  queue/inbox/    hàng đợi cho bot
  queue/outbox/
  assets/  renders/
```

### `PROJECT.md`

```yaml
---
name: "Phim cưới"
pack: video
stages: ["image", "video"]
workers: {"image": "mj", "video": "grok"}
gates:
  G1: {status: pending}        # đổi thành passed khi người duyệt brief + plan
  G2: {stages: ["image"], delegated: false}
  G3: {status: pending}
---
```

### `units.csv`

```csv
id,group,order,depends_on,stage,status,worker,spec_file,pick,output,note
H01,hook,1,,image,approved,mj,,1,assets/H01/H01_img.png,
H01,hook,1,H01:image,video,qa_pass,grok,,,,mặt lộ ở 5.1s
E01,ending,4,H01,image,todo,,,,,
```

`depends_on` nhận `ID:tầng` (đúng một tầng) hoặc `ID` (tầng cuối của đơn vị đó). Nhiều phụ thuộc thì ngăn bằng `;`.

## Pack

| Pack | Đơn vị | Tầng | Cổng G2 |
|---|---|---|---|
| `video` | shot | image → video | image |
| `slides` | slide | outline → content → illustration | outline |
| `images` | image | image → edit | image |

## Lộ trình

| Pha | Việc | Trạng thái |
|---|---|---|
| 1 | Lõi, template, `new`, `plan`, `next`, `status` | ✅ |
| 2 | `task`, `log`, `approve`, adapter `manual` | ⏳ |
| 3 | `ingest`, `sheet`, pack `video` (QA + assemble bằng ffmpeg) | ⏳ |
| 4 | Adapter `bot_file` + giao thức bot | ⏳ |
| 5 | Skill cho Claude, GPT; `lessons` | ⏳ |
| 6 | Test đầy đủ | ⏳ (đã có test lõi) |

Phiên bản này **không** tự thao tác web của dịch vụ bên thứ ba (Midjourney, Grok, ...). Phần đó viết thành runbook cho người hoặc agent làm theo. Hãy kiểm điều khoản dịch vụ trước khi tự động hóa.

## Phát triển

```bash
pytest
```

## Giấy phép

[MIT](LICENSE)
