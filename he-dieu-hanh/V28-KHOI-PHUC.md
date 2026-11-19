# V28 — diễn tập phục hồi và trạng thái chỉ đọc

Phạm vi ngày 17/11/2026: diễn tập cục bộ từ gói V20 đã có, vào thư mục chưa
tồn tại. Không chuyển dữ liệu phục vụ, chạy env đã khôi phục, khởi tạo
`UngDung` trên bản sao hoặc thay đổi dịch vụ đang hoạt động.

## Phép đo và giới hạn

`kiem_tra_khoi_phuc.py` dùng kiểm SHA-256 và SQLite integrity của V20 trước
khi phục hồi; sau chép kiểm lại kích thước, SHA và integrity của bản phục hồi.
Đếm các bảng thật `office_files`, `office_versions`, `du_an`,
`cong_viec_tasks`; so khớp với bản sao nguồn. Bảng chưa có được ghi `null`,
không tự diễn giải là không có dữ liệu. `database_user_version` là giá trị
`PRAGMA user_version`, không phải số phiên bản phát hành ứng dụng.

`restore_duration_seconds` đo toàn bộ bước kiểm gói, chép và kiểm bản phục hồi
bằng đồng hồ đơn điệu. Đây là thời gian **diễn tập phục hồi dữ liệu**, chưa
phải RTO trở lại phục vụ đầy đủ: `service_recovery_tested` luôn `false`.
`backup_age_seconds` đo chênh lệch từ `created_utc` trong manifest tới thời
điểm quan sát. Manifest V20 ghi thời điểm hoàn tất tạo gói; phép đo không
chứng minh thời điểm giao dịch cuối, tính nhất quán của mọi cấu hình riêng
hoặc lượng dữ liệu tối đa mất khi có sự cố. Vì vậy `rpo_basis` luôn
`snapshot_age_only`, không phải cam kết RPO.

Gói hỏng, manifest sai, đồng hồ gói ở tương lai, đích đã tồn tại hoặc đích
nằm trong gói đều bị từ chối. Không tự xóa gói/đích sau lỗi; giữ lại để điều
tra cục bộ. SHA phát hiện sai khác, không thay nguồn tin cậy/chữ ký.
`offsite.configured` luôn `false`: chưa có nơi lưu ngoài máy được xác minh.

## Diễn tập tổng hợp trước khi dùng bản sao vận hành

Chạy từ gốc kho, bằng Python 3.11 trở lên. Các đường dẫn dưới là ví dụ do
người vận hành chọn; không dùng lại thư mục đã tồn tại.

```sh
umask 077
DIEN_TAP=$(mktemp -d /tmp/bdsg-v28-synthetic.XXXXXX)
python3 trien-khai/van-hanh/v28_dien_tap_tong_hop.py \
  --workspace "$DIEN_TAP/drill" > "$DIEN_TAP/evidence.json"
python3 he-dieu-hanh/thu_kiem_tra_khoi_phuc.py -v
```

Fixture tạo SQLite tổng hợp mới, sao lưu, phục hồi, đo thời gian; chứng minh
gói bị sửa bị chặn và đích đã có bị từ chối. Bằng chứng JSON chỉ chứa số lượng,
thời gian và kết quả kiểm tra. CSDL fixture có bảng tối thiểu để thử định dạng
gói; không chứng minh toàn bộ luồng đăng nhập, Office, worker hay MCP.
Không dùng dữ liệu khách hàng, khóa, tệp môi trường hoặc gọi mạng.

## Diễn tập bằng một gói vận hành đã được duyệt

Chạy bởi người vận hành có quyền đọc gói riêng; bản phục hồi chứa bí mật và
phải ở ngoài Git, web root và thư mục mà gateway có thể duyệt/tải.

```sh
python3 he-dieu-hanh/kiem_tra_khoi_phuc.py \
  --bundle /var/backups/bdsg-thanhhoa/BAN-SAO-DA-CHON \
  --destination /root/bdsg-drill-DICH-MOI \
  --status-file /root/bdsg-drill-status.json
```

Mã thoát `0` là đã kiểm và phục hồi dữ liệu thành công; `1` là không thành
công. stdout luôn là báo cáo đã lọc; không in ngoại lệ chứa đường dẫn hoặc
nội dung. Tệp trạng thái ghi nguyên tử, quyền `0600`. Nếu lưu trạng thái thất
bại, mã thoát là `1` dù thư mục phục hồi có thể đã được tạo.

Không tự chọn gói mới nhất khi timer đang ghi dở. Chọn gói hoàn chỉnh sau
`verify`, tránh sửa cấu hình khi sao lưu và kiểm nguồn timer đang dùng đúng
mã phát hành hiện tại. Bộ kiểm không tự thay timer hoặc tự xóa bản cũ.

## Đưa trạng thái đã lọc vào trang chủ quản

`read_status(path, now=None, max_age_seconds=172800)` là bộ đọc chỉ đọc.
Đường dẫn do cấu hình máy chủ kiểm soát; không nhận từ URL/yêu cầu người dùng.
Schema chính xác gồm mốc đo, tuổi bản sao/phục hồi, thời lượng, trạng thái,
integrity, số lượng, `database_user_version`, `restored_files`, `rpo_basis`,
`service_recovery_tested`, `offsite`. Không có tên tệp, manifest, SHA, đường
dẫn, khóa, nhật ký hay nội dung. Khóa ngoài schema, kiểu sai, symlink, JSON
lớn hơn 16 KiB hoặc mốc tương lai trả `unknown`; báo cáo quá 48 giờ mặc định
trả `unknown/stale`. Tuổi hiện tại được tính lại từ mốc gốc, không đổi mốc đo.

Người vận hành chỉ công bố **báo cáo đã lọc**, không công bố cả gói. Có thể
chép báo cáo đã kiểm vào thư mục trạng thái riêng của dịch vụ với chủ sở hữu
`root`, nhóm dịch vụ và quyền `0640`; thư mục cha không cho tài khoản dịch vụ
ghi. Cấu hình gateway `BDSG_RECOVERY_STATUS_FILE` trỏ tới bản đã lọc đó.
Đảm bảo sandbox systemd cho phép đọc thư mục này. Báo cáo chỉ đưa cho phiên
web chủ quản, không mở endpoint phục hồi hoặc tải gói qua HTTP/MCP.

Staging ứng dụng đầy đủ là bước nghiệm thu riêng: dựng môi trường cô lập,
vô hiệu mạng/nhà cung cấp ngoài, cấu hình danh tính thử, kiểm đăng nhập,
dự án/tác vụ/Office rồi mới diễn tập chuyển dịch vụ có kế hoạch. Chưa thực
hiện bước đó thì giữ `service_recovery_tested: false` và không hứa RTO.
