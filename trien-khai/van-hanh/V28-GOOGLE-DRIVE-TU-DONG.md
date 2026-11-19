# V28 — đầu nối Google Drive cho ciphertext age

Ngày đối chiếu tài liệu và kiểm thử cục bộ: 17/11/2026. Đây là đầu nối tùy chọn
chưa được cấu hình OAuth trên máy chủ và chưa được chạy upload thật trong phần
việc này. Lượt gửi thủ công qua kết nối Codex không cung cấp thông tin đăng nhập
cho tiến trình máy chủ. Không lấy token của kết nối đó.

`v28_drive_transport.py` nhận tệp `.age` đã tạo bởi bước mã hóa. Quản trị phải
cấp sẵn rclone executable đáng tin, một cấu hình riêng có remote loại `drive`,
thư mục đích đã tồn tại và allowlist chính xác `remote:thu-muc`. Cấu hình và
OAuth nằm ngoài Git, ngoài thư mục web, chỉ tài khoản chạy dịch vụ được đọc/ghi.
Không ghi tài khoản cá nhân, token, đường dẫn máy chủ vào tài liệu công khai.
Không cài rclone, tạo remote, cấp quyền OAuth hay bật lịch từ module này.

Giao diện tích hợp Python:

```python
receipt = upload_age(
    encrypted_file, config=config_file, executable=rclone_binary,
    remote=approved_remote, prefix=approved_folder,
    allowed_destination=approved_destination, timeout=300,
)
```

Các đường dẫn cục bộ phải tuyệt đối, trỏ đến tệp thường và không qua symlink
hoặc junction. Prefix chỉ gồm chữ ASCII, số, `_`, `-` và dấu `/` giữa các đoạn;
không nhận đường dẫn gốc, dấu chấm, connection string hoặc tham số tự do.
Allowlist do cấu hình vận hành tin cậy cấp; truyền cùng một giá trị tùy ý từ
request người dùng vào cả đích và allowlist sẽ làm mất ý nghĩa kiểm soát.

Module kiểm đầu định dạng age, giới hạn ciphertext 8 GiB (chính sách triển khai
ngày 17/11/2026), chụp bản ciphertext riêng, băm SHA256, tạo tên hash + UUID.
Nó kiểm remote bằng `listremotes --name ... --type drive --source file --exact`,
chỉ nhận một remote đúng tên. Yêu cầu rclone hỗ trợ các cờ này; phiên bản cũ
thiếu cờ sẽ thất bại an toàn. Lệnh này chỉ liệt kê tên/loại, không đọc hoặc in
nội dung cấu hình bằng `config dump`.

Trước khi gửi, module liệt kê thư mục và từ chối tên đã có; upload dùng
`copyto --immutable --ignore-existing`; sau đó kiểm đúng một mục với kích
thước khớp và tải lại toàn bộ ciphertext qua `cat`. Chỉ trả biên nhận sau khi
kích thước và SHA256 khớp. Giới hạn đầu ra listing là 1 MiB, readback là kích
thước dự kiến cộng một byte (chính sách ngày 17/11/2026); vượt giới hạn sẽ dừng
tiến trình. Timeout dùng chung cho các lệnh vận chuyển. Stderr bị bỏ, stdin
đóng, không chạy shell, biến môi trường `RCLONE_*` bị loại để tránh ghi đè
remote/credentials, bật log hoặc chạy password command ngoài ý muốn.

Cấu hình mã hóa cần password sẽ thất bại với `--ask-password=false`; module
hiện không nhận password command hoặc mật khẩu. Rclone có thể cập nhật OAuth
trong cấu hình nên tài khoản dịch vụ phải có quyền phù hợp. Tránh nhiều tác
nhân ghi cùng vùng. Kiểm tồn tại rồi ghi không phải giao dịch nguyên tử của
Drive; tên UUID và các cờ bảo vệ giảm va chạm, không phải cơ chế khóa phân tán.
Không có lệnh xóa hoặc rollback cloud: upload lỗi có thể để lại đối tượng cần
quản trị kiểm tra. Lượt chạy lại tạo tên mới và không thay bản trước.

Biên nhận chỉ có trạng thái `verified`, đích `google-drive`, tên đối tượng
sinh máy, hash/kích thước ciphertext, thời điểm đo và phương pháp
`download-sha256`. Không có ID tài khoản, OAuth, file ID, config path hoặc
remote/prefix. `decryption_verified=false` vì đọc lại ciphertext chưa chứng minh
khôi phục được ứng dụng. Biên nhận không tự công bố `automatic=true`: bước
điều phối chỉ được công bố lịch tự động sau khi cấu hình riêng được cấp và
diễn tập thực tế thành công. API/web chỉ nên công bố trường trạng thái đã lọc.

Kiểm thử không mạng:

```text
python trien-khai/van-hanh/thu_v28_drive_transport.py -v
```

Bộ kiểm tra có fake transport và tiến trình Python cục bộ để thử timeout,
mã thoát lỗi, readback quá cỡ, hash sai, metadata sai, đích tồn tại, backend
sai, đường dẫn/allowlist sai và biến môi trường nguy hiểm. Kết quả trên máy
Windows ngày 17/11/2026: 7 bài kiểm tra đạt. Chưa đo throughput, thời gian
cloud hoặc khôi phục giải mã trong phần việc đầu nối này.

## Nguồn chính thức đã đối chiếu

- Google Drive dùng remote `drive:path`; cấu hình đầu tiên cần xác thực trình
  duyệt. Rclone khuyến nghị OAuth client riêng, cảnh báo shared client bị ngừng
  trong năm 2026. [Google Drive backend](https://rclone.org/drive/).
- `listremotes` hỗ trợ lọc chính xác theo tên, loại và nguồn cấu hình; đầu ra
  mặc định là tên remote. [listremotes](https://rclone.org/commands/rclone_listremotes/).
- `copyto` sao chép một tệp và mặc định có thể ghi đè, nên phải thêm bảo vệ.
  [copyto](https://rclone.org/commands/rclone_copyto/).
- `--immutable` cấm sửa tệp đã có; `--ignore-existing` bỏ qua tệp đích đã có.
  Hai cờ không thay thế đọc lại và không tạo giao dịch nguyên tử.
  [Các cờ immutable và ignore-existing](https://rclone.org/docs/#immutable).
- `lsjson` cung cấp metadata máy đọc được, gồm kích thước; `cat` xuất nội dung
  tệp ra stdout. [lsjson](https://rclone.org/commands/rclone_lsjson/),
  [cat](https://rclone.org/commands/rclone_cat/).
- `--config` chọn tệp cấu hình; rclone có biến môi trường thay cờ và cơ chế
  password command; `--ask-password=false` tránh lời nhắc mật khẩu.
  [Cấu hình và mật khẩu](https://rclone.org/docs/#configuration-encryption).
