# V28 — diễn tập cổng HTTP trên dữ liệu khôi phục

Mốc mã ngày 17/11/2026. Công cụ này khôi phục snapshot vào **đích mới**,
khởi động cổng HTTP trên loopback, kiểm rồi dừng đúng subprocess do nó tạo.
Không thay unit, firewall, dữ liệu hoặc dịch vụ production.

## Phạm vi đã thực hiện

`v28_khoi_phuc_dich_vu.py` dùng lại bộ kiểm manifest/SHA và phục hồi hiện có.
Sau khi đọc toàn vẹn dữ liệu, công cụ chạy `UngDung` cùng mã nguồn được chọn,
gán cổng loopback tự do và kiểm:

- `/api/ready` sẵn sàng; danh mục công khai trả cấu trúc hợp lệ.
- Khách chưa đăng nhập bị từ chối ở API máy chủ và yêu cầu nghiệp vụ.
- Danh tính, phiên, mật khẩu băm, chứng thư agent và quyền thành viên dự án
  còn nguyên; chỉ so sánh băm trong bộ nhớ, không xuất giá trị hoặc băm ra báo cáo.
- Nội dung tệp/phiên bản/dự án, số lượng dữ liệu và chủ sở hữu tác vụ còn nguyên.
- SQLite toàn vẹn sau khi dừng cổng; nguồn snapshot không bị sửa.

Khởi động có thể đánh dấu tác vụ đang chạy là gián đoạn theo hành vi bình
thường của ứng dụng. Công cụ không tự tiếp tục chúng. **Không khởi động lịch**
để tránh thực hiện các tác vụ đã lưu trong bản sao. Việc này được ghi rõ trong
báo cáo, không trình bày như toàn bộ startup production.

Worker nhận lệnh dừng qua stdin riêng; không có endpoint dừng trên HTTP.
Nếu không dừng hợp tác trong thời hạn, công cụ chỉ kill subprocess của mình
và không báo kiểm dừng sạch đạt. Đích phục hồi được giữ lại cho người vận
hành kiểm riêng; công cụ không xóa đích, nguồn hoặc thư mục cha.

## Hai chế độ và điều kiện cô lập

Mặc định `--mode isolated` chỉ chạy trên Linux bằng tài khoản không phải root,
`CapEff` bằng không, `NoNewPrivs=1`, giao diện mạng quan sát được chỉ có `lo`.
Các điều kiện được kiểm trước sao chép và trong worker. Không đọc được trạng
thái hoặc thiếu một điều kiện thì từ chối. Công cụ không tự dựng namespace.

Người vận hành phải cấp một transient unit hoặc sandbox có `PrivateNetwork=yes`,
`NoNewPrivileges=yes`, `CapabilityBoundingSet=` rỗng, source chỉ đọc; không được
mount dữ liệu hoặc cấu hình production vào vùng ghi. Chuẩn bị bản sao đầu vào
đã kiểm trong thư mục riêng cho tài khoản diễn tập. Các tệp khôi phục có quyền
riêng theo bộ restore. Báo cáo riêng của công cụ này không thay schema báo cáo
`recovery.json` hiện có.

Ví dụ phần lệnh trong sandbox đã được chuẩn bị, với đường dẫn riêng do người
vận hành đặt, ngoài Git/web và ngoài thư mục dữ liệu thật:

```text
python3 -B /READ_ONLY_SOURCE/trien-khai/van-hanh/v28_khoi_phuc_dich_vu.py
  --bundle /PRIVATE_RUN/verified-bundle
  --destination /PRIVATE_RUN/restored-new
  --source-root /READ_ONLY_SOURCE
  --mode isolated
```

Đích phải chưa tồn tại, không có liên kết, không nằm trong gói hoặc mã nguồn.
Các vùng `/var/lib/bdsg-thanhhoa`, `/etc/bdsg-thanhhoa`, và
`/srv/bdsg-thanhhoa/open-bdsg` bị cấm làm đích. Luôn truyền đường dẫn release
thực đã xác minh thay vì symlink `current`.

`--mode synthetic` dành cho fixture tổng hợp do người kiểm tạo. Chế độ này
không chứng minh cô lập mạng; báo cáo giữ `isolation_verified=false`. Chỉ nhận
gói có CSDL, không có tệp cấu hình/bí mật và không có lịch. Người vận hành vẫn
chịu trách nhiệm dùng dữ liệu tổng hợp; tên chế độ không tự làm dữ liệu thật
trở thành dữ liệu thử. Không dùng chế độ này để chạy bản sao production.

Environment worker được tạo mới, không kế thừa biến `BDSG_*`, proxy,
`PYTHONPATH` hoặc chứng thư của tiến trình cha. Không tải `gateway.env`, key
Google hay Office từ bản sao vào environment. Secret/config trong gói thật
được phục hồi như dữ liệu riêng và chỉ được thử trong chế độ mạng cô lập.

## Báo cáo và giới hạn phép đo

`run_drill(bundle, destination, source_root, mode, timeout)` trả cặp
`(report, exit_code)`; CLI chỉ in JSON lọc, không trả đường dẫn, nội dung,
exception, token, fingerprint hoặc port. Có thời điểm đo, thời gian phục hồi
dữ liệu, thời gian mở cổng, tổng thời gian, các check và số lượng bản ghi.
Kết quả `ok` chỉ khi tất cả check đạt. Bộ kiểm chỉ gửi GET cục bộ tới worker;
không gọi API AI trả phí hoặc nghiệp vụ ghi của đối tác.

`timeout` là hạn chung cho giai đoạn mở cổng và các lần kiểm HTTP, không nhân
lên theo số endpoint. Dừng hợp tác có hạn riêng; bộ kiểm dữ liệu và đọc lại
SQLite phải được giới hạn thêm bằng thời hạn của transient unit vận hành.

Đây là **phục hồi dữ liệu và cổng HTTP**. Chưa kiểm TLS/Nginx, host/kernel,
DNS, Office engine, ClamAV, LiteLLM/model provider, Google OAuth, MCP đối tác,
khôi phục trên máy vật lý thay thế hoặc toàn bộ luồng đăng nhập của người dùng.
Không gọi thời gian này là RTO toàn host, không suy ra RPO, không đổi
`whole_host_recovery_tested` hoặc `external_services_tested` thành true.

Các bài `thu_v28_khoi_phuc_dich_vu.py` dùng dữ liệu tổng hợp, kiểm subprocess
thật và các trường hợp dữ liệu/quyền bị đổi, cấu hình/lịch ngoài phạm vi,
gói sai SHA, đường dẫn cũ/liên kết, chưa cô lập, lỗi worker và ẩn ngoại lệ.
Kết quả thực tế của snapshot riêng chỉ lưu trong hồ sơ vận hành ngoài Git.
