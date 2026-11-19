# V28 R2 — kiểm cổng phục hồi và biên nhận ngoài máy

Mốc mã 17/11/2026. Bổ sung cho [V28](V28-VAN-HANH.md); không đổi schema dữ
liệu nghiệp vụ. R2 chưa đóng tất cả cổng nghiệm thu V28 trong lộ trình.

## Biên nhận ngoài máy

`BDSG_OFFSITE_STATUS_FILE` trỏ tới biên nhận ngoài Git/web. Probe chỉ đọc tệp
thường có kích thước giới hạn, không theo liên kết, không gọi mạng và không
đọc chứng thư. Schema phải khớp chính xác, không trùng trường, số phải hữu
hạn; snapshot không được mới hơn lần kiểm hoặc nằm trong tương lai.

`GET /api/node` và `thiet_bi.trang_thai` vẫn chỉ cấp cho chủ quản. Trường
`offsite` trả trạng thái verified/stale/unknown, mốc đo, tuổi bản sao, kích
thước ciphertext và bằng chứng giải mã. Không trả checksum, file ID, vị trí
cấu hình hay tài khoản. Bản sao quá 48 giờ thành stale; tải lại một bản đã cũ
không làm tuổi snapshot trẻ lại. Đây là chính sách hiển thị ngày 17/11/2026,
chưa phải cam kết RPO. Biên nhận không tự chứng minh lịch tải lên tự động.

UI giữ hệ iOS, thêm nhóm Bản sao ngoài máy với lần kiểm, tuổi snapshot và
phân biệt checksum với giải mã. Giữ unknown khi thiếu/sai biên nhận; kết quả
đến trễ không được ghi lên giao diện sau đổi tài khoản hoặc rời ứng dụng.

## Diễn tập cổng trong mạng cô lập

[Harness phục hồi](../trien-khai/van-hanh/V28-KHOI-PHUC-DICH-VU.md) dùng bundle
đã kiểm, phục hồi vào đích mới và khởi động cổng HTTP loopback bằng source đã
chọn. Chế độ thật yêu cầu tiến trình Linux không root, không capability,
NoNewPrivs và chỉ có interface loopback. Người vận hành thiết lập sandbox
trước; harness không tự sửa firewall hoặc namespace của máy đang phục vụ.

Không nạp gateway.env hoặc biến bí mật/proxy từ môi trường cha, không khởi
chạy lịch đã phục hồi. Sau readiness/catalogue và kiểm API từ chối khách,
worker phải dừng sạch. So sánh dữ liệu tệp/dự án, danh tính/quyền và owner tác
vụ trước/sau trong bộ nhớ; chỉ trả boolean/count, không xuất nội dung hoặc
fingerprint của chứng thư. Thay đổi dữ liệu dù số lượng không đổi phải fail.

Kết quả đo là **cổng HTTP từ bản sao**, không gồm tải bản sao, giải mã trên
thiết bị chủ quản, dựng host, TLS/DNS, Office, ClamAV, Google hoặc dịch vụ AI.
Không dùng thời gian này để công bố RTO toàn dịch vụ. Không thử mật khẩu của
người dùng thật; bảo toàn bản ghi danh tính không thay kiểm đăng nhập đầy đủ.

## Đầu nối Drive tùy chọn

[Đầu nối rclone](../trien-khai/van-hanh/V28-GOOGLE-DRIVE-TU-DONG.md) nhận cấu
hình riêng đã được chủ quản cấp, chỉ gửi ciphertext age đến đích allowlist,
không ghi đè/xóa đối tượng cũ và chỉ trả thành công sau khi tải lại so hash.
Không lấy token kết nối Codex. Các kiểm không mạng và CLI thật không thay
nghiệm thu OAuth/upload thật; chưa có cấu hình không được gọi là đã bật lịch.

## Phối hợp thiết bị và việc còn lại

[Quy trình hai máy](../trien-khai/van-hanh/PHOI-HOP-HAI-MAY.md) tách kết nối
thiết bị, Git/worktree, chuyển tệp và hộp thư agent. Không tự đăng ký Mac hoặc
coi mạng LAN chung là quyền truy cập. Mỗi máy có khóa và công việc riêng.

V28 còn cần lịch offsite được nghiệm thu, diễn tập toàn dịch vụ/host, kênh
thông báo sự cố được chủ quản chọn, pilot và chính sách vận hành dài hạn.
Giữ kế hoạch V29–V34, không thay cổng chưa đạt bằng một kiểm thử hẹp hơn.
