# V25 — đăng ký Google công khai, 17/11/2026

Chủ quản yêu cầu mở đăng nhập Google công khai. Chế độ `public` cho phép tài
khoản Google có email đã xác minh tự tạo tài khoản BDSG, không cần lời mời.
Tài khoản mới chỉ có quyền `operator`, dữ liệu riêng theo người dùng. Định danh
vẫn theo issuer/sub, không ghép vào tài khoản có sẵn hay cấp quản trị theo email.

## Cấu hình

Tệp riêng `BDSG_GOOGLE_LOGIN_FILE` có thể đặt:

```json
{"registration":"public","allowed_emails":[],"max_accounts":1000}
```

`registration` chỉ nhận `public` hoặc `invite-only`; khi không khai báo vẫn
giữ chế độ lời mời V24. Cấu hình cũ `allowed_emails` tiếp tục dùng được.
`max_accounts` là số danh tính Google tối đa, mặc định 1000 ở chế độ public,
100 ở chế độ lời mời; nhận số nguyên 1–100000. Chạm trần chỉ chặn đăng ký mới,
không chặn tài khoản đang hoạt động đăng nhập lại. Cấu hình sai không bật Google.

Đây là giới hạn tiếp nhận tài khoản, tách biệt với trần AI. Các mức tài trợ,
token và ngân sách BDSG đã cấu hình không đổi; Google không cấp tín dụng API.

## Ranh giới quyền

- Vẫn kiểm chữ ký token Google, issuer/audience/thời hạn, nonce, state một
  lần, PKCE, cookie ràng buộc và `email_verified`.
- Public chấp nhận cả tài khoản Google dùng email ngoài Gmail/Workspace.
  Email không quyết định quyền hay liên kết tài khoản. Chế độ lời mời vẫn
  yêu cầu email mà Google có thẩm quyền xác nhận như V24.
- Danh tính đã thu hồi không tự được tạo lại. Tài khoản chủ quản và đăng nhập
  mật khẩu hiện tại không thay đổi.
- Danh bạ của người dùng Google chỉ có chính họ và các agent đang hoạt động;
  không liệt kê hồ sơ nhân viên hoặc người dùng Google khác. Nhân viên nội bộ
  và chủ quản giữ danh bạ trước đây. Dự án và cấu hình AI giữ chính sách quyền.
- Chỉ xin `openid email profile`, không yêu cầu quyền Drive. Luồng Google
  Office và các ứng dụng khác không đổi.

Google mô tả ngoại lệ cho phạm vi danh tính cơ bản: người dùng không cần nằm
trong danh sách test users để dùng chỉ `openid email profile`. Đây không phải
tuyên bố dự án đã được Google xác minh thương hiệu hoặc cấp quyền Drive công
khai. Xem [trạng thái OAuth](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).

## Kiểm chứng

Các bài kiểm mới đi qua giao diện xác thực và nhân: người chưa được mời tạo
operator, tài khoản Google bên ngoài Gmail, hạn tiếp nhận, email chưa xác minh,
thu hồi, cấu hình sai và ngăn đọc danh bạ/dự án người khác. Giữ các kiểm thử
V24 cho token RSA, cookie, dùng lại state, PKCE và đăng nhập mật khẩu.

Triển khai phải giữ snapshot và cả chính sách Google trước khi mở public;
rollback mã phải phục hồi chính sách cũ tương ứng.

Ngày 17/11/2026: 239 bài lõi trên Linux, 224 đạt và 15 bỏ qua theo môi trường;
15 bài Google bao gồm kiểm chữ ký RSA thật với dữ liệu tổng hợp. 4 bài đóng gói
đạt. UI public desktop1440/mobile390 kiểm tạo tài khoản từ danh tính tổng hợp
không trong danh sách mời, chờ/lỗi/hủy/thử lại, từ chối quản trị và mật khẩu cũ.
Finish review SHIP; ảnh production1920/mobile390 cũng đã được đối chiếu.

Đã bật public trên Thanh Hoá với danh sách mời rỗng và đăng nhập Google thật
thành công bằng tài khoản hiện có. Lượt tạo người dùng mới ngoài danh sách
được kiểm bằng fixture; không khẳng định đã thử nhiều tài khoản Google thật.
Đã snapshot trước/sau, thử restore chính sách public và giữ rollback phục hồi
cả mã/chính sách cũ. Rollback cũng đóng các phiên Google để chính sách lời mời
cũ không bị vượt qua bằng một phiên công khai còn hiệu lực.
