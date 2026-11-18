# Thu hồi kết nối Office đang mở

Ngày tra cứu và ghi nhận: **18/11/2026**. Phạm vi: chọn ranh giới kiểm quyền phía máy chủ cho ONLYOFFICE; tài liệu nghiên cứu, chưa triển khai hay nghiệm thu giải pháp.

## Kết luận để chọn hướng

**Đề xuất chưa kiểm chứng:** giữ cổng kiểm quyền HTTP, bổ sung lớp giữ và ngắt kết nối đang mở, kiểm dữ liệu cả hai chiều, bao phủ polling lẫn WebSocket. Dùng `drop` như biện pháp bổ sung để dừng sửa; không dùng riêng lệnh này làm bảo đảm thu hồi đọc. Cơ sở và giới hạn dưới đây tách riêng thông tin chính thức, suy luận thiết kế và quan sát thử nghiệm.

## Điều tài liệu chính thức xác nhận

| Thành phần | Hành vi được công bố | Ý nghĩa đối với thu hồi |
|---|---|---|
| Nginx `auth_request` | Quyết định theo mã HTTP của subrequest: 2xx cho phép, 401/403 từ chối. | Có thể chặn yêu cầu mới khi quyền mất hiệu lực. [Tài liệu module](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html). |
| Nginx WebSocket | Sau phản hồi `101`, Nginx thiết lập đường hầm giữa client và upstream. Thời gian chờ đọc là thời gian không có dữ liệu; ping upstream có thể đặt lại bộ đếm. | **Suy luận:** kết quả kiểm quyền ở handshake không tự trở thành kiểm quyền từng message. Giảm timeout không tạo giới hạn thu hồi khi kết nối vẫn có dữ liệu. [WebSocket proxying](https://nginx.org/en/docs/http/websocket.html). |
| ONLYOFFICE `drop` | Ngắt người dùng được chỉ định khỏi dịch vụ sửa; họ vẫn có thể xem. Từ phiên bản 8.3, không truyền `users` sẽ cấm sửa đối với mọi người đang sửa tài liệu theo `key`. | Là điều khiển quyền sửa, không phải cam kết chặn đọc hoặc xóa nội dung đã tải. Bảng tham số vẫn ghi `users` bắt buộc, nên cần kiểm phiên bản và thử hành vi bỏ trường này trước khi dùng. [Lệnh drop](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service/drop). |
| ONLYOFFICE Command service | Gửi POST JSON tới `/command`; trước 8.2 dùng `/coauthoring/CommandService.ashx`. Phản hồi có mã lỗi, trong đó `0` nghĩa là không lỗi; token phụ thuộc cấu hình. | Cần kiểm kết quả lệnh và đúng phiên bản, không chỉ mã HTTP. [Command service](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service). |
| Socket.IO / Engine.IO | Polling gồm GET nhận và POST gửi; WebSocket dùng kết nối hai chiều. Có nâng cấp transport và cơ chế kết nối lại. Tài liệu mới còn liệt kê WebTransport. | Phải kiểm transport engine thật cho phép, bao gồm đường kết nối lại. [Cách hoạt động](https://socket.io/docs/v4/how-it-works/), [giao thức Engine.IO](https://socket.io/docs/v4/engine-io-protocol/). |
| Middleware Socket.IO | `io.use` chạy một lần cho mỗi kết nối. Từ 4.6.0, `io.engine.use` chạy mỗi HTTP request, gồm upgrade. | **Suy luận:** middleware HTTP vẫn không thay việc quản lý WebSocket đã nâng cấp. Không mặc định phiên bản Socket.IO nhúng trong engine hỗ trợ API mới. [Middlewares](https://socket.io/docs/v4/middlewares/). |

Các trang trên không công bố rằng `drop` xóa cache trình duyệt, đóng mọi đường đọc hay hoàn tác thay đổi đã nhận. Không suy diễn các bảo đảm này từ tên lệnh.

## Bằng chứng thử nghiệm riêng và giới hạn

Theo ghi nhận được cung cấp ngày **18/11/2026**, với nguồn `38bf005`, môi trường stage dùng SDK/engine thật và hai người dùng, không có lớp bảo vệ client:

- Lệnh thu hồi trả HTTP 200; kiểm quyền engine mới chuyển từ 200 sang 403.
- WebSocket đã chấp nhận chưa đóng trong cửa sổ quan sát 5 giây; ghi nhận 24 frame `saveChanges` sau thu hồi.
- Canvas người dùng C hiển thị phần dấu `AFTER REVOKE 38BF`; phiên bản lưu vẫn là 1. Không khẳng định toàn bộ dòng đã nhập được nhận nguyên vẹn.

Lần lặp ngày **18/11/2026** bằng CLI bên dưới, cùng nguồn ứng dụng `38bf005` nhưng tài liệu và lease mới: nhận 24 sự kiện cộng tác trước thu hồi, kiểm quyền mới vẫn 200→403, socket gốc không đóng trong 5 giây và nhận 29 sự kiện `saveChanges` **sau mốc 5 giây**. Canvas C hiển thị phần dấu mới `AFTER REVOKE public-04`, phiên bản trong kho vẫn 1. CLI trả mã 2 với `secure_baseline=false`; đây là lỗi chức năng đã tái hiện, chưa được vá trong thay đổi tài liệu/công cụ này.

Đây là quan sát thử nghiệm riêng do nhóm thực hiện cung cấp, không phải kết quả được tài liệu hãng xác nhận hoặc phép đo lại trong nghiên cứu này. Frame gửi đi không tự chứng minh engine đã chấp nhận hay lưu thay đổi; phiên bản lưu không chứng minh dữ liệu mới không đi qua kênh cộng tác. Nội dung hiển thị sẵn cũng không đủ chứng minh có lần đọc mới: cần đối chiếu thời điểm tạo dấu và frame nhận từ người cộng tác sau thu hồi.

Không gọi đây là lỗi production đã tái lập: các công cụ editor và launcher đơn vị trên website còn đóng; production vẫn chạy R13. Không đưa địa chỉ máy chủ, cấu hình, dữ liệu hay đường dẫn riêng vào bằng chứng trong Git.

## Công cụ tái hiện trên môi trường thử

`trien-khai/van-hanh/v29_thu_office_ws.py` nhận bundle riêng và dùng Chromium/SDK/engine thật. Cần Playwright Python cùng Chromium đã có trong môi trường QA. Công cụ không nạp client guard: quyền phía máy chủ phải giữ được ngay cả khi client không tự đóng.

Người vận hành tạo trước đơn vị, dự án, Word, hai tài khoản thử có quyền sửa và tài khoản quản lý đơn vị. Bundle có hai tệp mode `0600`, không đưa vào Git:

- `credentials.json`: các khóa `root`, `a`, `c` chứa mật khẩu tạm của các tài khoản thử tương ứng.
- `fixtures.json`: `synthetic=true`, `source_commit` là commit nguồn đang chạy, `actors` gồm tên đăng nhập `owner`, `a`, `c`; `unit` và `file` là ID tài nguyên thử. `a`/`c` còn chứa kết quả `SoanThaoOffice.open` của từng tài khoản, gồm `key` và `config`. Hai kết quả phải có cùng key, đúng user và `documentType=word`. Tạo các quyền trước khi mở để tham chiếu phiên không bị cũ.

Chạy bằng user QA không đặc quyền và thư mục đầu ra mới:

```sh
python3 trien-khai/van-hanh/v29_thu_office_ws.py \
  --origin https://office-qa.example \
  --bundle-dir /private/qa-bundle \
  --output-dir /private/qa-results/probe-01 \
  --label probe-01
```

Nếu trình duyệt chạy cùng máy với proxy TLS thử, `--loopback` ánh xạ hostname về loopback mà vẫn kiểm chứng thư HTTPS. Điểm nhập mặc định `430,300` ứng với viewport `1440×1000` đã dùng ngày 18/11/2026; có `--click-x/--click-y` để chỉnh theo hình học engine khác. Công cụ kiểm thay đổi thực sự đến người C trước khi bắt đầu thu hồi.

**Tác động thực:** công cụ thu hồi thành viên C trong đơn vị thử và giữ thay đổi này kể cả bài kiểm thất bại. Không dùng đơn vị, tài khoản hoặc tài liệu khách hàng. Chuẩn bị bundle mới và phiên mở mới cho lần chạy sau; không phát lại fixture đã bị thu hồi.

Mã thoát `0` khi các socket đã mở được đóng trong 5 giây và không nhận `saveChanges` sau mốc đó; `2` khi phép đo hợp lệ phát hiện thiếu bảo đảm này. Lỗi tham số và các đối chiếu bundle được CLI chủ động từ chối có mã `3`; lỗi đọc/giải mã bundle hoặc thực thi khác có thể có mã `1`, không tính là phát hiện thu hồi. `result.json` và ảnh chỉ giữ dữ liệu tổng hợp, không có frame thô, cookie hoặc token. Bundle đầu vào chứa thông tin xác thực và phải tiếp tục được giữ riêng. Đây là bài kiểm WebSocket Word; polling-only, reconnect, binary và tài liệu khác vẫn cần nghiệm thu riêng.

## Phương án phía máy chủ cần thử

Các điểm dưới là **đề xuất thiết kế chưa kiểm chứng**, dựa trên vòng đời HTTP/transport ở các nguồn trên:

1. Gắn mỗi kết nối với danh tính, đơn vị, tài liệu và phiên quyền do máy chủ xác thực. Đánh dấu quyền hết hiệu lực trước khi trả thành công thu hồi; chặn handshake, polling GET/POST và reconnect mới. Không tin `sid`, document key hay user id tự khai là đủ xác thực.
2. Giữ danh mục kết nối đang mở. Khi thu hồi, dừng chuyển dữ liệu cả client → engine lẫn engine → client, hủy polling đang chờ và đóng hai đầu WebSocket. Thông báo thu hồi giữa mọi worker giữ kết nối; kiểm quyền trước mỗi lần chuyển dữ liệu để bổ sung cho thông báo chủ động. Cần định nghĩa thứ tự xử lý và đo riêng dữ liệu đã ở bộ đệm trước mốc thu hồi.
3. Tách hai chính sách: thu hồi **ghi** có thể dùng `drop` và tiếp tục xem nếu còn quyền đọc; thu hồi **đọc** phải ngừng cấp dữ liệu mới qua mọi đường engine/tải tệp. Dữ liệu đã đến thiết bị không thể được coi là đã thu lại chỉ vì đóng kết nối.
4. Nếu dùng proxy Python, `aiohttp.WebSocketResponse` có nhận/gửi message và `close()` khởi động closing handshake, gọi được từ task khác. Đây chỉ là khả năng thư viện, chưa chứng minh proxy phù hợp engine. Phải kiểm binary, giới hạn bộ đệm, backpressure, hủy task và giới hạn thời gian đóng; không coi ping/heartbeat là kiểm quyền. [aiohttp WebSocketResponse](https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.WebSocketResponse).
5. Gọi `drop` có xác thực theo phiên bản engine như lớp bổ sung; kiểm `error`, ghi nhận lỗi và thử lại có kiểm soát. Bảo vệ ghi tại callback lưu vẫn cần giữ riêng: chặn lưu không thay thế việc ngăn cộng tác hoặc đọc tiếp. [ONLYOFFICE drop](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service/drop), [Command service](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service).

## Bằng chứng cần trước nghiệm thu

Chạy engine thật với ít nhất hai danh tính thử; người bị thu hồi không có client guard. Kiểm riêng polling-only, WebSocket trực tiếp, polling → WebSocket và reconnect; nếu engine bật transport khác thì kiểm hoặc khóa rõ transport đó. Kiểm người còn quyền vẫn đọc/sửa được. [Các transport và nâng cấp](https://socket.io/docs/v4/how-it-works/).

Sau mốc thu hồi, thử gửi sửa từ người mất quyền và tạo dấu mới từ người còn quyền. Đo riêng dữ liệu được chuyển mỗi chiều, thời gian đóng, lần kiểm quyền mới và phiên bản thực sự lưu. Thử cả kết nối nhàn rỗi, đang có dữ liệu và thu hồi qua worker khác. Chỉ kết luận mức bảo đảm cùng giới hạn thời gian đã đo; chưa có phép đo của lớp bảo vệ máy chủ trong tài liệu này.
