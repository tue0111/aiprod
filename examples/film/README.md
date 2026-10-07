# Ví dụ: phim montage anime 36 shot

Nhập dự án phim có sẵn (chỉ đọc), tự tính crop, dựng lại và so với bản dựng tay `rough_cut_v4_preview.mp4`.

```bash
aiprod import E:/Film D:/film-aiprod --pack video --picks examples/film/picks_v4.yaml
aiprod -C D:/film-aiprod plan
aiprod -C D:/film-aiprod qa all video      # crop 16:9 + contact sheet từng clip
aiprod -C D:/film-aiprod assemble          # renders/rough.mp4 (39,33s, 1180 khung)
aiprod -C D:/film-aiprod deliver           # renders/rough_preview.mp4 < 30 MB
python examples/film/compare.py D:/film-aiprod D:/film-aiprod/renders/rough.mp4 E:/Film/renders/rough_cut_v4_preview.mp4
```

Kết quả lần chạy 07/10/2026: 36/36 shot khớp (sai khác trung bình khung đầu và khung giữa ≤ 3,7/255; dùng sai take cho 44–48). Crop tự tính trùng crop đã dùng: H01/H02 `1840:1036:40:26`, H03 `1876:1056:22:16`, E01 `1764:992:78:48`, còn lại `1920:1080:0:4`.

`picks_v4.yaml` ghi clip đã chọn, khung bắt đầu và hiệu ứng cuối shot. Ghi chú trong file giải thích chỗ lệch với script cũ (D08, D11).
