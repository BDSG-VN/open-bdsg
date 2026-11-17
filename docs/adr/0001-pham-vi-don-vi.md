# Phạm vi đơn vị được xác lập ở máy chủ, quyền nội dung kiểm theo tài nguyên

Ngày 17/11/2026, chủ quản chọn mỗi doanh nghiệp/đơn vị có dữ liệu riêng và
chỉ chia sẻ khi cấp quyền. Chọn giữ SQLite chung, xác lập phạm vi đơn vị
bất biến từ danh tính đã xác thực và tư cách thành viên, rồi kiểm lại quyền
trong giao dịch của Module nghiệp vụ. Bắt đầu ở seam `DuAn.authorize` để
luồng dự án → tài liệu/tệp dùng chung chính sách thay vì mỗi caller tự ghép
điều kiện. Vai quản trị đơn vị không tự cấp quyền nội dung; quyền chủ quản
toàn cổng không thay quyền tài nguyên trong luồng có phạm vi.

Đã cân nhắc dispatcher nghiệp vụ tập trung và gateway/kho riêng theo đơn
vị. Dispatcher tập trung làm rộng tập yêu cầu và gom nhiều schema vào một
Module; gateway riêng giảm rủi ro truy vấn thiếu bộ lọc nhưng cần thêm định
tuyến danh tính, Office/Google callback, browser runtime và chia sẻ xuyên
gateway. Phương án chọn tận dụng giao dịch và chốt quyền Office hiện có;
đổi lại phải chuyển và kiểm mọi đường truy cập, vì SQLite không tự áp RLS.

Quyết định đã áp dụng ở backend dự án/tệp thử nghiệm; chưa nối vào gateway
production. Phạm vi trong bộ nhớ không là token hoặc dữ liệu tuần tự hóa
cho worker; worker/callback phải xác lập lại theo identity/unit đã lưu.
Chưa mở nhiều doanh nghiệp khi task, lịch, Google, MCP, AI, cache/audit hoặc
participant grant Office còn dùng quyền toàn cổng. Sau cutover, quay lại
mã cũ có thể bỏ chốt cách ly: chỉ rollback sang bản hiểu đơn vị, hoặc phục
hồi snapshot trước cutover trong cửa sổ đã dừng ghi.
