# Văn phòng tự vận hành — cấu hình kiểm ngày 15/11/2026

Ứng dụng giữ tệp, lịch sử và quyền dự án trong kho riêng. ONLYOFFICE Docs là
dịch vụ độc lập, giữ nguyên nhãn và giấy phép của nhà cung cấp; không chép mã
engine vào giấy phép Apache của BDSG. Tài liệu API và giới hạn edition:
[Docs API](https://api.onlyoffice.com/docs/docs-api/),
[Community FAQ](https://helpcenter.onlyoffice.com/docs/installation/community/faq).
Editor Community được nghiệm thu trên máy tính; giao diện điện thoại hướng
dẫn tải/nhập tệp, không hứa có editor mobile của bản thương mại.

## ONLYOFFICE

Image đã kiểm: `onlyoffice/documentserver:10.0.0.1`, manifest digest
`sha256:ca17889f10b11141cc6441836aebdd2835cf3e1b49681b2fd6e155c94b7850b3`.
Chỉ publish `127.0.0.1:8088:80`, không mở thêm cổng Internet. Mount riêng
`/var/www/onlyoffice/Data`, `/var/lib/onlyoffice`, `/var/log/onlyoffice`.
Giữ volume khi thay container; không mount kho BDSG hoặc Docker socket vào Docs.

Tệp môi trường riêng của engine, quyền `0600`, ngoài Git/web:

```text
JWT_ENABLED=true
JWT_SECRET=<bí mật ngẫu nhiên tối thiểu 32 byte>
JWT_HEADER=Authorization
JWT_IN_BODY=true
TZ=Etc/UTC
```

Gateway dùng cùng bí mật trong `BDSG_OFFICE_JWT_SECRET`. Không đưa tệp môi
trường vào web root, câu lệnh có bí mật hoặc bản mô tả Pull Request.

Ngày 18/11/2026: gateway hỗ trợ `BDSG_OFFICE_INTERNAL_PORT` trong môi trường
vận hành để tách engine thử riêng. Mặc định vẫn `8088`, host luôn
`127.0.0.1`; không nhận host/cổng từ công cụ hoặc HTTP. Chỉ nhận số ASCII
từ 1 đến 65535, cấu hình sai làm khởi tạo thất bại, không tự dùng mặc định.
Command và tải kết quả dùng cùng cổng đã chụp lúc khởi tạo; đổi biến môi
trường không đổi đối tượng đang chạy. URL callback loopback phải khớp cổng
này; URL HTTPS cùng origin/prefix được tải qua đúng engine nội bộ đã chọn.
Khi tách stage phải dùng container, secret, dữ liệu và proxy riêng; đặt cổng
gateway không tự cấu hình hoặc tạo container. Chưa thay cấu hình production.

Không bật `ALLOW_META_IP_ADDRESS`. Không tắt kiểm JWT để sửa lỗi kết nối.
Docs phải tải được nguồn HTTPS chính thức và gửi callback về gateway; nếu
dùng CDN, kiểm route origin phù hợp thay vì tắt bảo vệ toàn tên miền.

Reverse proxy dưới `/office-docs/` theo
[mẫu chính chủ](https://github.com/ONLYOFFICE/document-server-proxy/blob/master/nginx/proxy-to-virtual-path.conf):
WebSocket, `X-Forwarded-Host` có hậu tố `/office-docs`, proto từ nginx.
Mọi tài nguyên engine yêu cầu phiên BDSG; cache và WebSocket phải qua
`/api/office-engine-auth` với đường dẫn gốc do nginx ghi đè. Không tin header
đường dẫn tự gửi từ Internet, không để truy cập trực tiếp cổng engine.
Tắt access log của nguồn/callback/cache vì URL có khả năng truy cập riêng.

Chỉ nới CSP cần cho mã của nhà cung cấp ở location engine; giữ CSP nghiêm cho
portal. Dùng `SAMEORIGIN` cho iframe engine, không nới frame-ancestors portal.
Nguồn và callback có xác thực JWT máy riêng, không dùng cookie trình duyệt.

## ClamAV

Cài `clamav-daemon` và `clamav-freshclam` từ kho hệ điều hành. Cần tải thành
công cơ sở nhận diện chính thức trước khi bật luồng ghi/tải tệp:
[quét](https://docs.clamav.net/manual/Usage/Scanning.html),
[cập nhật](https://docs.clamav.net/manual/Usage/SignatureManagement.html).

```text
LocalSocket /run/clamav/clamd.ctl
LocalSocketGroup <nhóm dịch vụ gateway>
LocalSocketMode 660
EnableVersionCommand true
EnableReloadCommand true
EnableShutdownCommand false
AlertExceedsMax true
MaxScanTime 10000
MaxThreads 2
```

Không cấu hình TCP socket công khai. Gateway dùng
`BDSG_CLAMAV_SOCKET=/run/clamav/clamd.ctl`; daemon chạy UTC, giới hạn quét
không nhỏ hơn giới hạn tệp/giải nén của BDSG. Lỗi, giới hạn hoặc chữ ký quá
hạn chặn xuất bản/tải tệp. Không cấu hình quét ở môi trường phát triển thì
hiển thị “chưa quét”, không biến thành kết quả sạch. Không có cam kết phát
hiện mọi mã độc. Kiểm EICAR trong RAM với kho thử, không tải mã độc thật.

## Google Drive, Docs, Sheets, Slides

Cần Cloud project của chủ quản, bật Drive API và Picker API, OAuth Web client,
API key Picker giới hạn API/referrer, project number. Đăng ký chính xác:
`https://<tên-miền>/api/google/callback`; origin JavaScript cùng tên miền.
Chỉ scope `https://www.googleapis.com/auth/drive.file`. Picker cấp quyền các
tệp có sẵn; danh sách Drive chỉ gồm tệp người dùng đã cấp hoặc ứng dụng tạo.
Không dùng token của plugin, cookie Google hoặc tài khoản dùng chung.

Tệp OAuth JSON riêng của gateway theo định dạng download Web client, thêm
`picker_api_key` và `project_number` vào object `web`. Các trường bắt buộc:
`client_id`, `client_secret`, `redirect_uris`. Không nhập bí mật vào tài liệu này.

```text
BDSG_GOOGLE_CLIENT_FILE=<tệp OAuth riêng>
BDSG_GOOGLE_VAULT_KEY_FILE=<tệp nhị phân ngẫu nhiên 32 byte riêng>
```

Cài dependency tùy chọn từ `requirements-office.txt` trong môi trường gateway.
Tệp cấu hình/khóa chỉ root và tài khoản dịch vụ đọc được. Giữ khóa vault trong
bản sao lưu riêng có bảo vệ; mất khóa thì phải kết nối lại, không giải mã được
token từ bản sao SQLite. Không dùng mật khẩu người dùng để làm khóa vault.

Mỗi người tự đăng nhập/cấp quyền Google. PKCE, state một lần, cookie phụ Lax
và phiên BDSG còn hiệu lực được kiểm đồng thời; không nới cookie BDSG Strict.
Token mã hóa AES-GCM theo người dùng. Thu hồi quyền thật khi ngắt kết nối;
refresh lỗi không tự chuyển tài khoản. Chế độ Testing của ứng dụng Google có
giới hạn người dùng/thời hạn cấp quyền: phải kiểm cấu hình trước khi vận hành
rộng, không coi tài khoản thử là đã phát hành ứng dụng Google.

Nhập tạo bản sao riêng và quét trước khi xuất bản. Docs/Sheets/Slides được
xuất lần lượt DOCX/XLSX/PPTX; giới hạn BDSG 8 MiB vẫn áp dụng. Xuất Drive tạo
bản sao OOXML, không tự chuyển thành tệp Google gốc hoặc đồng bộ hai chiều.
Tệp lớn dùng resumable upload; ID và ledger cố định phục vụ đối soát khi mất
phản hồi. Nhập có request key và ledger nguyên tử với tệp BDSG.

## Nghiệm thu và khôi phục

Thử trên kho tổng hợp riêng: mở/sửa/lưu/mở lại ba loại tệp; công thức tính;
hai người cùng phiên; thu hồi quyền trong lúc callback chờ quét; retry sau
lỗi lưu; lặp callback; sai JWT/URL; mẫu EICAR; scanner dừng/chữ ký quá hạn.
Google cần thêm bài thử OAuth/Picker/import/export/refresh/revoke với tài
khoản thật. Bài kiểm giả lập không chứng minh đã kết nối tài khoản Google.

Trước triển khai giữ cấu hình nginx, gateway, daemon, image digest, volume,
bản sao SQLite nhất quán, dấu SHA và bản phát hành trước. Khôi phục mã/cấu hình
không tự thay SQLite bằng bản cũ và làm mất tài liệu mới. Không xóa dữ liệu
người dùng để quay lại bản trước. Nghiệm thu lại HTTPS, quyền và tải tệp.
