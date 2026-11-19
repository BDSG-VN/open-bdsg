# V29 R9 — giao diện đầu nối và quyền MCP cho tác vụ

Cập nhật 17/11/2026, tiếp [nền đầu nối R8](V29-R8-DAU-NOI-DON-VI.md).
Chế độ đơn vị vẫn thử nghiệm; mã mới không tự tạo đơn vị hoặc chuyển dữ liệu thật.

## Quản trị đầu nối

Ứng dụng Kết nối dùng membership của đơn vị hiện hành. Quản trị đơn vị có thể
lưu endpoint, chứng thư và allowlist, chọn độc lập vai admin/member được đọc,
probe và ngắt. Chủ quản hệ thống chỉ là member cũng chỉ nhận view thành viên.
View này không có URL/chứng thư hoặc nút cấu hình; chỉ có metadata và công cụ
đọc được cấp. Các tính năng Việt Nam/ghi chưa chuyển không hiện ở đây.

Token được xóa khỏi form sau gửi, không lưu trong browser storage hoặc hiện
lại. Đổi endpoint hoặc kết nối lại cần token mới; backend vẫn cưỡng chế quy tắc
này khi bỏ qua kiểm giao diện. Đổi scope/role đóng iframe và reset cache; các
async giữ cả operation, epoch và token phạm vi để không vẽ dữ liệu cũ.

Lưu không gọi mạng, probe chỉ handshake/tools/list; discovery không tự cấp
tool. “MCP có phản hồi” chưa xác nhận đồng bộ hoặc một nghiệp vụ thành công.
Ngắt cần xác nhận, xóa token hiện hành; không xóa dữ liệu upstream hoặc backup.

## Giao việc đọc MCP

Chọn mô-đun rồi mở “Ngữ cảnh và công cụ” để cấp đọc riêng cho tác vụ. Checkbox
mặc định tắt, chỉ bật khi AI đơn vị và mô-đun đã chọn có quyền đọc phù hợp.
Dữ liệu đọc được có thể gửi tới provider AI đã cấu hình; không cấp công cụ ghi.

Task lưu tên tool và revision đầu nối, không token. Followup giữ tập này; sửa
config hoặc thêm quyền không mở rộng task cũ. Muốn dùng cấu hình/grant mới cần
giao tác vụ mới. Legacy vẫn yêu cầu chủ quản; không nâng global role của người
dùng đơn vị để gọi công cụ.

Luồng qua task proxy và nhân thật. Guard ngoài JSON kiểm task/run/cancel,
project, membership, AI và connector trước mỗi HTTP và sau kết quả. Thu hồi
hoặc đổi cấu hình giữa initialize và tools/call chặn gửi tiếp. Đã gửi thì không
cam kết rút lại; không retry nghiệp vụ. Lỗi quyền MCP dừng run, không coi dữ
liệu cũ là kết quả hoặc tiếp tục đưa dữ liệu đó sang mô hình.

Các khóa JSON không được khai báo ở ket_noi.doc/ghi bị từ chối bằng kiểm riêng:
schema engine hiện không đủ để dựa duy nhất vào additionalProperties. Caller
HTTP không thể cấp callback guard hoặc sửa expected revision của task qua JSON.

## Kiểm tra và giới hạn

Ngày 17/11/2026: bài task dùng MoHinhLiteLLM thật với HTTP opener tổng hợp,
nhân thật và MCP exchange tổng hợp; kiểm opt-in, hai worker/hai đơn vị, grant
member, followup không mở rộng, che token và cancel/revoke+rejoin/rotate/
disconnect/project/AI đổi trong initialize. Không gọi provider trả phí.

Browser HTTPS loopback qua gateway/SQLite thật đã lưu/probe bằng UI, kiểm
reuse/ngắt/hủy ngắt, scope A/B, thành viên/chủ quản-member, save đến muộn,
loading/lỗi/thử lại và task không opt-in/opt-in qua model→nhân→MCP. Những endpoint,
khóa, mô hình và nội dung trong phép thử đều tổng hợp, không chứng minh một
nền tảng BDSG thật đã được cấp endpoint hoặc đồng bộ nghiệp vụ.

```sh
python3 he-dieu-hanh/thu_cong_viec_mcp_don_vi.py -v
python3 he-dieu-hanh/thu_don_vi_http.py -v
node --check khong-gian/ket-noi.js
node --check khong-gian/cong-viec.js
```

Công cụ ghi/phê duyệt, MCP inbound và token agent theo đơn vị còn tiếp.
Office/Google, workflows/runtime/delegation, audit/export/retention, MFA và
migration/cutover vẫn còn trước khi bật đơn vị cho dữ liệu sản xuất. Đây là
webOS, chưa phải hoàn tất toàn bộ lộ trình hệ điều hành/ứng dụng/thiết bị.
