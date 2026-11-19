# V24 — đăng nhập Google, 17/11/2026

Thêm “Tiếp tục với Google” trong hộp đăng nhập. Đăng nhập bằng mật khẩu vẫn
hoạt động. Đây là xác thực danh tính bằng OpenID Connect, độc lập với kết nối
Google Drive/Office; chỉ xin `openid email profile`, không xin quyền Drive,
không lưu access token, refresh token hoặc ID token Google sau khi đăng nhập.

## Cấu hình riêng

Cài phần tùy chọn bằng `python -m pip install -r requirements-google-login.txt`.
Lõi vẫn chạy khi chưa cài: lựa chọn Google không hiện và endpoint báo chưa
cấu hình. Không sửa interpreter hoặc môi trường của các ứng dụng khác.

- `BDSG_GOOGLE_CLIENT_FILE`: JSON OAuth Web client, có client ID, secret và
  redirect URI đã đăng ký `https://<ten-mien>/api/google/callback`.
- `BDSG_GOOGLE_LOGIN_FILE`: JSON riêng `{"allowed_emails":["tester@example.test"]}`.
  Chỉ địa chỉ được mời mới có thể đăng nhập. Ví dụ này là dữ liệu tổng hợp.
- Giữ hai tệp ngoài Git và web, quyền 0600. Khởi động lại gateway sau khi đổi
  cấu hình. Snapshot đã đưa `google-login.json` vào nhóm cấu hình riêng.

Cùng callback được dùng với Google Office: state `login.` thuộc luồng đăng
nhập, cookie riêng `bdsg_google_login`; state Office và cookie cũ không đổi.
Không ghi query callback vào access log. Bản nginx đang triển khai đã tắt log
callback; cấu hình tương đương phải giữ điều kiện này khi tự vận hành.

## Danh tính và quyền

Authorization Code dùng PKCE S256, state và cookie ràng buộc trình duyệt,
nonce, thời hạn 10 phút và state dùng một lần. `google-auth` kiểm chữ ký,
issuer, audience và thời hạn token; BDSG kiểm thêm nonce, presenter và email
đã xác minh. Email ngoài Gmail cần thuộc Workspace do Google quản lý.

Sau lời mời ban đầu, danh tính lưu theo issuer/sub của Google. Tài khoản mới
chỉ có vai `operator`; không liên kết với tài khoản mật khẩu hoặc chủ quản
chỉ vì trùng email. Thu hồi agent trong BDSG chặn đăng nhập lại và không tự
tạo lại danh tính đã thu hồi. Không có đăng ký Google công khai hay giao
diện quản lý lời mời trong bản này.

Phiên BDSG dùng cùng cơ chế với đăng nhập mật khẩu: token ngẫu nhiên băm trong
SQLite, cookie Secure/HttpOnly/SameSite=Strict, 8 giờ. Chỉ cookie ràng buộc
callback dùng SameSite=Lax. API nghiệp vụ vẫn qua nhân và chính sách quyền cũ.
Hạn mức AI tính theo người dùng BDSG; Google không tự cấp tín dụng API.

## Nghiệm thu

Ngày 17/11/2026: 11 bài kiểm riêng đạt, gồm token RSA ký thật bằng khóa tổng
hợp, sai chữ ký/audience/issuer/thời hạn/nonce, sai trình duyệt, dùng lại
state, callback đồng thời, chưa được mời, thu hồi, giới hạn bắt đầu và cookie.
Trong 235 bài lõi: 220 đạt, 15 bỏ qua theo môi trường. Kiểm UI fixture desktop
1440/mobile 390 đạt chờ/lỗi/hủy/thử lại, phiên operator, từ chối quản trị và
đăng nhập mật khẩu chủ quản. Fixture không thay thế đăng nhập Google thật.

Cùng ngày đã đăng nhập Google thật bằng tài khoản được mời trên hồ sơ Chrome
Thanh Hoá: chọn đúng tài khoản, Google chỉ yêu cầu thông tin hồ sơ/email,
callback tạo phiên operator và trở về trang giao việc với đúng tên người dùng.
Google Office và tài khoản chủ quản không bị thay đổi. UI finish review đã
chấm finding thông báo lỗi resolved và trả disposition ship.

Không ghi khóa, code hoặc phản hồi nhà cung cấp vào thông báo lỗi. Không đưa
danh tính Google hay ảnh tài khoản người dùng thật vào kho mã nguồn.
