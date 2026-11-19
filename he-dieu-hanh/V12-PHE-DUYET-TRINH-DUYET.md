# V12: phê duyệt thao tác trình duyệt

Phạm vi ngày 15/11/2026: tiếp nối Xưởng công việc V6–V11, bổ sung đề xuất
nhập văn bản, chọn giá trị, bấm thành phần và nhấn phím. Chưa nghiệm thu
agent với mô hình trả phí hoặc đầu nối nghiệp vụ BDSG thật.

## Cách sử dụng

Tạo công việc có phạm vi tên miền trình duyệt và bật quyền dự thảo hành động.
Mở Xưởng công việc → Trình duyệt, quan sát trang, chọn thành phần và thao tác.
Nút **Lưu đề xuất để chủ quản duyệt** chưa tác động lên biểu mẫu. Nội dung nhập
được lưu trong sổ hành động riêng; chỉ dùng dữ liệu nghiệp vụ thông thường.

Tại **Chờ phê duyệt**, chủ quản kiểm người giao, trang, đích biểu mẫu và nội dung.
Có thể xem màn hình hiện tại trước khi duyệt. Nếu biểu mẫu thay đổi, từ chối và
tạo lại đề xuất từ quan sát mới. Agent chỉ được gọi `hanh_dong.de_xuat`, không
được gọi trực tiếp công cụ thực hiện hoặc tự phê duyệt.

## Ranh giới

- Đề xuất gắn danh tính, công việc/lượt chạy, mã quan sát, thành phần đã quan sát,
  URL đầy đủ và trạng thái biểu mẫu. Bằng chứng HMAC dùng khóa tạm riêng phiên;
  giá trị các trường hiện có chỉ tham gia tính bằng chứng, không trả trong metadata.
- Chủ quản duyệt không nâng quyền người đề xuất. Công cụ thực hiện cần ngữ cảnh
  phê duyệt nội bộ, kiểm lại quyền và bằng chứng trước thao tác. Mã quan sát được
  tiêu thụ trước tác động; không tự gửi lại khi kết quả chưa rõ.
- Trường mật khẩu, tệp, OTP, thông tin thẻ được nhận diện bằng kiểu trường,
  tên trường và autocomplete sẽ bị chặn. Đây là nhận diện theo thuộc tính,
  **không bảo đảm phát hiện mọi biểu mẫu nhạy cảm**. Người dùng cần tự tiếp quản
  đăng nhập, xác minh và thanh toán; không đưa bí mật vào nội dung đề xuất.
  Biểu mẫu có nút đổi đích gửi cũng chặn đề xuất phím, tránh Enter gửi tới một
  đích khác với địa chỉ của biểu mẫu; người dùng tự tiếp quản trường hợp này.
- Ảnh xem trước chỉ trả qua API có xác thực, không lưu vào cơ sở dữ liệu hay web.
  Ảnh vẫn có thể chứa thông tin hiển thị trên trang. Đóng tab hoặc đăng xuất để
  xóa nội dung khỏi giao diện. Phiên và đề xuất giữ thời hạn của V11.
- Kiểm trạng thái DOM không phải giao dịch nguyên tử với máy chủ ứng dụng đích.
  JavaScript hoặc hệ thống phía sau có thể đổi sau bước kiểm. Chủ quản phải kiểm
  đúng nghiệp vụ; không dùng cơ chế này để cam kết giao dịch tài chính an toàn.
  Playwright vẫn kiểm điều kiện thao tác thông thường, không ép bấm thành phần.
- Dịch vụ, cổng mạng và kho dữ liệu giữ kiến trúc cách ly của V11. Khởi động lại
  worker xóa phiên trình duyệt; đề xuất còn lại không thể thực hiện bằng phiên cũ.

## Kiểm tra tái lập

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_phe_duyet_browser.py' -v
BDSG_TEST_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/duong-dan-chromium \
  /duong-dan-venv/bin/python -m unittest discover -s he-dieu-hanh -p 'thu_browser_bieu_mau.py' -v
```

Chạy kiểm Chromium bằng tài khoản không phải root và bật Chromium sandbox.
Biểu mẫu tổng hợp được trả tại chỗ, không gửi nghiệp vụ tới website bên ngoài.
CI không có Chromium phải ghi rõ bỏ qua nhóm này; không tính thành kiểm đã chạy.

Nguồn cơ chế thao tác: [Playwright actionability](https://playwright.dev/python/docs/actionability).
