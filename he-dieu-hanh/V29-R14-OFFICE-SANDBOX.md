# R14 — cổng soạn thảo đơn vị thử nghiệm

Cập nhật **18/11/2026**. Có opt-in backend qua nhân/HTTP và giao diện đơn vị theo capability; chưa nghiệm thu trọn giao diện với engine thật hoặc bật production. Các bằng chứng transport trước đó ở [nghiên cứu kết nối Office](NGHIEN-CUU-THU-HOI-KET-NOI-OFFICE.md) không thay nghiệm thu luồng giao diện với cờ mới.

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

Toàn **646 tệp Git** của nguồn này đã đối chiếu trong thư mục staging riêng trên máy chủ; chưa bật runtime mới. Cần chạy tiếp trọn UI → nhân → HTTP → engine thật từ nguồn đó, gồm vỏ nhiều cửa sổ và kiểm quyền sau thay đổi. Còn các gate upgrade, thu hồi trong lúc reconnect, tải/nhiều worker, binary/tài liệu khác, snapshot/restore/cutover. Website chính chưa dùng opt-in này.

[CI đúng nguồn giao diện 698875e](https://github.com/bdsgthanhhoa/open-bdsg/actions/runs/44250877698) đã kết thúc thành công ngày **18/11/2026**: **703 ca ứng dụng** gồm **688 đạt, 15 bỏ qua**, **52 ca vận hành**, **4 ca đóng gói** và các bước Node/MCP TLS đạt. Đây vẫn không thay phép đo giao diện với engine thật.
