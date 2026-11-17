# V26 — hoàn thiện độ tin cậy và điều khiển đồng bộ

Đo ngày **17/11/2026**, tiếp nối V25. Ba nhóm phát triển độc lập xử lý lõi
tác vụ, Office và đầu nối; phần ghép bổ sung điều khiển đồng bộ trên website.
Đây là bản nâng cấp có phạm vi kiểm chứng, không phải xác nhận đã hoàn tất
mọi khả năng của Manus, Microsoft Office hoặc mọi dịch vụ bên ngoài.

## Hành vi dùng được thêm

- **Quản lý kết nối → Ứng dụng Việt Nam** có tạo phiên từ thao tác đọc hiện
  tại, chạy từng trang, tạm dừng, tiếp tục, hủy và xem snapshot. Tạo phiên
  không gọi mạng. Mỗi lần chạy là một bước; không tự động chạy nền.
- Checkpoint giữ qua tải lại. Khóa tạo được giữ khi mất phản hồi để thử lại
  không tạo trùng. Hủy/tạm dừng vẫn dùng được trong lúc chờ provider; phản
  hồi muộn không ghi thêm trang hoặc ghi đè thông báo thao tác mới.
- Đầu nối thiếu điều kiện cục bộ không xuất hiện trong lựa chọn đọc. API
  trả readiness theo thời hạn, quyền, kho chứng thư và cooldown, tách khỏi
  bằng chứng đọc thật. Không dùng trạng thái đã lưu để khẳng định kết nối.
- Tác vụ bị dừng hoặc danh tính bị thu hồi trong lúc tổng hợp không xuất
  báo cáo mới. Mô hình trả sau deadline bị từ chối nhưng usage vẫn được giữ.
- Google Office kiểm cấu trúc phản hồi và đúng ID tệp trước khi chốt xuất
  thành công; phản hồi không chắc chắn còn chờ đối soát. Bộ quét thiếu Unix
  socket báo chưa sẵn sàng và chặn xuất bản.

Chi tiết: [lõi tác vụ](V26-LOI-TAC-VU.md),
[Office](V26-OFFICE-TIN-CAY.md), [tích hợp](V26-TICH-HOP-SAN-SANG.md).

## Kiểm chứng

Ngày 17/11/2026 trên Linux: **253** bài ứng dụng, **238** đạt và **15** bỏ
qua theo môi trường. **4** bài đóng gói đạt; cú pháp JavaScript và ba chương
trình hồi quy giao diện hiện có đạt. Dùng thư mục dữ liệu tạm và transport
tổng hợp, không gọi API tính phí trong đợt kiểm này.

```sh
python -m unittest discover -s he-dieu-hanh -p 'thu_*.py' -v
python trien-khai/thu_giao_dien.py -v
node --check khong-gian/tich-hop-vn.js
node khong-gian/thu_mo_dun.cjs
node khong-gian/thu_xuong.cjs
node khong-gian/thu_tro_ly.cjs
```

Trình duyệt với backend thật và provider tổng hợp đã kiểm tạo/chạy/dừng/
tiếp tục/hủy/xem trang, tải lại giữ checkpoint, lỗi/thử lại, pause trong lúc
provider chậm, văn bản provider được escape. Desktop 1440 và mobile 390 không
tràn ngang hoặc lỗi JavaScript. Bằng chứng riêng không chứa dữ liệu vận hành.
Review mã theo Standards và Spec đã xử lý hai lỗi bắt buộc: nút ngắt trong
lượt đọc và kiểm hết hạn sau khi lấy khóa SQLite. Review giao diện chấm sửa
độ dễ đọc nhãn trạng thái resolved, disposition ship ở phạm vi sửa đó.

## Phần đã chuẩn bị và phần còn phải làm

| Nhóm | Có thể dùng/đã chuẩn bị | Điều kiện hoặc công việc còn lại |
|---|---|---|
| Google đăng nhập | Public V25, quyền operator, danh tính riêng | Giữ chính sách Google riêng; không cấp quyền Drive |
| Google Office | OAuth/PKCE, token mã hóa, Picker, import/export, refresh/revoke và kiểm hợp đồng | Cloud/Picker, consent drive.file và nghiệm thu bằng tài khoản thật |
| Mô-đun BDSG/MCP | Danh mục, cấu hình endpoint/chứng thư, quyền công cụ, kiểm tra giao thức | Quản trị từng nền tảng cấp endpoint và quyền; nghiệm thu từng nghiệp vụ |
| Dịch vụ Việt Nam | Adapter đọc, vault, trạng thái, checkpoint và UI điều khiển | Tài khoản/hợp đồng/quyền thật; OAuth riêng, webhook và hành động ghi là phần phát triển tiếp, không chỉ nhập khóa |
| Ngân hàng/hóa đơn | Mục chờ điều kiện, không tự bật công cụ giao dịch | Đặc tả/chứng thư/sandbox và hợp đồng; xây adapter sau khi chốt hợp đồng |
| AI | Danh mục model, chọn tự động/thủ công, ngân sách, adapter; Claude đã có bằng chứng V23 | Chỉ dùng API được cấu hình; chưa dùng tín dụng gói ChatGPT thay API |
| Office tự vận hành | Engine Office và ClamAV có bằng chứng V19 | Không cam kết tương đương toàn bộ tính năng Microsoft/Google hoặc editor Community trên điện thoại |
| Khôi phục | Snapshot SHA/restore cục bộ và giữ release trước | Nơi sao lưu ngoài máy và phép đo RPO/RTO còn chưa hoàn tất |

Mã nguồn đo ngày 17/11/2026 bằng `python trien-khai/do_ma_nguon.py`:
**63.807** dòng theo phương pháp đã chốt, có mã kiểm thử, không tính tài liệu/
JSON/ngữ liệu. Mục tiêu **110.622** dòng chưa đạt; không chèn mã đệm để đạt số.
Các phần phát triển tiếp trong bảng không được gộp thành “chỉ chờ bên thứ ba”.

## Triển khai

Đóng gói đầy đủ source và web, snapshot/kiểm SHA/thử restore trước đổi bản;
giữ release V25, cấu hình và dữ liệu riêng ngoài web/Git. Kiểm không có tác
vụ/editor đang chạy trước dừng gateway. Chuyển unit và symlink sang release
mới; nếu readiness hoặc Google public sai thì quay về unit/symlink cũ.
Biên bản triển khai và commit thực tế được xuất riêng sau khi kiểm production.
Pull Request đóng góp tiếp tục là draft, không tự merge kho chính.
