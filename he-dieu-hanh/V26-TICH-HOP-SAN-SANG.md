# V26 — sẵn sàng tích hợp và kiểm quyền khi dữ liệu đến muộn

Ngày kiểm tra: 17/11/2026. Phần này hoàn thiện điều kiện tại Thanh Hoá; không
thay tài khoản, hợp đồng hay sự phê duyệt của nhà cung cấp.

## Hành vi hoàn thiện

Danh sách kết nối bổ sung `readiness`:

- `can_attempt_read`: điều kiện cục bộ cho phép thử đọc; không khẳng định
  nhà cung cấp đang hoạt động hoặc đã được nghiệm thu.
- `blockers`: mã lỗi cấu hình kho khóa, thu hồi, hết hạn, quyền hoặc thời gian
  chờ hiện hành. Liệt kê trạng thái không gọi mạng và không trả chứng thư.
- `last_read_verified`: lần đọc của revision hiện tại đã đạt và không có điều
  kiện chặn hiện tại; mốc `checked_at` vẫn là thời điểm đo, không phải cam kết
  mọi thao tác hay thời điểm tương lai.

Cấu hình mới có thể thử đọc nhưng chưa được đánh dấu đọc thành công. Cập nhật
revision xóa mốc nghiệm thu cũ. Hết hạn hoặc thu hồi làm trạng thái sẵn sàng
thay đổi ngay khi đọc danh sách, không cần chờ lời gọi mạng thất bại.

`validate_read` dùng chung kiểm tra với lượt đọc: không tạo phiên đồng bộ mới
cho chứng thư đã hết hạn, provider đã từ chối quyền hoặc còn trong cooldown.
Trước đây chuẩn bị hợp đồng cục bộ có thể bỏ qua các trạng thái này.

Nếu chứng thư hết hạn trong thời gian chờ provider, payload trả về bị loại
trước khi chốt ledger. Lượt có trạng thái thất bại và không lưu payload. Khi
provider báo mất xác thực hoặc quyền, snapshot đồng bộ trước đó cũng bị chặn;
chủ quản cần cấp lại chứng thư và tạo phiên gắn revision mới. Pause/resume
không vượt được việc thu hồi từ nhà cung cấp.

## Bằng chứng kiểm thử

Ngày 17/11/2026, chạy bằng Python trên Windows với dữ liệu tổng hợp:

```sh
python -m unittest discover -s he-dieu-hanh -p 'thu_tich_hop_vn.py' -v
python -m unittest discover -s he-dieu-hanh -p 'thu_vn_dong_bo.py' -v
```

Kết quả: 30 bài tích hợp và 14 bài đồng bộ đạt, không bài skip. Có năm bài mới
kiểm trạng thái cục bộ không gọi mạng, hết hạn khi phản hồi đến, auth/cooldown
trong preflight và chặn snapshot/resume sau provider thu hồi. Bài bổ sung đổi
đồng hồ ngay sau BEGIN IMMEDIATE để mô phỏng hết hạn khi chờ SQLite: không
gửi request mới, không replay payload cũ, không chốt phản hồi đến muộn. Transport mô
phỏng; không sử dụng chứng thư, dữ liệu khách hàng hoặc API tính phí thật.
Các bài cũ giữ kiểm phân trang, quyền qua nhân, replay, restart, cancel đồng
thời, giới hạn dung lượng/trang, chữ ký thanh toán và chống DNS nội bộ.

## Phần chờ bên thứ ba

Danh mục `vn_hop_dong.py` tiếp tục ghi rõ `requires`, tài liệu chính chủ và
`contract_pending`. Mã đọc đã có không tương đương nghiệm thu tenant thật.
Cần tài khoản/quyền/token chính thức cho từng OA, Page, cửa hàng, doanh nghiệp
và merchant. meInvoice, VNPAY production và ngân hàng trực tiếp vẫn chờ hợp
đồng/đặc tả phù hợp; không suy đoán endpoint hay mở thao tác tài chính.

Không tự động OAuth/refresh, webhook, CDC, đồng bộ theo lịch hoặc hành động
ghi nghiệp vụ bên ngoài trong đợt này. Các phần đó cần được triển khai theo
quyền, sự phê duyệt và hợp đồng từng nền tảng; không đánh dấu hoàn tất thay
cho người cấp quyền. Dùng Google để đăng nhập không tự cấp quyền tích hợp.
