---
version: 1
slug: yeu-cau-don-vi
primary_target: khong-gian/yeu-cau-ui.js
related_targets: [khong-gian/yeu-cau-ui.css, khong-gian/ung-dung.js]
---
# Yêu cầu kinh doanh theo đơn vị — 18/11/2026

Mode Operate; mở rộng bề mặt Yêu cầu hiện có, giữ thế giới iOS đã chọn,
PRODUCT/DESIGN và bốn chặng. Không tạo concept/world/comp mới.
Inherit seed dc2c02cf28665d7e/index3 từ webos-v27.

THESIS: Ghi nhận nhu cầu cá nhân hoặc dự án được cấp quyền và chuyển chặng.
FIRST VIEWPORT: tên đơn vị, làm mới/tạo, tổng số có quyền trong tối đa200,
bốn cột trên desktop; các chặng xếp dọc trên điện thoại390.
STORY: đọc → tạo trong form inline → cá nhân/dự án → gửi → đổi chặng.
RIGHTS: nhãn dự án/cá nhân/chỉ đọc/lưu trữ; quyền sửa lấy từ server, không
suy luận qua owner hoặc admin. Chỉ chọn dự án có quyền ghi từ server.
STATES: loading/empty/error/known rejection/unknown write, không auto retry;
scope/account/hidden clear; late callbacks không phục hồi nội dung cũ.
FINISH: typography16px, iOS nhóm trắng/nền hệ thống/blue, keyboard focus,
escaped longcontent, stable rows/focus qua refresh, không overflow1440/390.
Không ảnh minh họa/tài sản Apple; nội dung tổng hợp cho nghiệm thu riêng.
