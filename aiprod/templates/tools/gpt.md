# gpt (ChatGPT / GPT image)
Loại: edit, image, text       Điều khiển: web (Project instructions: skills/gpt/WORKER.md)
Giỏi: sửa chi tiết giữ bố cục (tay, ly, chân), viết lại prompt theo template, viết nội dung
Dở: giữ đúng màu/độ bão hòa của style khi tạo ảnh mới; ảnh tạo mới hay lệch style MJ
Đầu vào: ảnh + thẻ việc       Đầu ra: PNG hoặc văn bản, đặt tên theo thẻ việc       Chi phí / tốc độ: 1–2 phút

Luật dùng:
- Sửa ảnh: chỉ đổi đúng chỗ lỗi, giữ nguyên bố cục, màu và ánh sáng.
- Viết prompt: theo template trong `templates/<stage>.txt` của dự án, giữ nguyên câu style.

Runbook:
1. Dán nội dung WORKER.md vào Project instructions một lần.
2. Mỗi việc: dán thẻ việc + đính ảnh `Input`. Tải kết quả, đặt tên theo `Đầu ra`, `aiprod ingest`.

Lỗi hay gặp → cách xử lý:
- Màu nhạt đi sau khi sửa → yêu cầu "giữ nguyên màu gốc", hoặc chỉ dùng vùng sửa.
