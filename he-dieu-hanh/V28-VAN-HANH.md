# V28 — quản trị nút máy chủ và phục hồi dữ liệu

Mốc mã ngày 17/11/2026. V28 bổ sung ứng dụng **Máy chủ** vào vỏ iOS BDSG,
không cấp terminal hoặc quyền quản trị host qua trình duyệt.

`GET /api/node` và công cụ MCP `thiet_bi.trang_thai` chỉ cho chủ quản.
Danh tính và chính sách của nhân được kiểm trước khi đọc số liệu. Khách,
operator và agent không được xem thông tin nút. UI bỏ kết quả đến trễ khi
đổi tài khoản hoặc rời trang; lỗi chỉ hiển thị hướng dẫn thử lại.

Ứng dụng hiển thị thời điểm quan sát, OS/kernel, môi trường ảo hóa, CPU logic,
tải trung bình, bộ nhớ và hệ thống tệp chứa dữ liệu. Trường không đo được giữ
`null`; không dùng số không thay cho dữ liệu thiếu. Không suy luận phần cứng
vật lý hoặc khả năng GPU. Bộ thu chỉ đọc nguồn giới hạn, cache ngắn và không
trả hostname, IP, serial, biến môi trường, cấu hình hay nhật ký thô.

Phiên bản ứng dụng lấy từ `BDSG_RELEASE_ID` có giới hạn ký tự; thiếu hoặc sai
trả `unknown`, thay cho nhãn V20 cố định trước đây. `BDSG_RECOVERY_STATUS_FILE`
trỏ tới báo cáo ngoài web/Git, lọc schema và từ chối báo cáo cũ/sai.

Diễn tập phục hồi kiểm manifest/SHA, phục hồi vào thư mục mới, kiểm lại dữ liệu
và SQLite, rồi ghi số lượng bản ghi, tuổi snapshot và thời gian đo. Không chạy
dịch vụ đã phục hồi. Kết quả này chưa chứng minh RTO dịch vụ hoặc cam kết RPO.
Timer mẫu chạy sau cửa sổ sao lưu; chỉ dọn thư mục tạm của lượt diễn tập.

Gói sao lưu có thể mã hóa bằng công cụ age được ghim phiên bản; tar rõ đi qua
stdin, không ghi xuống đĩa. Khóa riêng và chứng thư Drive do người vận hành
giữ ngoài máy chủ/web/Git. Upload một bản và kiểm tải lại chưa tạo lịch sao lưu
Drive tự động. UI ghi riêng trạng thái **tự động sao lưu ngoài máy** để tránh
nhầm hai việc này.

Các kiểm thử dùng dữ liệu tổng hợp. Bằng chứng triển khai, kiểm kê thật, vị trí
Drive và tài liệu khôi phục riêng được giữ ngoài kho công khai. V28 mới đáp ứng
một phần cổng nghiệm thu trong lộ trình; còn lịch offsite, diễn tập khôi phục
toàn dịch vụ và chính sách vận hành dài hạn trước khi coi V28 hoàn tất.

Tham khảo: [bộ thu TH01](V28-TH01.md), [kiểm phục hồi](V28-KHOI-PHUC.md),
[mã hóa offsite](../trien-khai/van-hanh/V28-MA-HOA-OFFSITE.md).
