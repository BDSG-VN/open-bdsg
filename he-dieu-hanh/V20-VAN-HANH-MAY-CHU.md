# V20 — nền vận hành máy chủ

Phạm vi ngày 16/11/2026: hệ điều hành **ứng dụng kinh doanh** chạy trên Linux.
Open BDSG không có kernel, driver hay bộ quản lý phần cứng thay Ubuntu.
Không có chứng nhận ISO/SOC hoặc bằng chứng tương đương một sản phẩm quốc tế.

## Đánh giá từ mã nguồn

Đã có danh tính, chính sách quyền, hạn mức công cụ, nhật ký nhân, dự án,
tác vụ lưu bền, lịch công việc, runtime cô lập, phê duyệt trình duyệt, cộng
tác và Office. Danh mục ứng dụng không chứng minh SSO hoặc liên thông MCP.
Trợ lý cấu hình riêng không phải mô hình riêng đã huấn luyện.

Kho hiện là một gateway Python với worker tác vụ trong cùng tiến trình và
SQLite trên một máy. Worker trình duyệt và Office engine tách riêng. Một máy
hỏng vẫn gây ngừng phục vụ. Thêm dòng mã hoặc đổi nhãn không giải quyết điều đó.

## Nâng cấp đã triển khai trong mã

- `/api/suc-khoe` chỉ báo tiến trình còn trả lời; giữ tương thích khách cũ.
- `/api/ready` kiểm DB có chủ quản, dung lượng trống và luồng lịch khi đã bật;
  lỗi trả HTTP 503. Phản hồi công khai không có đường dẫn hoặc thông tin riêng.
- `/api/system` chỉ phiên web chủ quản: thời gian chạy, số tác vụ theo trạng
  thái, tình trạng cấu hình khả năng. Operator/agent không có quyền xem.
  Trạng thái “configured” không có nghĩa dịch vụ ngoài hoạt động hoặc Google
  đã được cấp quyền. Endpoint không gọi mạng hoặc đọc tài liệu khách hàng.
- Giới hạn kết nối được áp trước khi tạo thread, thời gian chờ socket được
  đặt trước khi đọc header. Quá tải trả HTTP 503/Retry-After, sau đó giải phóng.
- SIGTERM/SIGINT chuyển sang dừng tiếp nhận, dừng lịch, chờ request/worker và
  đóng nhật ký. Callback Office vẫn được phép hoàn tất trước khi ngừng HTTP.
  Giới hạn dừng của systemd vẫn có thể kết thúc tác vụ dài; lần khởi động sau
  đánh dấu gián đoạn theo logic sẵn có, không tự phát lại thao tác bên ngoài.
- CLI sao lưu dùng SQLite Backup API, gói có manifest SHA-256 và integrity_check.
  DB đích độc lập WAL, tệp riêng quyền 0600, thư mục 0700 trên Linux.
  Phục hồi chỉ vào thư mục **chưa tồn tại**, không đè DB vận hành.
- Timer mẫu sao lưu hàng ngày và lệnh khóa flock tránh chạy chồng.

## Vận hành và phục hồi

Sau khi triển khai, kiểm nginx/TLS, cookie, Office, MCP và readiness trước
khi đổi bản phục vụ. Giữ V19 và cấu hình gateway để quay lại, giữ nguyên DB.
Các lệnh sau dành cho tài khoản vận hành, không cung cấp qua web hoặc agent:

```sh
python3 he-dieu-hanh/sao_luu_he_thong.py backup \
  --data /var/lib/bdsg-thanhhoa --secrets-dir /etc/bdsg-thanhhoa \
  --destination /var/backups/bdsg-thanhhoa/TEN-BAN-MOI
python3 he-dieu-hanh/sao_luu_he_thong.py verify \
  --bundle /var/backups/bdsg-thanhhoa/TEN-BAN-MOI
python3 he-dieu-hanh/sao_luu_he_thong.py restore \
  --bundle /var/backups/bdsg-thanhhoa/TEN-BAN-MOI \
  --destination /root/phuc-hoi-thu-MOI
systemctl list-timers bdsg-backup.timer
```

Phục hồi tạo `data/` và `secrets/`; không nạp lại gateway hoặc thi hành env.
Đổi kho thật cần dừng dịch vụ, kiểm bản phục hồi và quyền người dùng/nhóm,
thu hồi phiên/token khi xử lý sự cố, rồi kiểm lại HTTPS và chức năng.
Không khởi tạo `UngDung` trên DB sống để kiểm bản sao: startup có tác dụng
đánh dấu gián đoạn các tác vụ còn chạy.

Gói gồm DB, cấu hình mô hình/đầu nối/đăng ký và các tệp cấu hình dịch vụ trong
danh sách cho phép. Không gồm hệ điều hành, handbook, audit log đang ghi,
cache/volume Office hoặc dữ liệu nền tảng bên ngoài. Các tệp cấu hình được
chép sau DB; tránh sửa cấu hình trong lúc backup để giữ cặp token/vault phù hợp.
SHA phát hiện hỏng/sửa gói, không thay chữ ký mật mã hoặc chứng minh nguồn tin cậy.

Timer giữ bản tại cùng máy, chưa phải khắc phục thảm họa. Chưa có nơi lưu
ngoài máy được chủ quản chỉ định, không tự gửi dữ liệu/bí mật tới bên thứ ba.
Không tự xóa bản cũ. Cần theo dõi lỗi timer, dung lượng, kiểm thử phục hồi định kỳ
và chốt RPO/RTO bằng phép đo thực tế. Không cam kết thời gian chưa đo.

## Các chặng tiếp theo để mở rộng vận hành

1. Adapter HTTP production thay lớp `http.server`, giữ kiểm quyền/cookie/MCP;
   kiểm tải với mục tiêu định lượng trước khi chuyển. Python khuyến cáo không
   dùng `http.server` làm máy chủ production; nginx không thay mọi kiểm bên trong.
2. Tách worker khỏi gateway, lease và hàng đợi bền có đối soát; không tự retry
   thao tác mua hàng/thanh toán hoặc nghiệp vụ ngoài khi chưa có idempotency.
3. PostgreSQL/migration có phiên bản khi cần nhiều máy; bảo đảm cô lập dữ liệu,
   thử failover và tải trước khi cam kết sẵn sàng cao.
4. OIDC/SSO, MFA, vòng đời tài khoản; chỉ kết nối nền tảng thực sự được cấp.
5. Theo dõi lỗi/latency, cảnh báo ngoài máy, backup ngoài máy và diễn tập phục hồi.
6. Đa ngôn ngữ/i18n, múi giờ, khả năng truy cập và nghiệm thu luồng kinh doanh.

## Nguồn kỹ thuật

- [Python HTTP server](https://docs.python.org/3/library/http.server.html)
- [SQLite backup qua Python](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)
- [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)

Các nguồn hướng dẫn kỹ thuật, không cấp chứng nhận cho Open BDSG.
