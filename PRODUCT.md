# BDSG Thanh Hoá

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Chủ quản, nhân viên vận hành và các agent được cấp quyền phát triển kinh doanh
đa lĩnh vực tại Thanh Hoá. Phạm vi theo yêu cầu của chủ quản, không giới hạn
thành công cụ dành riêng cho đội bất động sản hoặc mở rộng sang các tỉnh khác.
Khách hàng có thể dùng hướng dẫn công khai theo từng nền tảng; mỗi trợ lý có
hồ sơ riêng, không dùng quyền hoặc hội thoại của chủ quản.

## Product Purpose

Giao mục tiêu, chọn mô-đun BDSG, dùng tài liệu dự án và theo dõi công việc đến
kết quả có bằng chứng. Liên kết website và đầu nối MCP là hai khả năng khác nhau.

## Capabilities and Constraints

Định hướng máy chủ trước: không gian kinh doanh chạy trên máy chủ Ubuntu,
truy cập qua web; các phần mềm BDSG và trình duyệt nằm trong một vỏ ứng dụng.
Đây là webOS, không phải nhân hệ điều hành iOS hoặc trình duyệt Safari.
Giao diện HTML/CSS/JavaScript thuần; gateway Python, dữ liệu riêng ngoài web.
Dự án, tài liệu, công việc, lịch, công cụ xử lý dữ liệu, trình duyệt và phê duyệt
đã có trong bản thử nghiệm. AI và MCP nghiệp vụ thật cần cấu hình riêng, không
được bịa dữ liệu, kết quả hoặc trạng thái kết nối. Mọi quyền vẫn qua nhân.
Vỏ ứng dụng giữ cửa sổ trong bộ nhớ khi chuyển ứng dụng, không đình chỉ tiến
trình hệ điều hành. Tải lại không khôi phục đầy đủ trạng thái trong từng ứng
dụng. Tìm BDSG dùng danh mục; website và tìm web mở tab thiết bị. Đăng nhập
Google chạy ở cấp trang chính; trình soạn thảo và Google Office mở riêng khi
cần. Mở website không đồng nghĩa cài ứng dụng, SSO hoặc liên thông dữ liệu.

## Brand Commitments

Giữ tên, biểu tượng BDSG và tiếng Việt. Quyết định mới nhất ngày 17/11/2026:
“Chuyển toàn bộ giao diện theo phong cách iOS”. Quyết định này thay thế lựa
chọn diện mạo Manus ngày 15/11/2026: dùng chữ hệ thống, hành động xanh, nhóm
bề mặt sáng, biểu tượng BDSG bo góc và Dock. Không sử dụng tài sản Apple hoặc
đổi thương hiệu BDSG thành Apple; phong cách không làm phát sinh khả năng
native iOS, trạng thái thiết bị hoặc kết nối nghiệp vụ chưa có.

## Evidence on Hand

Mã tại khong-gian/, nghiệp vụ tại he-dieu-hanh/, danh mục tại nen-tang/.
Quyết định và phạm vi vỏ ứng dụng ngày 17/11/2026 tại
`.impeccable/surfaces/webos-v27.md`; màu và thành phần hiện tại trích từ
`khong-gian/ios.css` cùng `khong-gian/trinh-duyet.css`. Tài liệu thiết kế không
thay cho nghiệm thu ảnh hoặc kiểm thử chức năng. Dữ liệu kiểm tra phải ghi
nhãn tổng hợp; bí mật và thông tin khách hàng không vào Git.

## Product Principles

- Cho người dùng hiểu mình đang giao việc gì và theo dõi được kết quả thật.
- Các quyền và cấu hình có tác động phải rõ ràng, không tự mở rộng.
- Giao diện thống nhất trên máy tính và điện thoại, dùng bàn phím được.
- Triển khai có bản trước để quay lại và giữ nguyên dữ liệu vận hành.
