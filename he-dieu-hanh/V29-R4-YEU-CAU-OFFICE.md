# V29 R4 — yêu cầu và phiên tải Office theo đơn vị

Ngày 17/11/2026. Tiếp nối [V29 R3](V29-R3-HTTP-VA-TAC-VU.md).
Đây là backend thử nghiệm trên dữ liệu tổng hợp; đơn vị vẫn chưa bật trên
website production. Không chạy chuyển đổi dữ liệu thật ở bản này.

Mã yêu cầu tạo tệp và bắt đầu tải được phân biệt theo danh tính và đơn vị đang
làm việc. Một người dùng cùng mã ở hai đơn vị tạo hai yêu cầu độc lập. Thử lại
trong cùng đơn vị trả về đúng tệp/phiên cũ; thay tham số bị báo xung đột.

Phiên tải có phạm vi riêng. Chia sẻ dự án cho người dùng ở đơn vị khác cho
phép đọc hoặc sửa tệp theo quyền đã cấp, nhưng không cấp quyền dùng phiên tải
của đơn vị nguồn. Trạng thái, danh sách, ghi phần, hoàn tất và hủy đều kiểm
phạm vi. Hạn mức phiên chờ tính theo danh tính và đơn vị; trần dung lượng máy
chủ vẫn dùng chung. Sau quét, quyền và phạm vi được kiểm lại trước khi lưu.

Hai bảng metadata `office_request_units` và `office_upload_units` được bổ sung
trong chế độ thử nghiệm đơn vị. Bảng legacy giữ nguyên số cột. Snapshot SQLite
giữ cả metadata này; bộ dấu kiểm phục hồi cũng bao gồm chúng. Kiểm phục hồi
Office bằng dữ liệu tổng hợp chưa là chứng nhận phục hồi HTTP toàn hệ thống đa
đơn vị hoặc phục hồi toàn máy chủ.

## Dữ liệu cũ

Yêu cầu hoặc phiên cũ thiếu phân loại đơn vị bị chặn. Hàm
`chuyen_yeu_cau_office_don_vi.migrate_legacy(office, actor, copy_only=True)`
chỉ dành cho bản sao được người vận hành xác nhận. Cần chủ quản hệ thống đã
xác thực, marker chuyển dự án `projects-v1` và nguồn một đơn vị legacy rõ
ràng. Không tự suy đơn vị đang làm việc từ dự án đã chia sẻ. Nguồn đã có đơn vị
khác, danh tính không còn hợp lệ hoặc dữ liệu mồ côi cần được đối soát riêng.
Chạy lại kiểm nhất quán trước khi chấp nhận marker; mọi thay đổi cùng giao dịch.
Nguồn một đơn vị có cả yêu cầu legacy và yêu cầu đã phân loại được xử lý cùng
nhau: giữ ánh xạ hợp lệ, chỉ chuyển phần còn thiếu. Kiểm ánh xạ đối chiếu cả
loại yêu cầu, danh tính, đơn vị, mã ngoài và khóa nội bộ; ánh xạ sai bị từ chối.

## Kiểm tra

Từ gốc kho, dùng Python 3.11 trở lên:

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_yeu_cau_office_don_vi.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_don_vi_http.py' -v
```

Kiểm bằng SQLite tạm và nội dung tổng hợp, không gọi mô hình trả phí. Các bài
bao phủ retry/xung đột, chia sẻ dự án, sai đơn vị, tranh chấp ghi, hủy hoặc mất
quyền lúc quét, restart, sao lưu/phục hồi và chuyển legacy. Cổng HTTP thử nghiệm
vẫn chặn các đường chưa chuyển đổi như Google, callback soạn thảo và MCP.

Bản này chưa hoàn tất phân vùng editor/cộng tác, Google vault, cấu hình AI,
ngân sách, đầu nối và giao diện chọn đơn vị. Mặc định gateway production tiếp
tục vận hành không gian hiện có và từ chối khởi động trên kho đã có đơn vị.
