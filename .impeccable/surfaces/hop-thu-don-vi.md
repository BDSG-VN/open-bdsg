---
version: 1
slug: hop-thu-don-vi
primary_target: khong-gian/hop-thu-ui.js
related_targets: [khong-gian/hop-thu-ui.css, khong-gian/ung-dung.js]
---
# Thông điệp trong đơn vị — 18/11/2026

Mode: Operate. Mở rộng bề mặt Thông điệp trong webOS iOS đã được chủ quản
chọn. Giữ PRODUCT.md/DESIGN.md và bố cục danh bạ cạnh hội thoại hiện có;
không tạo thế giới thị giác, comp hoặc vòng chọn phong cách mới.

THESIS: Chọn thành viên, đọc đúng hội thoại và gửi lời nhắn trong đơn vị
hiện hành. Root/admin không có hộp thư giám sát; nhãn thành viên không có
nghĩa là một mô hình AI đã chạy.

OWN-WORLD: Hệ chữ hệ thống, nền #f2f2f7, nhóm trắng, hành động #0067dc,
focus/selection cùng màu, bo góc 12–16px. Không tài sản Apple hoặc ảnh mới.

STORY: Danh bạ → hội thoại → bản nháp → gửi → đọc lại hộp thư. Mất phản hồi
sau ghi phải làm mới để kiểm tra, không tự gửi lại. Ghi chú cho mình là cặp
đích danh, không trộn với toàn hộp thư.

FIRST VIEWPORT: Desktop1440 có tiêu đề/ngữ cảnh đơn vị, làm mới, hai vùng
danh bạ và hội thoại; mobile390 xếp dọc, danh bạ có giới hạn cuộn, nội dung
thư dài và người nhận dài không làm tràn ngang. Composer có nhãn rõ ràng.

SIGNATURE: Unit/account/membership hoặc cửa sổ ẩn xóa thư và bản nháp ngay.
Khi mở lại phải xác minh dữ liệu; không giữ nội dung qua một phạm vi mới.
Giữ phản hồi thật sau commit để chứng minh guard thế hệ, kể cả transport
không tôn trọng abort. Lỗi đọc không được hiển thị thư cũ hoặc giả empty.

FORM: code-led, kế thừa webos-v27. Seed reference dc2c02cf28665d7e,
assignment index3, mode Operate; đây là seed kế thừa, không roll mới. Pin
iOS do chủ quản chọn giữ toàn quyền. Không comp, raster hoặc DESIGN change.

FINISH: Chrome HTTPS gateway/SQLite/cookie thật, dữ liệu tổng hợp1440/390.
28 tình huống gồm loading/empty/readerror/gateclosed/unknownsend/late read/
late send/membership revoked/account changed/actualOS hide-resume/longcopy.
Fixture tăng giới hạn operator để chạy nhanh nhiều tình huống; production
giữ giới hạn cũ. Detector một lần:18px off-ramp đã sửa16px, không chạy lại.
App được mở trong PREVIEW_APPS của pilot, không phải cutover production.
