# R14 — cổng soạn thảo đơn vị thử nghiệm

Cập nhật **18/11/2026**. Có opt-in backend qua nhân/HTTP và giao diện đơn vị theo capability. Đã kiểm luồng cơ bản Word/Excel/PowerPoint từ vỏ BDSG đến engine thật trong môi trường thử; chưa bật production hoặc nghiệm thu toàn bộ R14. Các bằng chứng transport trước đó ở [nghiên cứu kết nối Office](NGHIEN-CUU-THU-HOI-KET-NOI-OFFICE.md) có phạm vi riêng với các phép đo giao diện dưới đây.

## Cách bật trong gateway thử riêng

Constructor `UngDung(..., unit_preview=True, unit_office_preview=True)` mở đúng năm công cụ editor: `van_phong.tao_office`, `mo_soan_thao`, `luu_soan_thao`, `phien_soan_thao`, `bo_phien_soan_thao`. Mặc định `unit_office_preview=False`. Cờ phải là boolean và chỉ được dùng với gateway đơn vị; cấu hình sai bị từ chối trước khi khởi tạo kho dữ liệu.

Chưa có tùy chọn CLI, biến môi trường hoặc nút quản trị để bật cờ. Chỉ dùng trên kho tổng hợp và proxy stage riêng đã cấu hình cổng transport kiểm quyền; không dùng cờ này để bỏ các gate nghiệm thu hoặc tự chuyển dữ liệu production. `PREVIEW_TOOLS` mặc định không đổi; mỗi instance có tập công cụ riêng dùng thống nhất cho HTTP và chính sách nhân.

## Quyền vẫn bắt buộc

Chỉ operator/chủ quản hệ thống được cấp loại công cụ; quyền dữ liệu vẫn phải đến từ đơn vị, dự án, lease và issuer hiện hành. Vai quản trị hệ thống không tự cấp quyền đọc/sửa nội dung đơn vị khác. Viewer dự án không mở được editor ghi. Tham số `actor`, `owner`, `unit_scope` hoặc `unit_id` không được thay scope do HTTP xác lập.

Agent không được thêm các công cụ editor. Credential MCP hiện có vẫn bị giới hạn bởi `authorize_call` và tập công cụ của grant; opt-in web không mở rộng danh sách đó. Google vẫn đóng ở chế độ đơn vị. Cổng ghi toàn nhân tiếp tục chặn các thao tác ghi; đọc tiến trình hợp lệ vẫn hoạt động.

`/api/me` bổ sung `workspace.capabilities.office_editor` ở chế độ đơn vị. Giá trị này chỉ mô tả opt-in của instance, không là quyền dữ liệu hoặc chứng nhận engine/scanner sẵn sàng. `van_phong.trang_thai` trả cấu hình editor thực khi opt-in; thiếu JWT vẫn báo chưa cấu hình.

Cờ kiểm soát các entrypoint công cụ mới, không phải lệnh thu hồi quyền. Không thay vòng đời source/callback/engine-auth đã có hoặc từ chối callback của operation đang chờ chỉ vì giao diện đóng. Thu hồi thành viên/quyền dự án vẫn đi qua các fence riêng. Bỏ phiên cho phép chủ phiên đọc lại trạng thái `revoked/abandoned`; không báo đó là tài liệu đã lưu hoặc cho ghi tiếp trên key bị thu hồi.

## Kiểm tra và phần còn thiếu

Ngày **18/11/2026**, có **12 ca** kiểm constructor, HTTP và nhân trên dữ liệu tạm: mặc định đóng, opt-in tạo/mở/đọc tiến trình, sai đơn vị/root/viewer, giả scope, MCP/agent, cấu hình và trạng thái, tách biệt instance, cổng ghi, thu hồi thành viên, lưu cùng intent không phát lại và bỏ phiên đang pending. Engine lệnh và scanner trong các bài này là dịch vụ tổng hợp. Phép thử lưu không gửi callback committed: tài liệu vẫn phiên bản gốc sau abandon, không tính là nghiệm thu lưu engine thật.

```sh
python3 he-dieu-hanh/thu_office_preview_http.py -v
python3 he-dieu-hanh/thu_don_vi_http.py -v
python3 he-dieu-hanh/thu_oauth_http.py -v
```

### Nghiệm thu Word qua HTTP với engine thật

Ngày **18/11/2026**, trên nguồn `dcdb3d5fd3546545a133a4eff7537dbc2978ddca`, đã đối chiếu **644 tệp Git** trước và sau thử trong môi trường riêng. Gateway dùng constructor opt-in đã đóng góp, không sửa allowlist hoặc gọi trực tiếp phương thức Office từ bộ điều phối.

Lượt `http-office-16` tạo DOCX và mở cấu hình cho hai người qua HTTPS `/api/tools` → nhân. Một trình duyệt riêng chạy SDK ONLYOFFICE thật, gõ nội dung và giữ tài liệu mở. Bộ điều phối gửi đúng một yêu cầu lưu HTTP, đọc biên nhận tiến trình đến `committed`, rồi đọc lại DOCX qua HTTP: phiên bản **1 → 2**, có dấu nội dung mới và ClamAV trả `khong-phat-hien`. Khi đã lưu, editor vẫn còn kết nối.

Sau đó gọi bỏ phiên qua cùng cổng HTTP với hai xác nhận. Gọi lại cùng ý định nhận biên nhận giống nhau; phiên bản và SHA của tài liệu đã lưu không đổi. Kết nối WebSocket gốc của SDK đóng trong **5 giây** tính từ xác nhận bỏ phiên. Đóng kết nối không xóa nội dung đã tải về trình duyệt.

Đây là launcher SDK thử riêng với cấu hình cấp qua HTTP, **chưa phải giao diện kho tệp/launcher BDSG**. Chỉ chứng minh Word và một editor đang kết nối; chưa chứng minh Excel/PowerPoint, tải hoặc nhiều worker. Lượt `http-office-15` trước đó đã mở và sửa tài liệu nhưng thiếu bước điều phối/kết quả lưu cuối, không tính đạt.

[CI đúng nguồn dcdb3d5](https://github.com/bdsgthanhhoa/open-bdsg/actions/runs/44247151633) đạt: **703 ca ứng dụng** gồm **688 đạt, 15 bỏ qua**; **52 ca vận hành**, **4 ca đóng gói**, các bước Node và MCP/TLS đạt. Không tính ca bỏ qua là tích hợp thật.

Sau thử đã dừng gateway/proxy/transport và container thử; không còn listener stage. Tệp firewall IPv4/IPv6 khớp trước thử, năm dịch vụ chính hoạt động, production vẫn R13. Bốn bản sao đầu vào xác thực của QA15/16 được xóa sau khi tiến trình kết thúc; cấu hình gốc vẫn giữ riêng ngoài Git để đối chiếu.

### Giao diện kho tệp và cửa sổ soạn thảo

Nguồn `698875e13d51bd5cac6e898b19ca9530773564a8` nối capability boolean vào `BDSGUnit`. Cửa sổ ứng dụng con chỉ có capability khi cả cha và phản hồi danh tính đều bật. Chỉ giao diện có quyền ghi mới bật tạo/mở tài liệu Office; Google theo đơn vị vẫn đóng. Legacy giữ cách mở thẻ riêng trước đó.

Trong chế độ đơn vị, editor nằm trong iframe cùng origin của kho tệp. URL chỉ chứa mã tệp; guard tiếp tục chụp danh tính và phạm vi từ cha trước I/O. Đổi đơn vị hoặc gỡ cửa sổ cha dừng ngữ cảnh cũ. Escape không tự đóng tài liệu. Sau lưu/đóng hoặc bỏ phiên có biên nhận, editor trả về kho tệp trong cửa sổ cha. Nếu phục hồi lỗi trước khi dựng editor, người dùng vẫn về kho tệp được và bản ghi phục hồi giữ nguyên, không tự gửi thao tác ghi.

Ngày **18/11/2026**, **69 ca Node liên quan** và **4 ca đóng gói** đạt. Rà soát Spec tìm lỗi kẹt phục hồi nói trên; hồi quy đã đỏ rồi đạt sau sửa. Rà soát lại Spec và Standards không còn finding. Trình duyệt kiểm **9 tình huống** ở rộng **1440/980/390 px**: tạo/lưu/đóng, bỏ phiên, đổi đơn vị, mở tệp có sẵn, mặc định đóng, chỉ đọc, điện thoại và hai dạng bản ghi phục hồi hỏng. Dùng DOM/launcher/guard/controller/CSS từ kho thật, nhưng vỏ cha, API và engine tổng hợp; không gọi đó là nghiệm thu full UI với engine thật.

Toàn **646 tệp Git** của nguồn này đã đối chiếu trong thư mục staging riêng trên máy chủ. Phép thử giao diện tổng hợp ở trên là bước trước các phép đo engine thật trong phần kế tiếp; không thay cho kết quả runtime đó. Website chính chưa dùng opt-in này.

[CI đúng nguồn giao diện 698875e](https://github.com/bdsgthanhhoa/open-bdsg/actions/runs/44250877698) đã kết thúc thành công ngày **18/11/2026**: **703 ca ứng dụng** gồm **688 đạt, 15 bỏ qua**, **52 ca vận hành**, **4 ca đóng gói** và các bước Node/MCP TLS đạt. Đây vẫn không thay phép đo giao diện với engine thật.

### Luồng cơ bản qua toàn giao diện và engine thật

Ngày **18/11/2026**, chạy toàn bộ web được đóng gói từ nguồn `698875e13d51bd5cac6e898b19ca9530773564a8`, không thay vỏ cha bằng HTML kiểm thử hoặc giả API/engine. Trình duyệt riêng đăng nhập bằng giao diện, chọn đơn vị, mở ứng dụng Văn phòng và dùng dự án tổng hợp có quyền ghi. Dùng HTTPS kiểm chứng chứng thư/hostname; ánh xạ kết nối tới loopback của máy chủ thử, không tắt kiểm TLS.

| Lượt | Tài liệu/thao tác | Bằng chứng đọc lại |
|---|---|---|
| Word17 | Tạo DOCX, gõ, bấm Lưu phiên bản khi editor còn mở | Phiên bản 1 → 2; XML trong DOCX có đúng nội dung đã gõ |
| Excel18 | Tạo XLSX, nhập công thức ở A1 và nội dung ở A2 | Phiên bản 1 → 2; công thức `SUM(10,20)`, giá trị **30**, A2 đúng nội dung |
| Slide26 | Tạo PPTX, chèn hộp văn bản ngang và gõ | Phiên bản 1 → 2; XML slide có đúng nội dung |
| Mobile23 | Giao diện rộng **390 px**, tạo DOCX và mở cửa sổ Office | Hiện giới hạn Community, nút lưu bị khóa, **0** request tải SDK; về được kho tệp, không tràn ngang |

Ba lượt desktop rộng **1440 px** đều dùng nút bỏ phiên với hai xác nhận, đọc tệp qua hộp thoại kho BDSG và kiểm ClamAV trả `khong-phat-hien`. Sau đó mở lại bằng giao diện, bấm Lưu và đóng trên tài liệu không sửa thêm; tải lại vỏ ứng dụng vẫn giữ đơn vị đã chọn và thấy tệp. Mỗi lượt không có lỗi JavaScript trang. Đã xem ảnh sau lưu và mở lại của cả ba định dạng. Không suy kết quả này ra mọi tài liệu phức tạp, tính năng Office hoặc cộng tác nhiều người.

Các lượt PowerPoint19/20/21/22/25 chưa hoàn thành thao tác chèn do bộ điều khiển kiểm thử dùng selector/menu chưa đúng; lượt24 chỉ quan sát điều khiển. Chúng không được tính là nghiệm thu đạt. Slide26 chọn đúng menu chèn hộp văn bản ngang rồi kiểm nội dung tệp sau lưu; không sửa SDK hoặc mã sản phẩm để làm phép thử đạt.

Sau thử, **646 tệp nguồn Git** và **69 tệp web** vẫn khớp dấu kiểm. So với bản dựng Windows, **65 tệp UTF-8** cần chuẩn hóa CRLF → LF để đối chiếu bản Linux; tệp nhị phân giữ nguyên. Không gọi hai bản dựng đó là giống byte trước chuẩn hóa. Đã dừng gateway/proxy/transport và container thử, không còn listener stage; firewall IPv4/IPv6 khớp trước thử, năm dịch vụ chính và R13 hoạt động. Đã xóa **20 bản sao đầu vào riêng của 10 lượt QA** sau khi các tiến trình kết thúc; cấu hình gốc giữ riêng ngoài Git.

Gate luồng cơ bản UI → nhân → HTTP → engine thật trên dữ liệu tổng hợp đã có bằng chứng cho ba định dạng. Vẫn cần kiểm thay đổi quyền/đơn vị trong editor thật, nhiều người và nhiều worker, tải, upgrade và thu hồi trong lúc reconnect, tài liệu phức tạp, Google theo đơn vị, snapshot/restore/cutover trước phát hành R14.

## Phục hồi qua HTTP và nhân — 18/11/2026

Đã bổ sung **2 bài kiểm tra** tại `thu_office_khoi_phuc_http.py`, dùng cookie đăng nhập thật, công cụ HTTP qua nhân, SQLite và cơ chế sao lưu/phục hồi công khai. Sau khi tạo và mở DOCX/XLSX/PPTX, phục hồi bản sao vào thư mục mới rồi chạy gateway khác: giữ nguyên byte tệp, phiên bản và quyền đơn vị; nguồn ký, tiến độ, lệnh lưu và callback của phiên soạn thảo cũ đều bị từ chối. Phiên mới dùng khóa mới và đọc đúng nội dung; đơn vị khác không đọc được tệp.

Trường hợp đang chờ lưu được kiểm riêng: bản phục hồi không tự gửi lại lệnh engine, retry phiên cũ bị chặn và callback cũ không tải nội dung hoặc ghi phiên bản. Phiên mới gửi lệnh đúng một lần dù client retry; callback mới mới được tải kết quả và commit phiên bản **1 → 2** với byte nội dung đã biết trước.

Hai bài đạt trên máy phát triển và trong dịch vụ Linux tách mạng, chạy bằng danh tính động không phải root, capability hiệu lực bằng **0**, `NoNewPrivs=1`, chỉ có loopback. Toàn **646 tệp nguồn** của backend `698875e13d51bd5cac6e898b19ca9530773564a8` được đối chiếu trước khi sao sang vùng thử chỉ đọc; bộ điều khiển kiểm mới có SHA-256 `2de6a057500c666d9e059c28d2e01a615be153dadf88559b1427ab379ba45ac0`. Dịch vụ thử kết thúc; firewall IPv4/IPv6 không đổi, các dịch vụ production được kiểm vẫn hoạt động.

Đây là kiểm hợp đồng phục hồi HTTP/nhân với engine HTTP và scanner tổng hợp, **không phải** phục hồi ONLYOFFICE/ClamAV thật, giao diện trình duyệt, WebSocket, nhiều worker hay RTO toàn máy chủ. Gate snapshot/restore/cutover với toàn bộ dịch vụ vẫn chưa hoàn tất; không bật R14 production từ kết quả này.

## Hai tiến trình gateway dùng chung kho — 18/11/2026

`thu_office_nhieu_tien_trinh_http.py` chạy hai tiến trình Python độc lập bằng
`spawn`, cùng kho SQLite nhưng mỗi tiến trình tự dựng ứng dụng và cổng HTTP.
Mở đồng thời trả cùng khóa editor. Tám yêu cầu lưu cùng ý định, phân đều qua hai
cổng, chỉ gửi **một** lệnh engine; retry trả được trong khi lệnh đầu vẫn chờ
phản hồi. Tệp chưa tăng phiên bản trước callback.

Hai callback giống nhau được buộc cùng tải kết quả trước khi bên nào commit.
Cả hai nhận xác nhận, nhưng tệp chỉ tăng **1 → 2**, đúng byte tài liệu tổng hợp
đã biết. Đọc tệp và tiến độ qua cả hai gateway đều thấy kết quả committed.
Retry lưu và callback sau commit không phát lệnh hay tải kết quả thêm.
Đây không phải cam kết chỉ tải một lần khi hai callback đang đồng thời xử lý.

Một ca đạt trên Windows và Linux cô lập. Phép thử Linux dùng nguồn backend
`698875e13d51bd5cac6e898b19ca9530773564a8`, đối chiếu **646 tệp** trước khi sao
sang vùng chỉ đọc; SHA-256 bộ kiểm mới là
`0930fe2bafac55c3ae7a108c1a1b99d4e597fe8e539b756868c5e1a456edb574`.
Dịch vụ thử không phải root, không có capability, chỉ mạng loopback và đã
kết thúc sạch. Firewall không đổi, sáu dịch vụ production được kiểm vẫn hoạt động.

Engine HTTP và scanner trong ca này là tổng hợp. Kết quả chưa chứng minh tải
thực tế, engine/SDK/WebSocket thật với nhiều worker, worker chết giữa lệnh,
hoặc toàn bộ điều kiện phát hành R14. Không thay cấu hình production từ ca này.

### Tiến trình chết sau khi engine nhận lệnh — 18/11/2026

Bộ kiểm hai gateway có thêm một ca thực sự kết thúc cưỡng bức tiến trình QA
gửi lệnh, sau khi engine HTTP tổng hợp đã nhận lệnh nhưng chưa trả ACK.
Client mất kết nối; gateway còn lại retry cùng ý định nhận trạng thái chưa rõ
kết quả và cùng mã lệnh, giữ tệp ở phiên bản **1**, không phát lại lệnh.
Callback hợp lệ đến trễ được gateway còn lại xử lý: phiên bản **1 → 2**, đúng
byte; replay callback và retry lưu không tải hoặc phát lệnh thêm.

Cả **2 ca** trong `thu_office_nhieu_tien_trinh_http.py` đạt trên Windows và
Linux cô lập không root. SHA-256 bộ kiểm ở lượt Linux mới là
`ccbf46eac619718836c816298496f7b7faa822c986a24be7caf7878b6bacebef`;
backend vẫn là nguồn `698875e` đủ **646 tệp** đã đối chiếu. Không thay mã
sản phẩm để làm ca đạt. Lượt đầu bộ kiểm dọn sai Event của process đã chết
bị kẹt; đã sửa chính bộ kiểm và chạy lại, không tính lượt kẹt là đạt.
Kết quả này vẫn dùng engine/scanner tổng hợp, chưa thay phép nghiệm thu sự cố
với SDK/ONLYOFFICE/ClamAV thật hoặc khôi phục toàn máy chủ.
