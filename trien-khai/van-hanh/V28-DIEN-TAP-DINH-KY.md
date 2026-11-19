# V28 — lịch diễn tập phục hồi dữ liệu cục bộ

Phạm vi ngày 17/11/2026: `bdsg-recovery-drill.timer` gọi job lúc 03:30 theo
`Asia/Ho_Chi_Minh`, sau cửa sổ sao lưu 02:30. Lịch có `Persistent=true` nên
có thể chạy bù sau khi máy bật lại. `After=bdsg-backup.service` giữ thứ tự
khi cả hai job cùng đang được khởi động; không tự khởi chạy thêm backup.

## Ranh giới job

CLI `v28_dien_tap_dinh_ky.py` không nhận đường dẫn từ tham số, chỉ chạy bằng
root trên Linux. Chỉ xét thư mục con trực tiếp của
`/var/backups/bdsg-thanhhoa` có tên UTC `YYYYMMDDTHHMMSSZ`. Chọn tên mới
nhất, kiểm SHA/integrity của gói và kiểm tuổi tên lẫn mốc manifest không quá
48 giờ, không ở tương lai. Nếu bản mới nhất hỏng/cũ thì báo lỗi; không lùi
sang bản cũ để tạo trạng thái thành công. Tên không đúng khuôn được bỏ qua;
tên đúng khuôn nhưng ngày không hợp lệ làm job thất bại.

Phục hồi vào thư mục mới trong `TemporaryDirectory` có tiền tố `v28-`, đặt
bên dưới `/var/backups/bdsg-thanhhoa/drills`. Job công bố báo cáo đã lọc rồi
chỉ dọn thư mục tạm của chính lượt này. Không quét/xóa các thư mục diễn tập
khác, không xóa bản sao cũ, không ghi vào kho sống. Một lượt bị tắt đột ngột
có thể để lại thư mục tạm chứa dữ liệu riêng; người vận hành kiểm và xử lý
riêng, job không tự dọn của lượt trước.

Báo cáo `/var/lib/bdsg-thanhhoa-status/recovery.json` đúng schema
`read_status`, thay nguyên tử với sở hữu `root:bdsg-thanhhoa`, quyền `0640`.
Thư mục cha phải là `root:bdsg-thanhhoa`, quyền `0750`, ứng dụng không được
ghi. Job từ chối symlink/junction trong đường dẫn; thư mục backup/drills
phải thuộc người vận hành và không cho nhóm/người khác ghi. Sai đường dẫn,
gói, tuổi hoặc quyền trả báo cáo thất bại đã lọc và mã thoát `1`; nếu không
ghi được báo cáo, trạng thái cũ vẫn giữ mốc cũ và sẽ bị bộ đọc coi là stale.

Job không tạo `UngDung`, không gọi mạng, không khởi động bản khôi phục.
Thời lượng vẫn là kiểm/phục hồi **dữ liệu**, chưa phải RTO trở lại phục vụ.
`service_recovery_tested` và `offsite.configured` giữ `false`. Biên nhận sao
lưu ngoài máy là bằng chứng riêng, không tự gắn vào báo cáo này.

## Cài mẫu sau khi mã nguồn đã vào bản current

Các lệnh sau dành cho người vận hành đã xác nhận đúng máy/thư mục. Không
chạy cài đặt chỉ vì mở tài liệu này. Nhóm dịch vụ phải có sẵn.

```sh
install -d -o root -g root -m 0700 /var/backups/bdsg-thanhhoa/drills
install -d -o root -g bdsg-thanhhoa -m 0750 /var/lib/bdsg-thanhhoa-status
install -o root -g root -m 0644 \
  trien-khai/van-hanh/bdsg-recovery-drill.service \
  /etc/systemd/system/bdsg-recovery-drill.service
install -o root -g root -m 0644 \
  trien-khai/van-hanh/bdsg-recovery-drill.timer \
  /etc/systemd/system/bdsg-recovery-drill.timer
systemd-analyze verify /etc/systemd/system/bdsg-recovery-drill.service \
  /etc/systemd/system/bdsg-recovery-drill.timer
systemctl daemon-reload
systemctl start bdsg-recovery-drill.service
systemctl enable --now bdsg-recovery-drill.timer
systemctl list-timers bdsg-recovery-drill.timer
```

Đặt `BDSG_RECOVERY_STATUS_FILE` của gateway tới tệp trên và bảo đảm sandbox
gateway cho phép đọc thư mục trạng thái. Chỉ phiên web chủ quản được xem.
Trước bật lịch cần kiểm đúng `current/source`, đường dẫn Python/flock, tài
khoản/nhóm, dung lượng và kết quả một lượt thực chạy. Service khóa flock
trong `drills/.lock` để tránh chạy chồng, filesystem strict chỉ mở ghi
drills/status; kho sống và thư mục bí mật bị chặn truy cập. Không ghi bytecode
vào mã phát hành. Không cấp cổng mạng hoặc quyền sửa dữ liệu cho gateway.

## Kiểm thử có thể tái lập

```sh
python3 trien-khai/van-hanh/thu_v28_dien_tap_dinh_ky.py -v
```

Fixture tạo SQLite tổng hợp và hai gói mới trong thư mục tạm; kiểm chọn bản
mới nhất, chặn gói hỏng/tuổi cũ/mốc tương lai/manifest cũ, không sửa nguồn,
chỉ dọn temp sở hữu và công bố schema đã lọc. Kiểm symlink chạy trên Linux;
Windows không có quyền tạo symlink sẽ bỏ qua các ca đó. Kiểm timer/service
và quyền root thực phải chạy trên Linux trước khi coi lịch đã hoạt động.

Nguồn chính thức: [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)
và [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).
