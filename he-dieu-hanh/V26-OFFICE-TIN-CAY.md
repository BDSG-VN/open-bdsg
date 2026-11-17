# V26 — kiểm chứng phản hồi Office và Google

Đo ngày **17/11/2026**, tiếp nối [V19](V19-OFFICE-ENGINE.md). Phạm vi này
hoàn thiện xử lý lỗi trong phần BDSG tự quản lý, không thay đổi quyền hoặc
tự mở thêm phạm vi Google.

## Thay đổi

- Xuất Drive chỉ báo hoàn tất khi phản hồi tải lên xác nhận đúng ID đã cấp,
  áp dụng cả multipart và resumable. HTTP thành công nhưng thiếu/sai ID hoặc
  JSON lỗi giữ ledger `pending`. Lần thử lại tiếp tục đối soát ID và checksum
  trước khi gửi lại; không tạo một bản sao mới chỉ vì mất phản hồi.
- Khi đối soát, ID, kích thước và checksum đều phải khớp. Phản hồi OAuth sai
  kiểu, token trống hoặc không dùng được trong header bị từ chối trước lưu.
- Phản hồi JSON không phải object trở thành lỗi Google có kiểm soát, không
  đưa nội dung phản hồi thô ra giao diện. Danh sách Drive kiểm kiểu dữ liệu và
  chỉ trả các trường metadata đã khai báo. Metadata nhập lỗi bị chặn trước
  tải nội dung hoặc tạo tệp BDSG.
- Máy kiểm không có Unix socket báo bộ quét chưa sẵn sàng và chặn xuất bản;
  không phát sinh AttributeError hay báo tệp sạch. Linux vẫn dùng clamd Unix
  socket như trước.

## Bằng chứng tái lập

Chạy riêng từng lệnh từ gốc kho, ngày **17/11/2026** trên Windows Python của
Codex: tổng **37** bài đạt, không gọi Google thật hay API tính phí.

```sh
python he-dieu-hanh/thu_google_office.py -v
python he-dieu-hanh/thu_van_phong.py -v
python he-dieu-hanh/thu_office_tich_hop.py -v
python he-dieu-hanh/thu_quet_virus.py -v
```

Theo thứ tự: **12**, **11**, **13**, **1** bài đạt. Đã chạy bài hồi quy mới
trước sửa: phản hồi tải lên sai vẫn bị đánh dấu thành công và OAuth sai kiểu
gây lỗi ngoài hợp đồng; sau sửa các trường hợp này đều bị từ chối đúng.
Phần triển khai và hồi quy Linux được ghi trong báo cáo phát hành chung V26.

## Phần chờ tích hợp thật

Đăng nhập Google công khai V25 chỉ dùng danh tính cơ bản. Nó không nghiệm thu
thay cho OAuth `drive.file`, Picker, import/export, refresh và revoke của
Google Office. Các luồng này còn cần cấu hình Google Cloud/Picker phù hợp và
chủ tài khoản cấp quyền, sau đó nghiệm thu bằng tệp thử riêng. Kiểm tổng hợp
trong bản này không được diễn giải thành đã chạy thật trên Drive.

Office Community vẫn có giới hạn chỉnh sửa trên điện thoại, tệp tối đa 8 MiB
theo V19; không tuyên bố tương đương toàn bộ Word/Excel/PowerPoint hoặc đồng
bộ hai chiều. Bộ quét không bảo đảm phát hiện mọi mã độc.
