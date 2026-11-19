# V29 R3 — HTTP và tác vụ trong phạm vi đơn vị

Ngày kiểm: 17/11/2026. Thêm chế độ thử `UngDung(..., unit_preview=True)`
trên dữ liệu tổng hợp; không có cờ CLI/environment tự bật nhiều đơn vị.
Mặc định vẫn là không gian hiện có và từ chối khởi động trên kho đã tạo
đơn vị. Chưa bật tenant hoặc chạy migration trên dữ liệu production.

## Xác thực và HTTP thử nghiệm

Cookie xác thực danh tính; `X-BDSG-Unit` chỉ đề nghị đơn vị, `DonVi.bind`
kiểm membership còn hiệu lực. Giữ chốt Origin, `X-BDSG-Actor`, schema,
giới hạn body và cổng ghi. `/api/me` chỉ trả id/name/role; không xuất scope
trong bộ nhớ. Chủ quản hệ thống quản trị vòng đời đơn vị, không tự có quyền
nội dung; quản trị đơn vị quản lý thành viên đúng đơn vị.

Các đường thêm trong preview: GET/POST `/api/units` và `/api/units/members`.
Dự án, tài liệu, lưu trữ Office và tác vụ thuần kịch bản vẫn đi qua nhân.
Chia sẻ xuyên đơn vị dùng công cụ `don_vi.chia_se_du_an`, ghi đích danh người
và đơn vị nhận. Chưa có UI chọn đơn vị hoặc phân tách cache/window theo đơn vị.

GET `/api/tasks`, `/api/task` và các công cụ `cong_viec` kiểm cookie cùng
đơn vị trước dispatch. MCP, Google, editor/callback Office, runtime, cấu
hình AI/connector và các công cụ chưa chuyển phạm vi bị chặn. Tài khoản
Bearer không thay cookie hoặc tự chọn đơn vị để vượt chốt này.

## Tác vụ giữ quyền đã giao

Tác vụ có đơn vị trong document và mapping riêng, giữ bảng tác vụ cũ nguyên
cấu trúc. Liệt kê/chi tiết/hủy/tiếp tục theo owner cùng đơn vị; vai quản trị
không bypass. Tác vụ cũ chưa phân đơn vị không tự được gán hoặc hiển thị.
Restart đánh dấu lượt chưa kết thúc là gián đoạn, không tự chạy lại.

Worker nhận số lượt và tham chiếu quyền bất biến lúc submit. Tham chiếu
chỉ lấy từ kho máy chủ tin cậy, không là chứng thư đăng nhập. Khôi phục
worker kiểm lại membership, revision, đơn vị và quyền dự án. Đổi đơn vị
trên caller, revoke/rejoin hoặc đổi vai vòng không chuyển worker cũ sang
quyền mới. Tiếp tục phải là thao tác rõ ràng của chủ tác vụ với phạm vi mới
còn hiệu lực; quyền dự án được kiểm lại trong giao dịch.

Hủy Future đang xếp hàng rồi tiếp tục không khiến Future cũ thực hiện lượt
mới. Generation được kiểm ở đọc, ghi và chuyển trạng thái; callback provider
trên thread khác giữ generation đã giao. Callback hoặc worker cũ thoát mà
không ghi/dừng lượt mới. Khi mất quyền, ghi dừng chỉ lấy bản đã lưu và cập
nhật trạng thái cố định, không nhận nội dung đến muộn. Kiểm quyền và lưu
kết quả nằm trong cùng giao dịch ghi. Lời gọi đã bắt đầu không thể bị thu hồi
hồi tố; dữ liệu/báo cáo hợp lệ đã lưu không bị xóa bởi việc thu hồi này.

Trong preview, tác vụ mới chỉ dùng danh mục công khai, không đọc đầu nối
toàn cổng hoặc gọi provider AI. Mô hình đã cấu hình toàn cổng, ngân sách,
MCP ngoài, Python, browser, drafts và delegation đều chưa được cấp cho đơn
vị. Bước đầu nối chưa sẵn sàng có `tool=None`, báo cáo không giả đã kiểm
kết nối. Ngữ cảnh snapshot của dự án chia sẻ giữ `source_unit_id`, tách
khỏi đơn vị đang làm việc và đơn vị sở hữu tác vụ.

## Bản sửa từ rà soát

- Tách revision của scope khỏi epoch của grant: thay vai luôn vô hiệu hóa
  scope cũ, kể cả đổi vòng; grant vẫn dùng được khi bind mới và chưa revoke.
- Migration chạy lại kiểm dữ liệu mồ côi trước nhánh marker.
- Generation của worker/callback chặn thực thi trùng hoặc ghi vào lượt mới.
  Bản sửa generation áp dụng cả luồng hiện có, không chỉ preview đơn vị.

Kiểm ngày 17/11/2026 trên Linux: 352 bài ứng dụng, 337 đạt/15 bỏ qua theo
điều kiện môi trường; 46 bài vận hành và 4 bài đóng gói đạt. Các kiểm mới
dùng SQLite/tệp tạm, cookie HTTP thật và provider tổng hợp; không gọi API
tính phí hoặc sử dụng dữ liệu khách hàng. Chạy từ gốc kho:

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_*.py' -v
python3 -m unittest discover -s trien-khai/van-hanh -p 'thu_*.py' -v
python3 trien-khai/thu_giao_dien.py -v
```

## Cổng chưa đạt trước production đa đơn vị

Chưa chuyển lịch, mailbox/actions/delegation, browser/runtime, ngân sách và
chứng thư AI/MCP/Google, participant grant/callback Office, namespace khóa
idempotency tệp, audit/search/export/retention, cache/UI đơn vị và token
MCP bound-unit. Còn phải migration đầy đủ tác vụ/quyền cũ và diễn tập gateway
tenant từ bản phục hồi, cutover/rollback. Không dùng preview làm bằng chứng
toàn V29 hoàn tất hoặc đã liên thông nền tảng nghiệp vụ thật.

Xem [backend dự án/tệp R2](V29-R2-DON-VI-DU-AN.md),
[phạm vi phiên web](V29-PHIEN-WEB.md) và
[bản đồ chuyển đổi](../docs/nghien-cuu/V29-KHONG-GIAN-DON-VI.md).
