# R14 — cổng soạn thảo đơn vị thử nghiệm

Cập nhật **18/11/2026**. Mới có opt-in backend qua nhân/HTTP; chưa mở giao diện đơn vị hoặc bật production. Các bằng chứng transport trước đó ở [nghiên cứu kết nối Office](NGHIEN-CUU-THU-HOI-KET-NOI-OFFICE.md) không thay nghiệm thu luồng giao diện với cờ mới.

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

Cần tiếp tục nối capability vào giao diện/launcher với đúng scope và vòng đời parent, kiểm trên desktop/mobile, rồi chạy trọn UI → nhân → HTTP → engine thật từ toàn nguồn được đối chiếu. Còn các gate upgrade, thu hồi trong lúc reconnect, tải/nhiều worker, binary/tài liệu khác, snapshot/restore/cutover. Website chính chưa dùng opt-in này.
