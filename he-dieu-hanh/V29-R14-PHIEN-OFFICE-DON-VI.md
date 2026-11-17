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

Thế hệ phiên Office có tệp riêng `office-editor-epoch`, cố ý không nằm trong
snapshot. Khởi động lại cùng kho giữ thế hệ; phục hồi vào kho mới sinh thế
hệ khác, chặn nguồn/lưu/progress/cache/callback của phiên cũ trước fetch.
Tài liệu và lịch sử vẫn được phục hồi, người dùng mở phiên mới để tiếp tục.
Phiên từ schema chưa có thế hệ không tự nhận vào thế hệ mới. Tệp thế hệ
hỏng làm khởi tạo thất bại và không tự bị ghi đè; yêu cầu nguồn không tự
tạo lại tệp bị mất. Đây chưa là nghiệm thu phục hồi engine hoặc toàn máy.

Kiểm cục bộ qua phương thức công khai `SoanThaoOffice`, đo 18/11/2026:
`thu_phien_office_don_vi.py` có 20 bài đạt về nguồn ký, hai đơn vị, rejoin,
quyền đổi trong scan/fetch, callback lưu, participant khác mất quyền,
restart/backup/restore, schema cũ, tệp thế hệ hỏng/bị mất và lệnh lưu bên dưới.
`thu_office_tich_hop.py` có 13 bài legacy đạt. Tệp Office thật và chữ ký thật;
scanner tổng hợp, fetch callback là đầu nối giả, chưa kiểm engine thật.

## Lệnh lưu và kết quả chưa rõ

Theo [command service](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service)
và [callback handler](https://api.onlyoffice.com/docs/docs-api/usage-api/callback-handler)
đối chiếu ngày 18/11/2026, nhận lệnh và lưu vào kho là hai bước. Backend
giữ ledger theo mã request; chỉ biên nhận commit mới cho kết quả `da-luu`.
Kết quả0 là đang chờ;4 là không có thay đổi, chỉ được clear pending sau
kiểm lại scope/key/request/file trong giao dịch. Callback commit2/6 trước
phản hồi lệnh được ưu tiên, kể cả phản hồi sau đó timeout hoặc báo4.

Timeout, HTTP/JSON không hợp lệ hoặc engine báo lỗi không đủ chứng minh
tài liệu chưa gửi: giữ pending với `chua-ro-ket-qua`, không phát lại mù,
kể cả khi quá120giây. Callback7 xác nhận lỗi, không được báo đã lưu hoặc
để phản hồi nhận lệnh muộn ghi đè. Callback1/3/4/7 kiểm quyền trong giao
dịch tương ứng; callback không hỗ trợ bị từ chối.

`progress` nhận `request_id` tùy chọn để đọc đúng lệnh của key; không được
mượn lệnh key khác. Lệnh từ schema trước ledger là unknown, không tự gửi
lại; callback ký hợp lệ có thể kết thúc nó. Backend `reconcile_save` cho
người có quyền xác nhận `acknowledge_unsaved_changes=true` để thu hồi key
đang chờ, giữ phiên bản đã commit; không coi đây là lưu thành công. Chưa
cấp công cụ/HTTP/UI cho phương thức này; chưa thử ngắt cache/WebSocket
engine thật. Mất quyền trong lúc đợi lệnh khiến phản hồi bị từ chối.

## Chưa mở để sử dụng

Còn kiểm force-save/callback/reconnect với engine thật và forcesave tự động
không do request BDSG; phục hồi/vòng đời engine/cache bên ngoài gateway;
proxy engine/cookie và cache/WebSocket theo phạm vi;
nhân/HTTP, UI và engine thật; các định dạng DOCX/XLSX/PPTX đầy đủ.
Google phải tách OAuth/tài khoản/token/callback và quyền nhập/xuất theo đơn
vị trước khi mở. Kiểm backend nêu trên không chứng minh các phần đó xong.
