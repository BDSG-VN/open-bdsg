# V27 — vỏ hệ điều hành ứng dụng BDSG

Ngày **17/11/2026**, chủ quản đổi hướng diện mạo từ Manus sang iOS và đặt
máy chủ vật lý Thanh Hoá là phần cứng đầu tiên của hệ sinh thái BDSG.
Tham vọng và các cổng nghiệm thu tiếp theo tại
[lộ trình V27–V34](LO-TRINH-HE-SINH-THAI-BDSG.md); căn cứ thiết kế tại
[nghiên cứu iOS/WebOS](NGHIEN-CUU-IOS-WEBOS.md).

## Bản đang được nghiệm thu

- Màn hình chính, Dock, tìm ứng dụng/danh mục BDSG, danh sách cửa sổ và tùy
  chỉnh chữ lớn/giảm chuyển động theo phong cách đã chọn. Giữ thương hiệu
  BDSG và SVG tự có; không phân phối tài sản hoặc mã hệ điều hành Apple.
- **16** mục ứng dụng nội bộ trong registry ngày 17/11/2026. Mỗi cửa sổ chạy
  mã BDSG tại `workspace.html` hoặc app trình duyệt riêng; không biến URL
  nền tảng bên ngoài thành bằng chứng cài phần mềm native hoặc liên thông.
- Tối đa **8** cửa sổ cùng tài khoản, mở lại dùng cửa sổ sẵn có, mở thêm chỉ
  khi chọn rõ. Chuyển ứng dụng giữ DOM và bản nháp trong bộ nhớ. Đóng có xác
  nhận, không tự hủy tác vụ đã gửi. Khôi phục trang chỉ giữ metadata đã lọc
  trong sessionStorage, không giữ nội dung biểu mẫu hoặc khóa.
- Trình duyệt BDSG có tối đa **12** tab và dấu trang trong bộ nhớ phiên,
  lịch sử điều hướng riêng, tìm không dấu trên danh mục thật, trạng thái
  lỗi/thử lại. URL và tìm web chuyển sang tab thiết bị một cách rõ ràng;
  không proxy mạng, không nhúng web tùy ý, không giả kết quả tìm kiếm.
- Đổi danh tính giữa các tab thông báo để xóa cửa sổ/cache cũ; trước mở hoặc
  kích hoạt cửa sổ kiểm `/api/me`. Header `X-BDSG-Actor` bảo vệ API cookie
  khỏi biểu mẫu cũ gửi dưới cookie tài khoản mới, trả 409 `identity_changed`.
  Header không xác thực người dùng hoặc thay danh tính Bearer. Client cũ
  thiếu header vẫn tương thích, nên không coi đây là thay thế xác thực.
- Khởi động ứng dụng chỉ tải dữ liệu cần cho màn hình đó. Các lượt đọc ban
  đầu được gộp khi đang bay, tối đa hai lượt cùng lúc và không cache kết quả
  quyền sau khi hoàn tất. Cửa sổ ẩn ngừng các vòng poll UI của tác vụ/hộp
  thư; công việc máy chủ vẫn chạy, không hạ hạn mức của nhân để mở nhiều cửa sổ.
- Đăng nhập Google ở trang chính; editor/Picker/Google Office mở thẻ riêng
  khi thao tác từ workspace. Office không bị kẹt trong iframe bị DENY.

V27 là lớp ứng dụng trên Ubuntu và trình duyệt thiết bị; không phải Linux
kernel mới, bản cài iOS, Safari engine hoặc hypervisor. Nhiều cửa sổ không
phải nhiều VM/tài khoản tách cookie; ẩn DOM không đình chỉ tiến trình nền.
Manifest hỗ trợ trình duyệt nhận dạng ứng dụng, chưa có service worker hoặc
cam kết offline. Các công cụ/API/MCP tiếp tục qua nhân/quyền/hạn mức đã có.

## Kiểm ngày 17/11/2026

Linux: **255** bài ứng dụng, **240** đạt, **15** bỏ qua theo môi trường.
**4** bài đóng gói và **27** bài Node mới đạt, cùng ba chương trình hồi quy
giao diện trước đó. Bộ mới kiểm metadata/identity/giới hạn/vòng đời cửa sổ,
URL, tab/search và Office tách thẻ. HTTP kiểm danh tính khớp/sai/không header,
read/write/logout và Bearer không bị header ghi đè.

```sh
python -m unittest discover -s he-dieu-hanh -p 'thu_*.py' -v
python trien-khai/thu_giao_dien.py -v
node --test khong-gian/thu_he_dieu_hanh.cjs khong-gian/thu_trinh_duyet.cjs khong-gian/thu_van_phong_cua_so.cjs khong-gian/thu_bao_ve_phien.cjs
```

Trình duyệt với backend thật và danh tính/dữ liệu tổng hợp đã qua Home,
search, nhiều cửa sổ, giữ bản nháp khi chuyển, restore metadata, tab/dấu
trang, lỗi/thử lại, handoff editor thẻ mới, từ chối danh tính cũ và thay
tài khoản giữa hai tab. Desktop 1440/mobile 390 không tràn ngang hay lỗi JS.
Đây không thay nghiệm thu Google Office, MCP hoặc provider AI thật; đợt này
không dùng API tính phí. Biên bản finish/triển khai được ghi riêng sau kiểm.

Review Standards không có lỗi bắt buộc mức cao; đã cập nhật chỉ dẫn Manus
cũ trong nghiên cứu theo quyết định iOS. Review Spec xác nhận bảo vệ phiên
cho editor/Picker và điều hướng liên ứng dụng đã được sửa. Review UI mở đủ
13 ảnh, chấm hệ chữ/vật liệu/nền/khả năng thích ứng phù hợp; sửa duy nhất
toast chồng Dock được chấm resolved, disposition ship trong ba ảnh chụp lại.

## Cấu hình triển khai và quay lại

Đóng gói `workspace.html`, app trình duyệt, state/shell/CSS và manifest. Chỉ
hai trang HTML nội bộ được `SAMEORIGIN`/`frame-ancestors 'self'` qua
`trien-khai/webos/nginx-khung.conf`. Trang gốc, editor và Google callback
giữ DENY; không cấp `frame-src https:` hoặc CORS mới. Sandbox chỉ cho phép
khả năng cần bởi mã BDSG đáng tin, kể cả prompt/confirm và mở thẻ; không dùng
chính sách này cho mã HTML/website tùy ý do người ngoài cung cấp.

Trước đổi bản cần snapshot SHA/restore và giữ V26. Rollback phải phục hồi
cả unit/symlink và cấu hình Nginx/snippet; kiểm `nginx -t` trước reload. Giữ
nguyên cơ sở dữ liệu, khóa, cấu hình AI và ứng dụng khác của máy chủ.

Chặng tiếp theo là quản lý nút máy chủ và hợp đồng thiết bị/ứng dụng, không
chạy shell root từ giao diện khách. Các khả năng tương lai trong lộ trình
không được đánh dấu hoàn tất vì đã có icon hoặc tên phiên bản.
