# V28 — tác vụ offsite hằng ngày

Chuẩn bị ngày 17/11/2026. Tác vụ và unit bên cạnh tài liệu này không tự
cài đặt, bật timer hoặc chứng minh upload tự động thật.
Quyết định dùng OAuth riêng cho máy chủ đã có; bước đăng nhập/chấp thuận
Google của chủ quản được hoãn lại. Không dùng token của kết nối Codex.

## Luồng xử lý

`v28_offsite_dinh_ky.py` là CLI root, không nhận tham số. Nó chọn bản sao
timestamp mới nhất qua `select_latest`; tên và manifest phải trong ngưỡng
tươi của bộ chọn, bản mới nhất hỏng không bị bỏ qua để dùng bản cũ. `verify`
kiểm toàn bộ trước khi gọi mã hóa; `encrypt_bundle` kiểm lại và băm từng byte
khi đóng tar qua stdin của age. Không ghi tar rõ xuống đĩa.

Ciphertext mới nằm trong thư mục tạm riêng `v28-offsite-*`, mode `0700`, dưới
staging. Age phải đúng phiên bản `v1.3.2`; chương trình và recipients do quản
trị kiểm nguồn/duyệt trước. Ciphertext chỉ được gửi bằng `upload_age` tới
remote cố định `bdsg-th01`, prefix cố định `daily`, allowlist chính xác
`bdsg-th01:daily`. Đầu nối kiểm remote loại Drive, dùng tên hash + UUID,
không ghi đè, không xóa cloud, kiểm metadata rồi tải lại SHA256 toàn tệp.
Tác vụ đối chiếu hash/kích thước trong receipt với ciphertext vừa tạo.

Sau thành công, receipt công khai chỉ có `format`, `status`, `verified_at`,
`snapshot_at`, `encrypted_sha256`, `encrypted_bytes`, `destination`,
`verification`. Nó được ghi nguyên tử, owner root, group `bdsg-thanhhoa`,
mode `0640`. Chỉ ciphertext được tải lại; receipt này chưa chứng minh giải
mã/khôi phục ứng dụng. Tác vụ không tạo trường công bố lịch tự động đã hoạt
động; phần điều phối/UI chỉ xác nhận sau khi kiểm tra job thật và timer.

Ngay đầu lượt chạy, trước mã hóa hoặc network, tác vụ thay receipt cũ bằng
`status=failed` với lý do cố định đã lọc. Vì vậy crash/timeout giữa chừng không
giữ trạng thái xanh cũ. Reader schema hiện tại trả unknown khi gặp receipt
này. Nếu không ghi được status, job trả lỗi; reader còn có kiểm tuổi snapshot
để receipt cũ không xanh mãi. Không đưa raw exception/OAuth/config path vào
báo cáo. Không giữ thêm bản receipt xanh trước đó trong vùng API.

Cleanup chỉ xóa thư mục ciphertext tạm do lượt này tạo. Bản sao nguồn, các
tệp staging khác và đối tượng cloud không bị xóa. Mất điện/SIGKILL có thể để
lại ciphertext tạm; quản trị kiểm tra và dọn riêng sau đó. Lượt chạy lỗi sau
upload có thể đã để lại ciphertext trên Drive, không tự xóa để rollback.

## Đường dẫn cố định cần chuẩn bị

| Mục | Đường dẫn |
| --- | --- |
| Bản sao đã hoàn tất, chỉ đọc | `/var/backups/bdsg-thanhhoa` |
| Staging root riêng, `0700` | `/var/backups/bdsg-thanhhoa/offsite-staging` |
| Cấu hình OAuth riêng, root `0600` | `/etc/bdsg-thanhhoa-backup/rclone.conf` |
| Dấu xác nhận OAuth đã kiểm, root cấp | `/etc/bdsg-thanhhoa-backup/oauth-ready` |
| Public recipients đã duyệt, root `0600` | `/etc/bdsg-thanhhoa-backup/recipients.txt` |
| Thư mục cấu hình root `0700` | `/etc/bdsg-thanhhoa-backup` |
| age đã xác minh | `/opt/bdsg-age-v1.3.2/age/age` |
| rclone đã xác minh | `/opt/bdsg-rclone-v1.76.0/rclone` |
| Thư mục trạng thái root:bdsg-thanhhoa `0750` | `/var/lib/bdsg-thanhhoa-status` |
| Receipt ứng dụng chỉ đọc | `/var/lib/bdsg-thanhhoa-status/offsite.json` |

Đường dẫn trong bảng là hằng số vận hành, không chứa tài khoản cá nhân.
Không đặt OAuth, khóa riêng age hay thông tin đăng nhập trong Git/web.
Rclone cần quyền cập nhật token trong thư mục cấu hình riêng; ứng dụng
không được đọc thư mục đó. Remote `bdsg-th01` và thư mục `daily` phải tồn tại
trong cấu hình được cấp đúng tài khoản. Module không tự tạo remote, nâng
scope, cài phần mềm hoặc mở trình duyệt đăng nhập. Cấu hình cần hỏi mật khẩu
sẽ thất bại do đầu nối không nhận password command và tắt prompt.

## Unit chuẩn bị để quản trị xét và cài

`bdsg-offsite.timer` đặt `03:10 Asia/Ho_Chi_Minh` hằng ngày sau cửa sổ sao lưu,
`Persistent=true` để chạy bù nếu bỏ lỡ khi máy tắt. `bdsg-offsite.service`
chạy root bằng `flock` chống trùng lượt, chờ network-online và sau backup
service nếu backup cùng được khởi động. `After=` chỉ là thứ tự, không thay
kiểm tính hoàn chỉnh/tươi của snapshot trong mã.

Unit có `ConditionPathExists` yêu cầu dấu `oauth-ready`. Người vận hành chỉ
tạo dấu sau khi kiểm OAuth đúng tài khoản và đúng vùng Drive được cấp. Chưa
có dấu thì service được bỏ qua trước khi đọc cấu hình hoặc thay receipt;
dấu này không thay chứng thư, kiểm cloud thật hay quyết định bật timer.

Service đặt toàn hệ thống chỉ đọc, backup root chỉ đọc và chỉ mở ghi staging,
cấu hình OAuth riêng để refresh, thư mục receipt. Dữ liệu ứng dụng thật và
cấu hình chính bị `InaccessiblePaths` chặn. `/tmp` và `/var/tmp` chỉ đọc;
`TMPDIR` hướng ciphertext tạm của transport về staging. Không dùng plaintext
tar hoặc đường dẫn dữ liệu thật trong pipeline.

Ngân sách Python là 840 giây, thời hạn unit là 900 giây; đây là chính sách
ngày 17/11/2026, chưa phải thời lượng cloud đo được. Budget truyền phần còn
lại cho age và transport; systemd chặn toàn tiến trình kể cả bước kiểm tệp.
`KillMode=control-group` dừng cả tiến trình con khi hết hạn. Không tự động
retry vô hạn. Người vận hành cần đo kích thước thực tế trước khi thay ngân
sách, kiểm unit trên Linux, chạy một job thật rồi mới bật timer và xác nhận
trạng thái tự động. Không có lệnh enable/deploy trong tác vụ này.

## Bằng chứng cục bộ

Ngày 17/11/2026: `python trien-khai/van-hanh/thu_v28_offsite_dinh_ky.py -v`
đạt 6 bài kiểm trên Windows. Fixture dùng bản sao SQLite tổng hợp thật,
`verify` thật, chọn mới nhất/freshness thật và publisher/reader thật; seam
mã hóa/upload chỉ kiểm hợp đồng điều phối, không chứng minh crypto hoặc
Google Drive. Kiểm tra bao gồm receipt sai hash, lỗi adapter có chuỗi nhạy
cảm, config thiếu, bản hỏng/cũ, thu hồi xanh cũ, schema chính xác và cleanup
chỉ tệp riêng. Bằng chứng kiểm unit và triển khai thật được lưu riêng;
kiểm fixture không được dùng để công bố đã bật sao lưu Drive tự động.

Nguồn chính thức: [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)
giải thích `OnCalendar` và `Persistent`;
[systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
giải thích sandbox filesystem và `ReadWritePaths` lồng trong vùng chỉ đọc;
[systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
giải thích timeout oneshot. Chi tiết quyền Drive, rclone và đọc lại xem
[V28-GOOGLE-DRIVE-TU-DONG.md](V28-GOOGLE-DRIVE-TU-DONG.md).
