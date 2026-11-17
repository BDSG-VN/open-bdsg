---
version: 1
slug: sync-v26
primary_target: khong-gian/tich-hop-vn.js
related_targets: [khong-gian/tich-hop-vn.css]
---
# Điều khiển đồng bộ đọc — 17/11/2026
Mode: Operate. Mở rộng trang tích hợp Việt Nam đang có, giữ nguyên DESIGN.md và PRODUCT.md.
THESIS: Chủ quản có thể tạo phiên, đọc từng trang, tạm dừng, tiếp tục, hủy và xem dữ liệu đã lưu bằng công cụ backend hiện có.
OWN-WORLD: Giữ bảng màu Manus trung tính, hàng kết nối, kiểu nút và typography hiện hữu. Không raster mới.
STORY: Chọn kết nối và thao tác → tạo phiên chưa gọi mạng → chạy từng bước → xem checkpoint. Mất phản hồi tạo dùng lại request key; thoát hoặc đổi danh tính bỏ phản hồi UI cũ.
FIRST VIEWPORT: Giữ nội dung cấu hình hiện có; phần đồng bộ tiếp sau đọc dữ liệu, trước dịch vụ chờ hợp đồng. Desktop1440 và mobile390 không tràn ngang. Điều khiển trạng thái rõ và tránh tự động gọi lại dịch vụ.
FORM: code-led, mở rộng cục bộ theo mục tiêu đã được chủ quản ủy quyền. Không thay nhận diện.
FINISH: Kiểm tương tác thật trên dữ liệu tổng hợp, detector một lần và review ảnh. Giữ các tệp thiết kế.
