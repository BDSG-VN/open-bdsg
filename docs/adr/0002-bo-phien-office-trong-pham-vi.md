# Bỏ phiên Office thu hồi quyền ghi, không cấp lại quyền phiên cũ

Ngày 18/11/2026, chọn thao tác phục hồi theo tài liệu và đơn vị hiện tại:
người gọi phải còn quyền ghi tài liệu và đã tham gia phiên của đúng đơn
vị. Sau xác nhận mất thay đổi và ảnh hưởng phiên dùng chung, thu hồi các
phiên của người đó trong phạm vi này; không bỏ lần lưu đang chờ của người
khác. Thao tác có mã riêng, kết quả và thu hồi cùng giao dịch; gọi lại chỉ
đọc kết quả đã ghi, không hủy phiên mới mở sau lần đầu.

Chỉ xóa trạng thái trong trình duyệt không chặn yêu cầu lưu đến muộn. Chỉ
đối soát theo request_id không xử lý được yêu cầu chưa nhận phản hồi hoặc
record hỏng. Vì vậy quyền ghi hiện tại cho phép thu hồi phiên từng tham
gia trong cùng tài liệu/đơn vị, kể cả phiên cũ đã mất hiệu lực; quyền này
không cho đọc lại nội dung hoặc dùng lại tham chiếu quyền cũ. Không sửa
chính sách nguồn/callback/engine để làm phiên cũ hợp lệ trở lại.

Kết quả gọi lại vẫn ràng buộc tư cách/quyền dự án và issuer; đổi quyền
hoặc phục hồi sang issuer mới không dùng được biên nhận cũ. Thu hồi ở
gateway chặn lệnh/callback mới, chưa tự chứng minh ngắt WebSocket hoặc
xóa cache đã tồn tại của engine. Công cụ/HTTP/UI và engine thật còn cần
nghiệm thu trước khi mở cho người dùng.
