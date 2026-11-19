# V19 — bộ soạn thảo, quét virus và đầu nối Google

Cập nhật ngày **15/11/2026**. Nối tiếp [V18](V18-TRUYEN-TEP.md), không thay
đổi mô hình AI, trọng số hoặc quyền MCP của các nền tảng BDSG.

## Phần đã thực hiện và kiểm thật

- Tạo tài liệu DOCX, XLSX và PPTX; mở ONLYOFFICE Docs tự vận hành trong trang
  soạn thảo riêng. Giữ nhãn của engine, không đổi thành thương hiệu giả.
- Sửa, lưu phiên bản mới, tải về và mở lại từ kho BDSG; giữ lịch sử và so
  sánh revision. Bài thử XLSX có công thức và kiểm giá trị được lưu.
- Người có quyền sửa cùng dự án dùng chung key. Snapshot chỉ xác nhận khi
  callback ký hợp lệ, bytes đã kiểm/quét và giao dịch lưu thành công.
- Nút Lưu chờ editor gửi thay đổi, chờ snapshot thực sự; lỗi hoặc hết thời
  gian không báo thành công. Lỗi force-save có thể thử lại trong cùng phiên.
- Một người đóng không làm người cùng sửa phải đóng. Đổi quyền, lưu trữ dự
  án hoặc thu hồi tài khoản khóa phiên chung trong chính giao dịch đổi
  quyền, rồi gửi lệnh ngắt Docs. CLI thu hồi cũng đi qua ranh giới này.
- ClamAV chạy qua Unix socket; tệp bị phát hiện, quá hạn chữ ký hoặc lỗi
  quét không được xuất bản. Quét được áp dụng cho phiên bản mới, khôi phục,
  callback editor và nhập Google; tệp Office cũ được quét lại trước tải.
  Kho tài liệu TXT/PDF cũ cũng quét trước nhận và tải tệp.
- Đã thử bộ quét thật: mẫu kiểm tra EICAR bị chặn trước khi tạo tệp trong
  kho thử; tệp tổng hợp thông thường được chấp nhận. Không thử mã độc thật.

## Google: mã tích hợp và phần cần tài khoản thật

Mã đã có OAuth Web client + PKCE, state một lần, gắn với phiên BDSG còn hiệu
lực và cookie phụ Lax; cookie đăng nhập BDSG vẫn Strict. Token mã hóa AES-GCM
theo từng người; làm mới token và thu hồi quyền thật khi ngắt kết nối. Không
đọc cookie Google hoặc lấy token của plugin làm thông tin đăng nhập hệ thống.

Có Google Picker để người dùng cấp quyền tệp có sẵn; scope `drive.file`, danh
sách tệp đã cấp, nhập bản sao Docs/Sheets/Slides thành DOCX/XLSX/PPTX, xuất
bản sao OOXML lên Drive. Nhập và xuất có mã thao tác và ledger để thử lại
sau mất phản hồi; xuất đối soát ID cố định thay vì tạo lại mù. Tệp lớn dùng
resumable upload. Không tự đồng bộ hai chiều hoặc tự sửa tệp Google gốc.

**Chưa nghiệm thu Google OAuth/Picker/import/export/refresh/revoke bằng tài
khoản Google thật.** Cần chủ quản hoàn tất Cloud project, Web client, Picker
và cấp quyền trên hồ sơ trình duyệt BDSG riêng. Khi thiếu cấu hình, giao diện
hiển thị đang chờ thiết lập, không báo đã kết nối. Bài kiểm dùng phản hồi
tổng hợp chỉ xác minh hợp đồng chương trình và các tình huống lỗi.

## Bằng chứng và giới hạn

Đo ngày 15/11/2026: phát hiện **142** bài kiểm Python, **127** đạt, **15** bỏ
qua vì môi trường kiểm không bật Chromium/runtime/PDF cách ly tương ứng.
Các bài kiểm mới của Office/Google đều chạy; có kiểm tranh chấp thu hồi quyền
trong lúc snapshot chờ và ngắt Google khi callback kết nối lại đang chạy.
Các phép thử trình duyệt với engine và ClamAV thật chạy riêng trên kho tổng
hợp, gồm ba loại tài liệu, công thức, cộng tác và thu hồi quyền. Không ghi
dữ liệu thử vào kho vận hành.

Editor Community trên điện thoại chưa nằm trong phạm vi được cung cấp;
giao diện hướng dẫn về kho tệp. Tệp vẫn tối đa 8 MiB; hạn mức lịch sử của
dự án từ V18 còn áp dụng. Không nhận macro, OLE hoặc gói Office lỗi/vượt giới
hạn; kiểm cấu trúc không thay bộ quét virus. Kết quả quét là bằng chứng tại
thời điểm quét, không bảo đảm phát hiện mọi mã độc.

Khi thu hồi một thành viên trong phiên chung, không thể tách đáng tin các
thay đổi chưa commit của từng người: hệ thống giữ bản đã lưu và khóa cả
phiên, những người còn quyền mở lại từ bản đã lưu. Khi xuất Google, đóng
editor và chờ phiên chung lưu xong để không xuất nhầm bản cũ.

Xem [cấu hình vận hành](../trien-khai/office/README.md),
[API chính chủ ONLYOFFICE](https://api.onlyoffice.com/docs/docs-api/),
[Google Web OAuth](https://developers.google.com/identity/protocols/oauth2/web-server).
