# V29 R13 — yêu cầu kinh doanh theo đơn vị

Ngày 18/11/2026: backend và giao diện đang nghiệm thu trên dữ liệu thử;
chưa phát hành R13 lên máy chủ hoặc chuyển production sang chế độ đơn vị.

Ba công cụ `kinh_doanh.danh_sach`, `kinh_doanh.tao_yeu_cau`,
`kinh_doanh.doi_chang` đi qua nhân và kiểm phạm vi đơn vị còn hiệu lực.
Tạo yêu cầu nhận `title`, `sector`, `description` và `project_id` tùy chọn.
Không nhận chủ sở hữu hoặc mã đơn vị từ nội dung yêu cầu.

- Không có dự án: chỉ người tạo trong đúng đơn vị và lần tham gia được đọc/sửa.
  Quản trị đơn vị không tự đọc được; rời rồi tham gia lại không phục hồi quyền.
- Có dự án: nội dung thuộc đơn vị nguồn của dự án. Quyền đọc/sửa theo dự án,
  kể cả chia sẻ đích danh xuyên đơn vị. Người tạo không giữ ngoại lệ sau khi
  quyền dự án bị thu hồi. Viewer chỉ đọc; editor được tạo và đổi chặng.
- Dự án lưu trữ vẫn đọc được nhưng chặn tạo/đổi chặng tới khi khôi phục.
- Cổng ghi trong nhân vẫn áp dụng; thay đổi và audit metadata cùng giao dịch.
  Nội dung yêu cầu không được ghi vào audit.

Danh sách trả tối đa 200 yêu cầu có quyền, mới nhất trước (giới hạn kiểm trong
mã ngày 18/11/2026). Bốn chặng hiện có: tư vấn, triển khai, vận hành, kinh doanh.
Chưa có tìm kiếm/phân trang, chỉnh mô tả, gán người xử lý hoặc lịch sử chặng.
Không nhập bảng `yeu_cau` cũ vào đơn vị, không mở thêm quyền MCP đầu vào.
Chế độ legacy tiếp tục dùng kho cũ; không nhận gắn dự án để tránh hiểu nhầm
rằng quyền dự án đã được áp dụng ở chế độ đó.

Kiểm thử công khai: `thu_kinh_doanh_don_vi.py` gọi nhân thật trên SQLite tạm,
bao gồm chia sẻ/thu hồi, epoch, cổng ghi và sao lưu–phục hồi.
`thu_don_vi_http.py` kiểm cookie, chọn đơn vị, Origin và chặn alias cũ.
Kết quả kiểm này không chứng minh giao diện hay tích hợp với nền tảng ngoài.

## Giao diện đơn vị thử nghiệm

Trang Yêu cầu nhận danh sách cùng `can_edit`, `project_name`, `archived` và
`project_options` từ máy chủ. Các thông tin này được kiểm trong cùng giao
dịch đọc; không là token ghi và không thay lần kiểm quyền khi tạo/đổi chặng.
Danh sách chọn dự án có tối đa 100 dự án được phép ghi, chưa có phân trang
(giới hạn mã ngày 18/11/2026). Không trả metadata dự án chưa được cấp quyền.

Biểu mẫu nằm trong trang, cho chọn cá nhân hoặc dự án. Bốn chặng nằm cạnh
nhau trên máy tính và xếp dọc trên điện thoại. Lưu trữ/viewer là chỉ đọc;
không suy quyền từ người tạo hoặc vai quản trị trong JavaScript. Giao diện
đọc lại theo chu kỳ, giữ node/focus khi dữ liệu không đổi. Lỗi đọc gỡ danh
sách cũ; mất phản hồi ghi khóa thao tác tới khi người dùng làm mới và kiểm
tra kết quả. Không gửi lại tự động. Đổi scope/tài khoản hoặc ẩn ứng dụng gỡ
nội dung/bản nháp và bỏ các callback của scope cũ.

Không mở tổng quan/nhật ký hoặc alias toàn cổng. Legacy vẫn dùng giao diện
cũ. Nghiệm thu trình duyệt và trạng thái phát hành được ghi trong báo cáo
riêng; kiểm backend không tự thay nghiệm thu toàn bộ giao diện.
