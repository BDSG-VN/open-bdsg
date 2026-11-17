# V29 R11 — ủy quyền MCP đầu vào, đang phát triển

Ngày 17/11/2026, tiếp [R10](V29-R10-PHE-DUYET-GHI-DON-VI.md). Đây là chặng
nền grant/credential và gọi trong tiến trình. Chưa bật HTTP MCP theo đơn
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

R11a có sáu công cụ đọc danh mục/mô-đun/dự án/tác vụ. Không wildcard
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

## R11b — nguồn theo lượt, bước đầu trong tiến trình

Ngày 17/11/2026: thêm cấp rõ `cong_viec.tao`, `cong_viec.tiep_tuc`,
`cong_viec.dung`. Có công cụ tác vụ phải có `task_profile: {"allow_ai": false}`
hoặc `true`; không mặc định cho dùng AI. Profile cơ bản chạy quy trình danh
mục hoặc AI trên ngữ cảnh dự án đã cấp. Phần mở rộng đọc/dự thảo dưới đây cần
thêm công cụ cụ thể; chưa cấp tài liệu đính kèm, Python, trình duyệt hoặc
điều phối từ token.

Nguồn grant ID/revision/issuer epoch lưu riêng theo task/run trong cùng
giao dịch tạo lượt, không lấy từ JSON client. Worker phục hồi marker riêng
của instance hiện tại, giữ danh tính thật và kiểm nguồn khi đọc công cụ,
lưu tiến trình/kết quả, giữ ngân sách và trước gửi AI. Followup cần cùng
nguồn còn hiệu lực; không cho token khác hoặc phiên web tự tiếp quản. Web
vẫn xem/dừng việc của mình; chưa có thao tác chuyển nguồn rõ ràng.

Khởi động lại không replay; token còn hiệu lực có thể yêu cầu lượt tiếp
theo rõ ràng. Khôi phục data ở kho mới từ chối nguồn epoch cũ. Giữ ngân sách
bảo thủ cho yêu cầu đã gửi; không tự hoàn phí upstream khi kết quả bị chặn.

Ngày 17/11/2026: 15 bài nguồn/worker/adapter HTTP tổng hợp đạt: tạo/followup,
profile/AI opt-in, token chỉ tạo, từ chối tiếp quản token/web, thu hồi trước
reserve và lúc provider chờ, expiry, thu hồi/cấp lại dự án, restart/restore,
dừng bằng token và bằng web sau khi token đã thu hồi.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_mcp_tac_vu_don_vi.py' -v
```

## R11b — đầu nối đọc và dự thảo giữ cùng nguồn

Profile có thể cấp `module_reads` và `module_drafts` riêng theo nền tảng/tên
công cụ, chỉ khi `allow_ai` bật. Ví dụ cấu trúc (không có chứng thư):

```json
{
  "allow_ai": true,
  "module_reads": {"bdsg_crm": ["crm.list"]},
  "module_drafts": {"bdsg_crm": ["crm.delete"]}
}
```

Đầu nối phải đã xác minh và có quyền đọc/ghi tương ứng; cấp profile không
tự tạo quyền của chủ thể. Thế hệ cấu hình được chụp trong giao dịch cấp
grant và kiểm lại khi dùng. Đổi cấu hình không tự mở rộng hoặc hồi sinh
grant cũ. Tác vụ chụp giao của công cụ được chọn với profile, không nhận
toàn bộ công cụ của đầu nối. Client chỉ gọi tạo/tiếp tục/dừng; không được
gọi trực tiếp đọc MCP, đề xuất, duyệt, đối soát hoặc cấu hình bằng token.
Các công cụ đọc/dự thảo chỉ mở bên trong worker có marker task/run do máy
chủ tạo, đi qua nhân và guard trước/sau lời gọi.

Dự thảo giữ grant ID/revision trong payload đã chốt digest; credential và
issuer epoch không đưa vào payload. Nguồn đầy đủ nằm ở bản ghi task/run.
Kiểm nguồn cùng giao dịch INSERT và claim, rồi trước mỗi gửi/sau kết quả.
Web không tự lập dự thảo thay nguồn của tác vụ token. Admin có quyền đơn
vị/dự án mới được duyệt; agent không có quyền duyệt hoặc ghi trực tiếp.
Thu hồi/hết hạn trước claim giữ dự thảo chưa gửi. Nếu đã claim mà nguồn
mất hiệu lực thì kết quả là `unknown`, phải đối soát; không tự retry hoặc
nhận là đã rút lại yêu cầu đã gửi.

Ngày 17/11/2026: 17 bài AI/MCP/dự thảo qua gateway/nhân/SQLite thật đạt với
transport tổng hợp: hai đơn vị cùng identity chạy xen kẽ, tách chứng thư,
member/admin, giao công cụ, phân biệt đọc/ghi, thu hồi trước INSERT/claim/
send và sau send/đọc, hết hạn, xoay đầu nối, snapshot restore và token mới
không hồi sinh dự thảo cũ. Không gọi endpoint nghiệp vụ thật/API trả phí.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_mcp_mo_dun_don_vi.py' -v
```

Manual Bearer chỉ là một chế độ credential, chưa là OAuth. HTTP MCP dự kiến
pin [Streamable HTTP 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports),
kiểm Origin/JSON-RPC/header và notification. Luồng client chuẩn sẽ cần
[OAuth/authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization),
metadata discovery, resource audience và PKCE; không nhận ChatGPT/Claude đã
kết nối khi mới có nền grant này. Đây là version pin, không khẳng định mới nhất.

Còn transport HTTP/client SDK, OAuth/consent UI, nghiệm thu ghép/release và
hậu kiểm. Chưa dùng kiểm backend trong tiến trình để nhận HTTP/client thật
đã hoạt động hoặc toàn R11/lộ trình hệ sinh thái đã hoàn tất.
