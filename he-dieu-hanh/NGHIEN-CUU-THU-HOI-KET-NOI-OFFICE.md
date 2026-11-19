# Thu hồi kết nối Office đang mở

Ngày tra cứu và ghi nhận: **18/11/2026**. Phạm vi: ranh giới kiểm quyền phía máy chủ cho ONLYOFFICE và bằng chứng từng lát trên stage; chưa bật production hoặc nghiệm thu toàn bộ giải pháp.

## Cổng cộng tác đang triển khai

Ngày **18/11/2026**, `cong_ket_noi_office.tao_cong` có bản thử độc lập bằng aiohttp 3.14.5 (phụ thuộc riêng `requirements-office-transport.txt`). Chỉ nhận đường `/office-docs/[version/]doc/<key>/c/` đã phân loại; upstream và bộ kiểm quyền là endpoint HTTP loopback cố định. Không nối vào gateway mặc định hoặc nginx production.

WebSocket kiểm quyền BDSG trước handshake, trước mỗi message hai chiều và định kỳ lúc nhàn rỗi. HTTP polling GET/POST có cùng kiểm quyền; yêu cầu đang chờ bị hủy khi mất quyền, buffer phản hồi tối đa 8 MiB và kiểm lại trước trả dữ liệu. Cookie chỉ gửi đến bộ kiểm quyền, không dùng cookie jar chung; lỗi bộ kiểm quyền chặn tiếp tục truyền. Origin ngoài bị từ chối; GET polling không có Origin vẫn kiểm cookie/quyền. Bộ bảo vệ không đọc hoặc sửa nội dung gói cộng tác, không tự phát hành lease.

Đã kiểm **7 ca qua HTTP/WebSocket loopback thật** ngày 18/11/2026: đóng socket nhàn rỗi hai đầu sau thu hồi, hủy polling đang chờ, polling GET thiếu Origin, giữ byte binary/POST hợp lệ, lỗi bộ kiểm quyền, từ chối origin/cookie/key sai và từ chối POST nén bằng HTTP 415. Body có `Content-Encoding` chưa được hỗ trợ; cổng tắt tự giải nén để không âm thầm đổi payload. Engine và bộ kiểm quyền trong các ca này là server tổng hợp; **chưa phải ONLYOFFICE thật**, chưa đo thông lượng/tải hoặc đóng nhiều worker, chưa xử lý đủ vòng đời tắt ứng dụng và chưa cấu hình nginx chuyển đường cộng tác qua cổng này. Không lấy kết quả này thay phép thử đỏ `public-04` phía trên hoặc tuyên bố lỗi sản phẩm đã vá.

Tiếp nối ngày **18/11/2026**: cổng giới hạn tối đa 64 yêu cầu/kênh đang xử lý (có thể giảm qua `max_connections`), từ chối thêm bằng 503; đây không phải giới hạn toàn bộ TCP keepalive ở nginx. Shutdown chặn kênh mới, hủy handler, đợi tối đa 2 giây rồi đóng transport còn giữ. Handshake upstream giới hạn 3 giây; HTTP polling tính cả đọc body tối đa 60 giây. Không tự theo redirect của WebSocket; hook aiohttp chặn trước request kế tiếp, tránh đi ra ngoài endpoint nội bộ.

CLI chỉ bind `127.0.0.1`, yêu cầu ba cổng riêng biệt và origin HTTPS. Có `--check` không mở socket; access log bị tắt khi chạy CLI. Ví dụ cấu hình thử tổng hợp, không phải cấu hình production:

```sh
python3 he-dieu-hanh/cong_ket_noi_office.py \
  --listen-port 18081 --engine-port 18082 --auth-port 18083 \
  --public-origin https://office-qa.example --max-connections 16 --check
```

Tổng **15 ca loopback đạt** ngày 18/11/2026, thêm giới hạn kênh, shutdown hai đầu/từ chối mở lại, chặn message mới hai chiều khi mất quyền, redirect, auth chậm và handshake chậm. Đây vẫn là engine/auth tổng hợp; chưa đo tải hoặc bảo đảm thu hồi trên engine thật. Mốc thu hồi được quan sát qua các lần kiểm quyền HTTP, không phải giao dịch nguyên tử với mỗi byte đã vào bộ đệm mạng.

Chẩn đoán tiếp ngày **18/11/2026**, nguồn `5ba0eed` với overlay chỉ ghi metadata: khi mở hai editor thật, thấy lần auth hết hạn ở 751/752 ms rồi pump/watch kết thúc; trước đó auth hợp lệ có lần mất 620 ms. Lần thử chưa tới bước thu hồi, không tính là phép đo bảo mật đạt hay đỏ. Deadline cũ 750 ms làm đóng kênh trong tải mở tài liệu; bản tiếp theo dùng 1,5 giây, vẫn chặn khi timeout/lỗi và không cache quyền. Hồi quy loopback với auth mất 1 giây phải mở/sửa được rồi ngắt sau thu hồi trong cửa sổ quan sát 5 giây. Tổng hiện **16 ca loopback đạt** ngày 18/11/2026; còn phải chạy lại SDK/engine thật với mã này. Không coi deadline hay phép cộng thời gian danh nghĩa là bảo đảm thời gian thực khi hệ thống quá tải.

Trước khi bật: cấu hình dịch vụ/nginx stage, giới hạn tài nguyên hệ điều hành, kiểm dưới tải và chạy lại CLI bằng engine thật trên nguồn mới; chứng minh cộng tác/thu hồi/reconnect/polling. [aiohttp ClientSession và WebSocket](https://docs.aiohttp.org/en/stable/client_reference.html), [gói aiohttp chính thức](https://pypi.org/project/aiohttp/).

## Kết luận để chọn hướng

Giữ cổng kiểm quyền HTTP, bổ sung lớp giữ và ngắt kết nối đang mở, kiểm dữ liệu cả hai chiều, bao phủ polling lẫn WebSocket. Các lát stage đã đo được ghi tại mốc hiện tại bên dưới; chưa suy thành nghiệm thu mọi transport hoặc nhiều worker. Dùng `drop` như biện pháp bổ sung để dừng sửa; không dùng riêng lệnh này làm bảo đảm thu hồi đọc. Cơ sở và giới hạn dưới đây tách riêng thông tin chính thức, suy luận thiết kế và quan sát thử nghiệm.

## Mốc hiện tại trên stage

Đo ngày **18/11/2026**, SDK/ONLYOFFICE thật, nguồn ứng dụng `3286eca`, dữ liệu tổng hợp, không client guard BDSG:

| Lát kiểm | Quan sát | Giới hạn |
|---|---|---|
| CLI công khai, polling-10 | SDK tự fallback sang HTTP; 5 sự kiện cộng tác trước thu hồi, 1 GET C đang chờ; auth mới 403, GET kết thúc trong 5 giây, polling mới 403 và 0 `saveChanges` sau mốc đó. | Thời điểm kết thúc tại interface trình duyệt. |
| CLI mặc định, WebSocket-11 | 20 sự kiện cộng tác trước thu hồi; auth mới 403, socket đóng trong 5 giây và 0 `saveChanges` sau mốc đó. | Word/WebSocket, không xóa dữ liệu đã tải trước đó. |
| Client độc lập, polling-12 | Sau cộng tác thật, giữ GET của SDK chưa chuyển tiếp; client TLS riêng dùng đúng SID/cookie đã xác thực, chờ ít nhất 2 giây trước thu hồi. Client riêng nhận HTTP 403 sau 374 ms từ ACK thu hồi; request mới cũng 403. Driver chưa thả hoặc hủy route GET trong lúc đo. | Driver riêng, không phải chế độ CLI công khai. Không dùng thời điểm SDK hủy request làm tín hiệu; không mở hai GET cùng SID tới engine hoặc tuyên bố đo trực tiếp thời điểm socket upstream đóng. |
| Tự kết nối lại, reconnect-14 | Đóng 1 WebSocket native bằng mã 4001; SDK tự tạo 1 kết nối mới, không reload trang hoặc thay cấu hình editor. C nhận 23 sự kiện sửa sau kết nối lại; canvas có phần dấu mới `AFTER RECONNECT reconnect-14`. | Có wrapper chỉ giữ tham chiếu constructor native để gây đóng transport; không sửa payload hoặc mã SDK. Không phải kiểm upgrade, mất mạng vật lý hay thu hồi trong lúc reconnect. |

Lát polling-12 dùng `HTTPSConnection` chuẩn với kiểm chứng thư/SNI; chỉ ánh xạ TCP về loopback của stage, không tắt TLS. URL, SID, cookie và body chỉ ở bộ nhớ; báo cáo chỉ chứa mã HTTP, timing và các điều kiện quan sát. C vẫn giữ nguyên trang editor, nên HTTP 403 của client riêng không phụ thuộc SDK tự hủy yêu cầu.

Reconnect-13 trước đó không tạo được điều kiện socket cũ đóng bằng thao tác route thử, dừng trước bước đo phục hồi. Không tính lần đó là sản phẩm lỗi hay nghiệm thu đạt. Reconnect-14 thay cách gây ngắt bằng socket native và kiểm cả socket cũ đóng, kết nối mới cùng dữ liệu mới tới người cộng tác.

Sau thử, stage đã dừng, firewall khớp trước thử và website chính vẫn R13. Nguồn `3286eca` được đối chiếu 642 tệp trước/sau; không diễn giải các phép thử riêng này thành luồng UI → nhân → HTTP → launcher đã hoàn tất. Các mục cũ bên dưới giữ nguyên bối cảnh và phạm vi tại thời điểm đo.

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

## Chế độ polling của công cụ nghiệm thu

Ngày **18/11/2026**, CLI thêm `--transport polling`; mặc định vẫn là `websocket`. Chế độ này chặn riêng WebSocket của tài liệu trong trình duyệt thử, không kết nối route đó tới engine, để chính SDK tự chuyển sang polling. HTTP GET/POST tiếp tục dùng cookie, gateway, cổng kiểm quyền và engine thật. Không thay response bằng dữ liệu cộng tác tổng hợp. [Playwright route_web_socket](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route-web-socket), [Socket.IO transport](https://socket.io/docs/v4/how-it-works/).

CLI yêu cầu GET/POST thành công của cả hai người, thay đổi thật đến người C và ít nhất một GET của C đang chờ trước khi thu hồi. Sau đó đo thời điểm request kết thúc, auth mới, yêu cầu polling mới và `saveChanges` sau cửa sổ 5 giây. Tập pending rỗng hoặc phản hồi 200 không quan sát được body không đủ bằng chứng: không được báo đạt. Observer chỉ đưa loại frame/mã trạng thái/timing vào báo cáo; body/URL có token chỉ ở bộ nhớ trong lúc quan sát. Hủy request được quan sát tại interface trình duyệt, chưa phải phép đo độc lập thời điểm ngắt socket upstream của engine.

```sh
python3 trien-khai/van-hanh/v29_thu_office_ws.py \
  --origin https://office-qa.example --bundle-dir /private/qa-bundle \
  --output-dir /private/qa-results/polling-01 --label polling-01 --transport polling
```

Kết quả polling có `transport=polling-only`, số lần chặn WebSocket, số HTTP 200, số GET pending, `revoked_poll_requests_ended_within_5s` và `new_poll_status_after_revoke`. Không dùng trường đóng WebSocket để mô tả polling. CLI vẫn thu hồi thành viên C thật trong đơn vị tổng hợp; không phát lại bundle cũ.

Thử riêng **polling-09 ngày 18/11/2026**, nguồn ứng dụng `58fe762`, SDK/engine thật và driver tiền thân riêng: SDK tự fallback khi mỗi người có 2 lần thử WebSocket bị chặn; 38/24 HTTP 200 cho A/C, 5 sự kiện cộng tác trước thu hồi, 1 GET C đang chờ. Thu hồi 200, auth mới 403, GET đang chờ kết thúc trong 5 giây, yêu cầu polling mới 403 và 0 `saveChanges` sau mốc đó; không lỗi đọc body. Chưa gọi đây là kiểm chạy lại bằng CLI công khai vừa thay đổi. Vẫn còn kiểm reconnect/upgrade không chặn, polling qua client độc lập không tự hủy, binary, tải và nhiều worker.

Nguồn SDK đóng gói có SHA256 `e47811041aa5c3470fc5c0920104ba94e93f47f9658d4547847b2fed0ed3e2a5`: đọc chuỗi cấu hình thấy thứ tự WebSocket/polling và đổi thứ tự khi connect lỗi. REA phân tích tĩnh toàn bundle dừng ở hạn provider, không phân tích xong AST; chỉ giữ được inventory/partial Evidence. Không dùng kết quả này chứng minh thực thi hoặc không có transport khác. Phép thử SDK thật bên trên mới là bằng chứng fallback đã xảy ra trong cấu hình đã chạy.

## Phương án phía máy chủ cần thử

Các điểm dưới là **đề xuất thiết kế chưa kiểm chứng**, dựa trên vòng đời HTTP/transport ở các nguồn trên:

1. Gắn mỗi kết nối với danh tính, đơn vị, tài liệu và phiên quyền do máy chủ xác thực. Đánh dấu quyền hết hiệu lực trước khi trả thành công thu hồi; chặn handshake, polling GET/POST và reconnect mới. Không tin `sid`, document key hay user id tự khai là đủ xác thực.
2. Giữ danh mục kết nối đang mở. Khi thu hồi, dừng chuyển dữ liệu cả client → engine lẫn engine → client, hủy polling đang chờ và đóng hai đầu WebSocket. Thông báo thu hồi giữa mọi worker giữ kết nối; kiểm quyền trước mỗi lần chuyển dữ liệu để bổ sung cho thông báo chủ động. Cần định nghĩa thứ tự xử lý và đo riêng dữ liệu đã ở bộ đệm trước mốc thu hồi.
3. Tách hai chính sách: thu hồi **ghi** có thể dùng `drop` và tiếp tục xem nếu còn quyền đọc; thu hồi **đọc** phải ngừng cấp dữ liệu mới qua mọi đường engine/tải tệp. Dữ liệu đã đến thiết bị không thể được coi là đã thu lại chỉ vì đóng kết nối.
4. Nếu dùng proxy Python, `aiohttp.WebSocketResponse` có nhận/gửi message và `close()` khởi động closing handshake, gọi được từ task khác. Đây chỉ là khả năng thư viện, chưa chứng minh proxy phù hợp engine. Phải kiểm binary, giới hạn bộ đệm, backpressure, hủy task và giới hạn thời gian đóng; không coi ping/heartbeat là kiểm quyền. [aiohttp WebSocketResponse](https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.WebSocketResponse).
5. Gọi `drop` có xác thực theo phiên bản engine như lớp bổ sung; kiểm `error`, ghi nhận lỗi và thử lại có kiểm soát. Bảo vệ ghi tại callback lưu vẫn cần giữ riêng: chặn lưu không thay thế việc ngăn cộng tác hoặc đọc tiếp. [ONLYOFFICE drop](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service/drop), [Command service](https://api.onlyoffice.com/docs/docs-api/additional-api/command-service).

## Bằng chứng cần trước nghiệm thu

Chạy engine thật với ít nhất hai danh tính thử; người bị thu hồi không có client guard. Kiểm riêng polling-only, WebSocket trực tiếp, polling → WebSocket và reconnect; nếu engine bật transport khác thì kiểm hoặc khóa rõ transport đó. Kiểm người còn quyền vẫn đọc/sửa được. [Các transport và nâng cấp](https://socket.io/docs/v4/how-it-works/).

Sau mốc thu hồi, thử gửi sửa từ người mất quyền và tạo dấu mới từ người còn quyền. Đo riêng dữ liệu được chuyển mỗi chiều, thời gian đóng, lần kiểm quyền mới và phiên bản thực sự lưu. Thử cả kết nối nhàn rỗi, đang có dữ liệu và thu hồi qua worker khác. Chỉ kết luận theo các lát và giới hạn đã đo; các kết quả stage ở trên chưa phủ hết tải, nhiều worker, upgrade, binary hoặc luồng giao diện đầy đủ.
