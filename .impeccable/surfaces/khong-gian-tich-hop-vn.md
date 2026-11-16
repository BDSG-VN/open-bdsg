# Tích hợp Việt Nam — phần mở rộng trang Quản lý kết nối

Mode: Operate. Kiểm ngày 16/11/2026. Đây là phần mở rộng trong nhận diện đã
chốt, không thiết kế lại hệ màu hoặc trang MCP. Dữ liệu nghiệm thu tổng hợp;
không có tài khoản nhà cung cấp thật trên bản QA.

## Direction contract

THESIS: chủ quản chọn nhà cung cấp, cấp đúng quyền và đọc một trang có nguồn;
không dùng tên/logo để giả trạng thái “đã liên thông”.

OWN-WORLD: kế thừa DESIGN.md và trang ket-noi.js: nền trung tính, nút đen,
system body, border mảnh và biểu mẫu rõ. Không có thế giới thị giác mới.

STORY: từ MCP chuyển sang ứng dụng Việt Nam, cấu hình riêng không gọi mạng,
đọc có chủ đích, xem kết quả/lịch sử và ngắt kết nối. Chưa có khóa vẫn biết
điều kiện triển khai; chưa có hợp đồng thì không có công cụ được bật.

FIRST VIEWPORT: giữ sidebar/header hiện tại; tên trang và nút trở về MCP;
form cấu hình bên trái, danh sách tài khoản bên phải. Điện thoại xếp một cột.
Kết quả đọc nằm dưới, bảng cuộn ngang trong vùng riêng và có hướng dẫn.

FORM: seed: none (pinned). Chủ quản đã yêu cầu “giao diện màu sắc giống manus
nhất”; thay đổi này mở rộng quy trình hiện có. Tương tác chính: lưu chứng thư
rồi bỏ trống trường khóa, chọn quyền đọc và xem nguồn/thời điểm đọc thật.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Không thay DESIGN.md. Không có raster mới được phục vụ; ảnh QA chỉ là bằng
chứng kiểm thử. Nghiệm thu scope này không chứng minh đã đạt mục tiêu dòng mã
hoặc đã kết nối ngân hàng, hóa đơn, mạng xã hội thật.
