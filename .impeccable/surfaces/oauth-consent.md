---
version: 1
slug: oauth-consent
primary_target: khong-gian/oauth-consent.html
related_targets: [khong-gian/oauth-consent.js, khong-gian/oauth-consent.css]
---
# Chấp thuận ứng dụng — 18/11/2026

Mode: Operate. Phần mở rộng luồng Tài khoản trong thế giới iOS BDSG đã được
chủ quản chọn. Code-led, không thay PRODUCT.md/DESIGN.md hoặc tài sản nhận diện.

PIN: Chủ quản chốt “Chuyển toàn bộ giao diện theo phong cách iOS” ngày
17/11/2026, ghi tại PRODUCT.md và bề mặt webos-v27.md. Đây là phần bổ sung
đã có mục đích/phạm vi rõ trong Tài khoản; không mở vòng chọn thế giới mới.

OWN-WORLD: Kế thừa chữ hệ thống, hành động xanh, nền xám và nhóm trắng của
Tài khoản BDSG. Không thêm font, palette, minh họa hoặc tài sản Apple.

STORY: Ứng dụng gửi yêu cầu → đăng nhập BDSG → chọn đơn vị → xem client/
phạm vi → tự chọn công cụ/dự án/thời hạn → cho phép hoặc từ chối → quay về
callback đã đăng ký. Context thay đổi chấm dứt biểu mẫu và cần bắt đầu lại.

FORM: Code-led, một cột đọc theo thứ tự quyết định. Không có comp được duyệt
hoặc seed mới cho phần mở rộng này; pin/thế giới đã chốt ở webos-v27.

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
Metadata, quản lý grant/client và SDK tự OAuth đã có trong bản thử. Trang
chấp thuận có profile AI/đọc/lập đề xuất cho công cụ tác vụ; AI mặc định tắt,
công cụ lấy summary đã xác minh theo unit. Không cấp ghi trực tiếp, duyệt
hoặc đối soát. Bỏ công cụ tác vụ hoặc tắt AI phải bỏ lựa chọn mô-đun cũ.
Đổi context xóa cả profile, không giữ grant dưới danh tính hoặc đơn vị mới.

FINISH: Desktop1440/mobile390: login/đơn vị/consent/error/empty/loading/
retry/approve/deny/account/membership/expiry. Chỉ dữ liệu tổng hợp. Kiểm ảnh,
keyboard/focus, overflow, code exchange và không hiện lại dữ liệu sau đổi
context. Detector một lần, reviewer độc lập trước khi nhận bề mặt hoàn tất.
Thêm opt-in/profile reset và SDK qua trang thật approve/deny/stale ở hai kích
thước; kiểm policy đi qua token/worker/provider tổng hợp và đổi revision đầu
nối sau consent làm exchange bị chặn. Không gọi API trả phí hoặc nhận client
ChatGPT/Claude thật đã kết nối.
