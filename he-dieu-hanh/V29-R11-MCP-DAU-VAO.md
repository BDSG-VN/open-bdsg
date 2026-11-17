# V29 R11 — ủy quyền MCP đầu vào, đang phát triển

Ngày 17/11/2026, tiếp [R10](V29-R10-PHE-DUYET-GHI-DON-VI.md). Đây là chặng
nền grant/credential và gọi đọc trong tiến trình. Chưa bật HTTP MCP theo đơn
vị, OAuth, giao diện hoặc chuyển dữ liệu production; chưa hoàn tất R11.

## Danh tính và phạm vi

Người cấp ủy quyền dưới danh tính thật của chính mình trong một đơn vị, với
nhãn client, danh sách công cụ và dự án rõ ràng. Không tạo tài khoản người
giả, dùng quyền root thay chủ thể hoặc chứng nhận máy vật lý từ một nhãn.
Mỗi grant giữ membership epoch/revision, audience `/mcp`, expiry và revision
riêng. Chỉ trả credential một lần; SQLite lưu hash, metadata không có raw
credential/hash/epoch hoặc project IDs của người khác.

Grant chụp riêng thế hệ quyền của từng dự án/chia sẻ. Thu hồi rồi cấp lại
cùng vai, đổi vai, hoặc lưu trữ rồi khôi phục dự án không hồi sinh khóa cũ
hay kết quả đang chờ. Sửa nội dung hoặc đổi quyền người khác không đổi thế
hệ quyền của người đang kết nối. Schema cũ được bổ sung thế hệ trong giao
dịch; restart giữ nguyên các tham chiếu đã tạo.

Chặng nền chỉ có sáu công cụ đọc danh mục/mô-đun/dự án/tác vụ. Không wildcard
hoặc all-project ngầm định. Phạm vi `""` chỉ cho tác vụ độc lập, không phải mọi
dự án. Danh sách dự án/tác vụ được lọc và chi tiết tác vụ kiểm scope trước khi
đọc. Công cụ vẫn đi qua nhân; gọi trực tiếp `core.goi` với actor ủy quyền cũng
phải qua guard/filter. Dispatcher MCP legacy từ chối actor ủy quyền mới.

Credential hết hạn, bị thu hồi, đổi membership hoặc mất quyền dự án chặn cả
lượt mới và kết quả đến muộn. Chủ xem/thu hồi khóa của mình; admin có thể thu
hồi khóa trong đơn vị nhưng không tự xem project IDs/nội dung riêng của chủ
khác. Credential MCP không được tự cấp thêm credential. Audit giữ grant ID
để đối chiếu client, không raw credential/tham số nghiệp vụ.

Ngày 17/11/2026: hạn khóa từ 15 phút đến 24 giờ; mỗi người/đơn vị tối đa 64
khóa đang được bật/chưa hết hạn trong epoch hiện tại, 512 bản ghi lịch sử;
tối đa 100 project IDs rõ ràng trong grant. Retention/rotation quản trị còn
tiếp; đây không là chính sách refresh token OAuth đã hoàn thành.

## Khởi động lại và phục hồi

Epoch được ghi trong tệp riêng `mcp-inbound-epoch`, không thuộc ALLOWED của
data snapshot. Restart trên cùng kho giữ epoch và credential còn hiệu lực;
context trong bộ nhớ từ instance cũ không tái sử dụng. Khôi phục data vào
đích mới tạo epoch khác, giữ metadata grant/audit nhưng từ chối credential cũ.
Như vậy snapshot trước một lần thu hồi không tự hồi sinh khóa đó. Phải cấp
credential mới sau phục hồi. Không suy rộng thành kiểm toàn host/image backup;
phục hồi toàn host phải xử lý epoch/thu hồi trước khi mở traffic.

## Kiểm chứng và phần còn lại

Ngày 17/11/2026: 20 bài kiểm module qua gateway/nhân/SQLite thật đạt, dùng
dữ liệu tổng hợp. Kiểm hai đơn vị cùng identity chạy xen kẽ, project scope,
root-member, extra args/wildcard/JSON giả provenance, audience/client, expiry,
revoke/rejoin, project revoke/cấp lại và archive/restore giữa đọc, đổi vai,
restart và snapshot restore. Bài kiểm dự án riêng xác minh nâng schema cũ
giữ nội dung và tham chiếu qua restart. Không gọi
provider/endpoint nghiệp vụ thật hoặc API trả phí.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_mcp_uy_quyen_don_vi.py' -v
```

Manual Bearer chỉ là một chế độ credential, chưa là OAuth. HTTP MCP dự kiến
pin [Streamable HTTP 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports),
kiểm Origin/JSON-RPC/header và notification. Luồng client chuẩn sẽ cần
[OAuth/authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization),
metadata discovery, resource audience và PKCE; không nhận ChatGPT/Claude đã
kết nối khi mới có nền grant này. Đây là version pin, không khẳng định mới nhất.

Còn chuyển worker/task/AI/MCP đọc/draft với nguồn ủy quyền bền theo run,
transport HTTP/client SDK, OAuth/consent UI, review/CI/release và hậu kiểm.
Chỉ mở công cụ thay đổi tác vụ khi đã khóa quyền theo token ở worker/callback;
không coi profile đọc hiện tại là đích cuối của R11 hoặc toàn lộ trình.
