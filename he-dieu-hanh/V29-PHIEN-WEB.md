# V29 — Quản lý phiên đăng nhập web

Phạm vi ngày 17/11/2026: ứng dụng **Tài khoản** trên màn hình chính cho người
dùng web đã đăng nhập xem, đặt tên và đăng xuất các phiên của chính mình.
Phiên hiện tại đứng đầu và được giữ khi chọn đăng xuất các phiên khác.
Đăng xuất phiên hiện tại dùng luồng đăng xuất đang có.

Danh sách hiển thị tối đa 100 phiên và báo rõ khi còn phiên chưa hiển thị.
Thu hồi các phiên khác vẫn áp dụng cho toàn bộ phiên còn hiệu lực của tài
khoản đó. Thao tác có xác nhận; các tài khoản khác không bị ảnh hưởng.
Nhãn người dùng đặt và nền tảng do trình duyệt gợi ý không xác minh thiết bị.
Thời gian ghi nhận là lần không gian web kiểm tra phiên, không phải trạng
thái online. Phiên cũ không có ngày tạo được ghi là chưa ghi nhận.

## Ranh giới bảo mật

- API `/api/sessions` và các thao tác `/rename`, `/revoke`, `/revoke-others`
  yêu cầu cookie web, chỉ làm việc với danh tính của cookie đó. Bearer token
  agent không thay được cookie. Chủ quản cũng không dùng API này để quản
  lý phiên của người khác.
- POST kiểm Origin; GET và POST kiểm danh tính tab qua `X-BDSG-Actor` nếu có.
  Mã công khai độc lập với token/hash xác thực. Không trả IP hay raw User-Agent.
- Kiểm cookie còn hiệu lực và quyền người dùng trong cùng giao dịch ghi với
  thu hồi. Hai phiên thu hồi nhau đồng thời không làm mất cả hai phiên.
- Nhật ký chỉ ghi actor, hành động và mã phiên công khai hoặc số lượng.
  Nhãn, token, hash xác thực, IP và raw User-Agent không ghi vào nhật ký này.
- Thu hồi chặn yêu cầu web tiếp theo; không rút lại phản hồi đã gửi hoặc hủy
  thao tác đã bắt đầu. Quyền Office, Google, SSH và token agent được cấp
  riêng; thu hồi phiên web không thu hồi các quyền đó. Xem
  [đối chiếu capability](../docs/nghien-cuu/V29-PHIEN-VA-UY-QUYEN.md).

## Dữ liệu và quay lại

Giữ nguyên bảng `phien` ba cột; bảng `phien_web` lưu metadata, xóa theo phiên
qua khóa ngoại. Mã trước vẫn tạo phiên ba cột và đăng xuất được. Khi quay
lại mã cũ, giữ dữ liệu vận hành và bảng thêm; không khôi phục đè bản sao cũ
vì sẽ mất công việc mới. Sao lưu SQLite bao gồm metadata phiên.

## Kiểm chứng và giới hạn

Ngày 17/11/2026, kiểm thử phần phiên gồm 15 bài mô-đun, 8 bài HTTP và 7 bài
JavaScript. Trình duyệt dùng dữ liệu tổng hợp kiểm desktop 1440 và mobile
390, đổi tên đã escape, xác nhận/hủy, thu hồi đơn lẻ/hàng loạt giữ phiên
hiện tại, cookie bị thu hồi nhận 401, lỗi mạng và thử lại. Không dùng phiên
người dùng thật để thử thu hồi. Cách chạy từ gốc kho trên Linux:

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_phien_web*.py' -v
node --test khong-gian/thu_phien_web.cjs
```

Đây chưa phải quản lý thiết bị được chứng nhận, MFA, SSO liên nền tảng hoặc
thu hồi mọi quyền của thiết bị. Quyết định của chủ quản ngày 17/11/2026:
mỗi doanh nghiệp/đơn vị có không gian dữ liệu riêng, chỉ chia sẻ khi được
cấp quyền. Lát cắt phiên web chưa triển khai cách ly dữ liệu theo đơn vị;
[kế hoạch chuyển đổi](../docs/nghien-cuu/V29-KHONG-GIAN-DON-VI.md) mô tả các
ranh giới và migration cần hoàn tất trước khi mở dữ liệu đa đơn vị thật.
