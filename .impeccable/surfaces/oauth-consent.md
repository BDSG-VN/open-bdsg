---
version: 1
slug: oauth-consent
primary_target: khong-gian/oauth-consent.html
related_targets: [khong-gian/oauth-consent.js, khong-gian/oauth-consent.css]
---
# Chấp thuận ứng dụng — 17/11/2026

Mode: Operate. Phần mở rộng luồng Tài khoản trong thế giới iOS BDSG đã được
chủ quản chọn. Code-led, không thay PRODUCT.md/DESIGN.md hoặc tài sản nhận diện.

THESIS: Người dùng nhìn đúng tài khoản/đơn vị/client rồi tự chọn công cụ và
dự án trước khi cấp quyền có thời hạn. Không chọn sẵn hoặc ngầm cấp tất cả.

FIRST VIEWPORT: Tiêu đề hành động và trạng thái thật; chưa đăng nhập có form
BDSG, đã đăng nhập có đơn vị, đã bind có client/tài khoản/đơn vị trước danh
sách quyền. Nhóm trắng trên nền xám hệ thống, chữ hệ thống và hành động xanh
như Tài khoản hiện có. Desktop tập trung theo cột đọc, mobile một cột.

SIGNATURE: Quyền thay đổi giữa lúc duyệt làm mất toàn bộ biểu mẫu cũ; không
giữ các lựa chọn dưới tài khoản hoặc đơn vị mới. Nút duyệt không tự gửi lại
khi chưa rõ kết quả. Chấp thuận trả code thật cho callback đã đăng ký.

CONSTRAINTS: Nonce ở fragment, không có mật khẩu/token trong lưu trữ trình
duyệt hoặc log. Cookie/identity/unit và snapshot quyền được backend kiểm.
Chưa quảng bá metadata, chưa có trang quản lý grant/client hoặc SDK tự OAuth.
Profile công việc của trang này chưa cấp AI/đọc/ghi nền tảng ngoài; các khả
năng đó vẫn còn trong phạm vi đầy đủ R11 và sẽ có bề mặt cấp rõ tương ứng.

FINISH: Desktop1440/mobile390: login/đơn vị/consent/error/empty/loading/
retry/approve/deny/account/membership/expiry. Chỉ dữ liệu tổng hợp. Kiểm ảnh,
keyboard/focus, overflow, code exchange và không hiện lại dữ liệu sau đổi
context. Detector một lần, reviewer độc lập trước khi nhận bề mặt hoàn tất.
