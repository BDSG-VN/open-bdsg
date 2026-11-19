# V29 R7 — chọn đơn vị làm việc

Ngày cập nhật: 17/11/2026. Bổ sung giao diện cho chế độ đơn vị thử nghiệm của
R2–R6; không tự bật chế độ này, tạo đơn vị hay chuyển dữ liệu vận hành cũ.

Sau đăng nhập, `/api/me` trả khả năng của không gian làm việc tách khỏi bản ghi
người dùng. Khi chế độ đơn vị được bật, thanh chọn chỉ nhận danh sách membership
đã xác thực từ `/api/units`. Lựa chọn lưu theo tài khoản trong từng thẻ trình
duyệt; không lưu nội dung dự án, tệp hoặc khóa. Chưa chọn đơn vị thì các ứng
dụng nghiệp vụ yêu cầu chọn trước. Tài khoản và trình duyệt vẫn mở được.

Đổi đơn vị có cửa sổ đang mở cần xác nhận vì nội dung chưa lưu có thể mất.
Sau khi đổi, vỏ đóng các iframe cũ, xóa bộ nhớ nghiệp vụ và trạng thái broker.
Cửa sổ con giữ phạm vi tại thời điểm được mở; không nhận đơn vị mới từ cửa sổ
cha. Phản hồi đến muộn phải kiểm lại phạm vi sau khi đọc JSON. Thu hồi quyền
hoặc thay đổi vai trò buộc xóa ngữ cảnh cũ, không chờ xác nhận của người dùng.

Header epoch/revision giúp phát hiện giao diện cũ và trả `409 unit_changed`;
chúng không thay xác thực cookie, membership hoặc quyền công cụ ở máy chủ.
Client không thể ghi đè các header phạm vi bằng cách đổi kiểu chữ tên header.
Chủ quản hệ thống có thể tạo đơn vị và chỉ định tài khoản quản trị đã tồn tại;
quyền chủ quản không tự cho phép đọc nội dung của mọi đơn vị.

## Các ứng dụng ở chế độ đơn vị

- Dự án: đọc, tạo và sửa theo phạm vi; bộ nhớ bị xóa khi chuyển đơn vị.
- Công việc và Agent BDSG: giao việc theo cấu hình/hạn mức AI của đơn vị.
- Văn phòng: tệp và phiên bản cơ bản, chia sẻ đọc/chỉnh sửa rõ ràng. Trình soạn
  thảo Office và Google chưa được chuyển sang phạm vi đơn vị, nên không bật.
- Trung tâm AI: quản trị theo membership của đơn vị, không theo vai trò toàn
  hệ thống. Thành viên thường chỉ xem trạng thái được phép và giao việc.
- Mô-đun và đội ngũ agent: danh mục được lọc, chỉ đọc; không trả cấu hình kết
  nối toàn cục hay mở công cụ xuất dữ liệu chưa hỗ trợ đơn vị.
- Máy chủ, Xưởng, Kết nối và các ứng dụng chưa chuyển được đánh dấu chưa hỗ
  trợ. Không mở được bằng biểu tượng hoặc đường dẫn trực tiếp trong vỏ.

Mở danh mục website không chứng minh có SSO, MCP hoặc kết nối dữ liệu thật.
Không bật lại ứng dụng chưa chuyển chỉ để làm đầy giao diện.

## Kiểm tra và giới hạn nghiệm thu

Ngày 17/11/2026, trình duyệt Chromium trên HTTPS loopback với gateway thật và
dữ liệu tổng hợp đã qua 18 tình huống: tạo dự án, tải tệp, tạo tác vụ AI qua
adapter giả lập, đổi/hủy đổi đơn vị, tải lại, vai trò quản trị/thành viên,
thu hồi quyền, phản hồi JSON đến muộn, header giả, lựa chọn độc lập hai thẻ,
loading/lỗi/thử lại, không có membership và chủ quản tạo đơn vị. Không gọi
API tính phí hoặc dùng dữ liệu khách hàng trong phép thử này.

Các bài kiểm có thể chạy từ kho:

```sh
node --test khong-gian/thu_don_vi.cjs khong-gian/thu_vo_don_vi.cjs khong-gian/thu_du_an_form.cjs
python3 he-dieu-hanh/thu_don_vi_http.py -v
python3 trien-khai/thu_giao_dien.py -v
```

Hai lỗi được tái hiện rồi sửa: control `name="id"` che `form.id` làm bộ xử lý
submit nhận sai định danh; iframe kết quả tác vụ mở lúc cha đang xác minh
membership giữ nhầm trạng thái loading. Kiểm hồi quy đi qua listener thật và
vòng đời phạm vi thực tế, không chỉ kiểm chuỗi mã nguồn.

Đây là nghiệm thu bản thử nghiệm đơn vị, chưa phải chuyển đổi dữ liệu sản xuất.
Cần tiếp tục chuyển công cụ chưa hỗ trợ, tích hợp Office/Google theo đơn vị,
di chuyển và thử phục hồi toàn bộ dữ liệu trước khi quyết định bật trên hệ thống
đang vận hành. Triển khai mã mới phải giữ bản trước và đường quay lại.
