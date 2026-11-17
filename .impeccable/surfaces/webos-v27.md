---
version: 1
slug: webos-v27
primary_target: khong-gian/he-dieu-hanh.js
related_targets: [khong-gian/ios.css, khong-gian/trinh-duyet.html, khong-gian/trinh-duyet.js, khong-gian/trinh-duyet.css, khong-gian/ung-dung.js]
---
# Không gian ứng dụng iOS BDSG — 17/11/2026

Mode: Operate. Thay thế thế giới Manus theo lựa chọn trực tiếp của chủ quản:
“Chuyển toàn bộ giao diện theo phong cách iOS”. Trải nghiệm được yêu cầu là
hệ điều hành có các phần mềm BDSG và trình duyệt/tìm kiếm riêng; phần cứng đầu
tiên là máy chủ. Đây là webOS trên Ubuntu, không phải nhân iOS hoặc Safari.

THESIS: Mở ứng dụng từ màn hình chính, chuyển qua Dock và danh sách cửa sổ,
giữ ngữ cảnh khi chuyển ứng dụng; có tìm kiếm ứng dụng và danh mục BDSG.

OWN-WORLD: Kiểu chữ hệ thống, tiêu đề rõ, nhóm trắng trên nền xám/xanh nhạt,
hành động xanh, biểu tượng vuông bo góc tự vẽ bằng hệ SVG BDSG. Dock dùng lớp
mờ để vẫn thấy ngữ cảnh phía sau, có nền trắng dự phòng; không dùng tài sản
Apple hoặc giả thời tiết, pin, tín hiệu mạng. Các màn hình nghiệp vụ dùng
cùng hệ chữ và hành động xanh, không giữ Lora làm giọng tiêu đề.

STORY: Màn hình chính → ứng dụng → giữ cửa sổ trong bộ nhớ → Dock/chuyển
ứng dụng → tiếp tục. Tìm kiếm BDSG → kết quả thật từ danh mục; tìm web/mở URL
→ chuyển rõ sang tab thiết bị. Google đăng nhập ở cấp cao nhất. Editor và
Google Office mở thẻ riêng khi ứng dụng chạy trong khung.

FIRST VIEWPORT: Desktop 1440 có thanh trạng thái BDSG/giờ thật/tài khoản,
tiêu đề Thanh Hoá, tìm kiếm, nhóm ứng dụng và Dock. Mobile 390 có bốn cột
biểu tượng, nhãn đọc được và Dock không che điều khiển. Mở app có thanh cửa
sổ và nội dung trong khung; ứng dụng ngoài không hiển thị như đã cài native.

SIGNATURE: Đổi ứng dụng giữ DOM của cửa sổ, chỉ cửa sổ hiện tại nhận tương
tác; tải lại chỉ khôi phục metadata có giới hạn. Đăng xuất hoặc đổi danh
tính đóng cửa sổ cũ. Không mô tả ẩn DOM như đình chỉ tiến trình thật.

FORM: code-led. Seed reference seed:dc2c02cf28665d7e, assignment index3 đã
được đọc; pin iOS của chủ quản giữ toàn quyền, không mượn hình thức từ các
challenger typography/transit. Chuẩn tham chiếu là Apple HIG có nguồn trong
NGHIEN-CUU-IOS-WEBOS.md. Không comp/raster shipping mới.

FINISH: Kiểm Home/app/switcher/tùy chỉnh/browser, desktop1440/mobile390,
search/empty/error/URL không hợp lệ/giới hạn tab/cửa sổ/logout/đa tab. Detector
một lần theo đích. Reviewer kết luận trên ảnh/bằng chứng; cập nhật DESIGN.md
và design.json theo quyền thay thế toàn bộ phong cách đã được chủ quản cấp.
