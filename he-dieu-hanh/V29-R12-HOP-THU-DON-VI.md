# V29 R12 — hộp thư đơn vị, đang phát triển

Ngày 18/11/2026, tiếp bản mã R11 đã phát hành ở chế độ legacy. Mục tiêu
R12 là đưa thông điệp/danh bạ vào phạm vi đơn vị rồi kiểm UI và phát hành;
backend không được coi là đã mở một ứng dụng hoàn chỉnh.

## Hợp đồng

Ba công cụ `agent.danh_sach`, `agent.doc_hop_thu`, `agent.gui_tin` đi qua
nhân với actor/unit thật. Danh bạ chỉ người đang tham gia đơn vị và có danh
tính còn hoạt động. Chủ quản hệ thống chưa là thành viên không đọc được;
admin đơn vị chỉ có thư mình gửi/nhận. Không có hộp thư giám sát toàn đơn vị.

Thông điệp giữ đơn vị và epoch tham gia của cả người gửi/người nhận. Thu
hồi rồi cấp lại không tự khôi phục thư của epoch cũ. Người còn tham gia
vẫn đọc lịch sử thư của chính mình khi người đối thoại rời đơn vị. Đổi vai
không đổi quyền sở hữu thư; actor đã chụp trước đổi vai phải xác lập lại.

Kiểm người gửi và người nhận trong cùng giao dịch ghi. Nội dung 1–4000 ký
tự; chỉ trả 100 thông điệp gần nhất theo danh tính/đơn vị. Không nhận thêm
sender/actor/unit từ JSON. Nội dung không vào audit; audit chỉ giữ mã đơn
vị/thông điệp. Không gửi email, gọi AI hoặc giao dữ liệu ra mạng.

Chế độ đơn vị không đọc bảng `tin` legacy; bảng mới `unit_messages` nằm
trong SQLite riêng đã được sao lưu. Chế độ legacy vẫn gọi các phương thức
cũ của Kho. Chưa tự phân loại hoặc chuyển thư cũ vào đơn vị.

MCP credential R11 chưa được cấp ba công cụ này; danh sách quyền MCP giữ
nguyên. Direct module cũng từ chối actor ủy quyền MCP. Việc có danh bạ không
chứng minh người nhận là mô hình AI đang chạy.

## Trạng thái ngày 18/11/2026

Đã có backend/nhân và route công cụ trong gateway thử. Đã kiểm dữ liệu
tổng hợp: hai đơn vị cùng identity, admin không đọc thư người khác, recipient
ngoài đơn vị/ngừng hoạt động, revoke/rejoin cả hai phía, đổi vai, JSON dư,
gate ghi đóng và snapshot/restore. HTTP dùng cookie/Origin/unit thật có
luồng gửi–nhận và từ chối thiếu phạm vi/sai origin.

Ứng dụng thông điệp chưa nằm trong `PREVIEW_APPS`: còn cần nối dữ liệu và
kiểm clear/late/error/stale ở giao diện; chưa công khai chế độ đơn vị. Chưa
hoàn tất lịch/workflow/runtime, Google/editor, audit/export/retention hoặc
toàn V29. Chưa triển khai R12 lên website.
