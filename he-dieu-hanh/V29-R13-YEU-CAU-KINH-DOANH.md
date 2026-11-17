# V29 R13 — yêu cầu kinh doanh theo đơn vị

Ngày 18/11/2026: phần backend đang phát triển trên dữ liệu thử; chưa phát hành
R13 lên máy chủ và chưa mở giao diện yêu cầu trong chế độ đơn vị.

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
