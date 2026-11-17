# R14 — phiên Office theo đơn vị, đang phát triển

Ngày 18/11/2026: mới nghiệm thu các chốt quyền backend trên kho tổng hợp;
chưa mở công cụ/HTTP soạn thảo trong chế độ đơn vị và chưa triển khai R14.

Phiên cộng tác có tham chiếu membership epoch/revision và thế hệ quyền dự
án của từng người tham gia trong SQLite riêng. Hai đơn vị không dùng chung
khóa phiên dù cùng được cấp quyền vào một tệp. Cùng đơn vị được dùng chung
khóa khi các tham chiếu còn hiệu lực. Tạo lại quyền không hồi sinh phiên cũ.

Mỗi lần dùng phiên kiểm lại quyền của mọi người tham gia. Nếu một người đã
mất quyền, callback không được dùng danh tính còn quyền khác để lưu thay.
Khi người hợp lệ mở lại, phiên không còn hợp lệ được đánh dấu thu hồi và
khóa mới được tạo. Đổi lại, cộng tác viên còn quyền cũng phải mở lại phiên;
không tự tiếp tục các sửa đổi còn trong engine của phiên bị thu hồi.

Mở tệp giữ tham chiếu quyền trước quét và đối chiếu lại trong giao dịch ghi.
Nguồn ký khôi phục actor từ tham chiếu phía máy chủ. Save/progress và truy
cập cache có key kiểm actor thuộc chính phạm vi đã tham gia, không chỉ
trùng ID. Callback đọc lại tham chiếu sau nhận/quét dữ liệu trước commit.
Legacy giữ luồng cũ khi không bật đơn vị.

Kiểm cục bộ qua phương thức công khai `SoanThaoOffice`, đo 18/11/2026:
`thu_phien_office_don_vi.py` có 5 bài đạt về nguồn ký, hai đơn vị, rejoin,
quyền đổi trong scan/fetch, callback lưu và participant khác mất quyền.
`thu_office_tich_hop.py` có 13 bài legacy đạt. Tệp Office thật và chữ ký thật;
scanner tổng hợp, fetch callback là đầu nối giả, chưa kiểm engine thật.

## Chưa mở để sử dụng

Còn kiểm lệnh force-save và kết quả sau IO; mọi nhánh callback 1–7 trong
giao dịch; vòng đời khóa khi restart/restore (không để bản sao phục hồi hồi
sinh quyền phiên cũ); proxy engine/cookie và cache/WebSocket theo phạm vi;
nhân/HTTP, UI và engine thật; các định dạng DOCX/XLSX/PPTX đầy đủ.
Google phải tách OAuth/tài khoản/token/callback và quyền nhập/xuất theo đơn
vị trước khi mở. Kiểm backend nêu trên không chứng minh các phần đó xong.
