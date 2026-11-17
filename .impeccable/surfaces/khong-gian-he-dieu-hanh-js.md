---
version: 1
slug: "khong-gian-he-dieu-hanh-js"
primary_target: "khong-gian/he-dieu-hanh.js"
related_targets: ["khong-gian/don-vi-ui.js","khong-gian/don-vi-ui.css","khong-gian/don-vi.js","khong-gian/ung-dung.js"]
---

# Đơn vị làm việc trong BDSG OS — 17/11/2026

Mode: Operate. Local extension của vỏ iOS đã được chủ quản chốt. Không thay
thế PRODUCT.md, DESIGN.md hoặc thế giới thị giác, không mở vòng chọn concept.

THESIS: Người dùng biết đang làm việc cho đơn vị nào, đổi đơn vị rõ ràng và
không nhìn thấy hoặc tiếp tục gửi dữ liệu của đơn vị trước trong ngữ cảnh mới.

OWN-WORLD: Giữ kiểu chữ hệ thống, bề mặt sáng, hành động xanh, nhóm bo góc và
hệ SVG BDSG. Thanh chọn dùng select có label, bố cục nhẹ dưới thanh trạng thái;
không nhồi tên dài vào hàng tài khoản trên điện thoại. Legacy không có thanh này.

STORY: Đăng nhập → lấy đơn vị có membership thật → chọn đơn vị → mở dự án,
Office hoặc AI → đổi đơn vị có cảnh báo nội dung chưa lưu khi có cửa sổ → đóng
ngữ cảnh cũ và làm việc trong đơn vị mới. Thu hồi quyền buộc xóa giao diện cũ.
Không có đơn vị: giải thích cách được cấp quyền; owner có tạo đơn vị bằng tên
và tài khoản admin được nhập rõ. Không cấp quyền nội dung tự động cho creator.

FIRST VIEWPORT: Desktop1440 và mobile390 giữ Home/Dock hiện tại. Trong unitmode,
thấy ngay tên đơn vị/select, vai thực và trạng thái tải/lỗi/thử lại. Select min
44px, label đọc được14px trở lên, tên dài không đẩy ngang viewport. App chưa
hỗ trợ đơn vị vẫn được nhận diện là chưa sẵn sàng và không mở bằng deeplink.

SIGNATURE: Cùng danh tính nhưng đổi unit hoặc epoch/revision là một ngữ cảnh
mới: remount iframe, reset broker, chặn kết quả async cũ, window metadata theo
scope. Các thẻ trình duyệt độc lập chọn unit riêng; account logout vẫn lan như
trước. Giữ focus chọn đơn vị sau thao tác, giảm motion theo cài đặt đang có.

FORM: code-led, seed: none (pinned). Canonical reference: DESIGN.md và
PRODUCT.md, Brand Commitments, ghi nhận quyết định chủ quản ngày 17/11/2026:
“Chuyển toàn bộ giao diện theo phong cách iOS”. Đây là bằng chứng pin thế giới
thị giác. Home/Dock là bề mặt hiện có được giữ theo quy tắc mở rộng cục bộ,
không có trích dẫn riêng của chủ quản pin bố cục Home/Dock; không nhận đó là
một quyết định mới đã được chủ quản duyệt. Không comp hay raster
shipping mới. Incumbent visual truth là ảnh Home iOS production R6 desktop/mobile
ở outputs/BDSG-V29-R6/bdsg-v29r6-live. Ambition là độ rõ và đúng của thao tác,
không trang trí mới hoặc hứa mọi module đã liên thông.

FINISH: Browser desktop/mobile các trạng thái guest/no-unit/selected/unit-switch/
confirmation-cancel/error/retry/revocation/rolechange; có real project/task/file
theo dữ liệu tổng hợp, actor giống nhau A/B, phản hồi đến muộn và reload. Kiểm
keyboard/contrast/overflow, legacy Home không đổi. Detector một lần trên đích
đã sửa, reviewer độc lập chấm từ ảnh và bằng chứng chức năng. Preserve DESIGN.md
và PRODUCT.md, ghi nhận drift có sẵn thay vì tự sửa hệ thống.
