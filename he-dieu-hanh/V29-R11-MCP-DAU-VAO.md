# V29 R11 — ủy quyền MCP đầu vào, đang phát triển

Ngày 17/11/2026, tiếp [R10](V29-R10-PHE-DUYET-GHI-DON-VI.md). Đây là chặng
nền grant/credential, worker và HTTP MCP trong chế độ đơn vị thử nghiệm.
OAuth có nền backend và HTTP token/API đang kiểm, chưa có luồng authorize/consent/giao diện quản lý
hoàn chỉnh hoặc chuyển dữ liệu production; chưa hoàn tất R11 và chưa triển
khai thay đổi này lên website.

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
Phản hồi được tuần tự hóa trước giao dịch chốt kết quả; trong giao dịch
kiểm lại nguồn, quyền dự án/thành viên, hủy lượt, người duyệt và đầu nối.
Mất quyền trong khoảng sau guard mạng cuối không lưu nội dung upstream.
Web không tự lập dự thảo thay nguồn của tác vụ token. Admin có quyền đơn
vị/dự án mới được duyệt; agent không có quyền duyệt hoặc ghi trực tiếp.
Thu hồi/hết hạn trước claim giữ dự thảo chưa gửi. Nếu đã claim mà nguồn
mất hiệu lực thì kết quả là `unknown`, phải đối soát; không tự retry hoặc
nhận là đã rút lại yêu cầu đã gửi.

Ngày 17/11/2026: 20 bài AI/MCP/dự thảo qua gateway/nhân/SQLite thật đạt với
transport tổng hợp: hai đơn vị cùng identity chạy xen kẽ, tách chứng thư,
member/admin, giao công cụ, phân biệt đọc/ghi, thu hồi trước INSERT/claim/
send và sau send/đọc, revoke/expiry/đổi đầu nối sau guard cuối trước commit,
hết hạn, xoay đầu nối, snapshot restore và token mới
không hồi sinh dự thảo cũ. Không gọi endpoint nghiệp vụ thật/API trả phí.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_mcp_mo_dun_don_vi.py' -v
```

## R11c — HTTP và client SDK, bước đầu chưa OAuth

Ngày 17/11/2026: `/mcp` trong chế độ đơn vị thử nghiệm xác thực mới ở mỗi
yêu cầu bằng manual bearer của module grant. Không nhận cookie/token legacy,
query credential hoặc chọn scope từ `X-BDSG-Unit`. Không cấp hoặc giữ quyền
bằng Session-ID; không có state bắt tay chứa actor. Không cung cấp SSE GET,
nhận GET/DELETE/OPTIONS/HEAD/PUT/PATCH với 405 sau kiểm nguồn/xác thực.

POST JSON kiểm Origin nếu có, header trùng, Content-Type, Accept/quality,
Content-Length, version, giới hạn 64 KiB, JSON trùng khóa/không hữu hạn và
JSON-RPC envelope/ID/tham số. Phân biệt lỗi transport, lỗi giao thức và công
cụ `isError`. Notification hợp lệ trả 202 với body rỗng; notification không
thực thi công cụ. Cancellation RPC là gợi ý, dừng tác vụ nghiệp vụ cần công
cụ đã cấp. Không mở CORS hoặc metadata OAuth giả.

Version ghim [Streamable HTTP 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports),
không khẳng định mới nhất. Thiếu header mặc định 2025-03-26 theo fallback
transport; initialize phản hồi version 2025-06-18 và capabilities tools.
Tham chiếu [lifecycle/version negotiation](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle).

Ngày 17/11/2026: 11 bài wire HTTP đạt và hai bài [Python SDK 2.3.0](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0)
đạt trên socket thật: initialize, list/call, tạo/chạy tác vụ, thu hồi khi
client đang kết nối nhận HTTP 401. SDK dùng `mode="legacy"` để kiểm handshake
era của version ghim, không phải thử protocol 2026 hoặc chế độ auto.
Dependency chỉ dùng kiểm nghiệm ở `requirements-mcp-test.txt`, không cần
cài SDK vào runtime gateway. CI cài đúng pin; môi trường không cài SDK bỏ
qua hai bài này, không dùng skip đó để nhận là đã thử SDK.

```sh
python3 -m pip install --only-binary=:all: -r requirements-mcp-test.txt
python3 -m unittest discover -s he-dieu-hanh -p 'thu_mcp_http_don_vi.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_mcp_client_sdk.py' -v
```

Manual Bearer chỉ là một chế độ credential, chưa là OAuth. HTTP MCP dự kiến
pin [Streamable HTTP 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports),
kiểm Origin/JSON-RPC/header và notification. Luồng client chuẩn sẽ cần
[OAuth/authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization),
metadata discovery, resource audience và PKCE; không nhận ChatGPT/Claude đã
kết nối khi mới có nền grant này. Đây là version pin, không khẳng định mới nhất.

## R11c — nền authorization code S256

Ngày 17/11/2026: backend đăng ký public client do chủ quản hệ thống duyệt,
redirect allowlist khớp tuyệt đối, resource cố định, scope theo công cụ đọc/
tác vụ đã chuyển. Yêu cầu gắn đúng phiên web/danh tính/đơn vị; đổi phiên,
account hoặc membership không được tiếp tục consent cũ. Consent giữ snapshot
quyền dự án và đầu nối; token exchange không tự nhận quyền mới cấp sau đó.

Authorization code chỉ lưu hash, dùng một lần với PKCE S256. Đổi mã và tạo
grant dùng cùng giao dịch; lỗi sau INSERT không để lại token hoặc tiêu thụ
mã nửa chừng. Replay đúng client/redirect/resource/verifier thu hồi token
đã cấp, sai verifier không được dùng để thu hồi token của người khác. Khóa
OAuth vẫn đi qua nhân/guard nguồn như manual bearer; client bị ngắt chặn cả
code đang chờ và token đã cấp. Không có refresh, confidential-client secret,
DCR công khai hoặc endpoint metadata giả trong bước này.

Ngày 17/11/2026: request chờ tối đa 600 giây, code tối đa 300 giây và không
vượt hạn request. Giới hạn 128 request còn hạn/client, 1.024 toàn máy, 10.000
bản ghi lịch sử; dọn OAuth state đã hết hơn 24 giờ. Callback giữ nguyên query
đã đăng ký, chỉ thêm code/error, state và issuer. Snapshot restore đổi epoch
chặn cả code/token và đăng ký client cũ; cần chủ quản đăng ký lại client.
Restart bình thường giữ epoch và code chưa hết hạn, không tự replay.

Ngày 17/11/2026: 23 bài backend/SQLite thật đạt, gồm PKCE, redirect/resource/
scope, bind phiên/unit, consent/deny, logout, đổi quyền dự án, code replay,
hai exchange song song, rollback, raw credential không trong snapshot/
metadata/audit, restart/restore, hạn pending, state rỗng, root token không
quản lý client/consent và worker từ token OAuth. Chưa gọi HTTP authorize/token,
chưa kiểm SDK OAuth hoặc màn hình người dùng.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_oauth_mcp_don_vi.py' -v
```

Tham chiếu [MCP authorization ghim](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization),
[PKCE RFC7636](https://www.rfc-editor.org/rfc/rfc7636),
[protected resource metadata RFC9728](https://www.rfc-editor.org/rfc/rfc9728).
Chưa dùng nền code S256 này để nhận là đã hoàn tất OAuth 2.1.

## R11c — HTTP token và API duyệt/quản lý, chưa có trang authorize

Ngày17/11/2026: thêm `POST /oauth/token`, form-urlencoded với code/verifier/
client/redirect/resource; không lấy cookie hoặc header đơn vị để đổi chủ thể.
Không nhận Authorization passthrough, query token, field/header trùng, JSON
không hữu hạn; body form tối đa8KiB, JSON API tối đa64KiB. Token response
no-store/Pragma no-cache. Chưa cấp refresh hoặc client-secret authentication.

API cookie thực gồm bind/decide dưới `/api/oauth/`, đăng ký/list/ngắt client
do chủ quản hệ thống, create/list/revoke grant dưới `/api/mcp/`. POST quản lý
cần Origin đúng, cookie thật, actor và đơn vị còn hiệu lực. BIND/consent giữ
các snapshot session/unit/role hiện có; header actor cũ bị409. Grant trả key
một lần, list không trả lại. Cổng ghi đóng vẫn cho thu hồi/ngắt/từ chối;
không cho cấp thêm hoặc đổi code. Draining chặn nhận thao tác mới.

Ngày17/11/2026: chín bài socket/cookie thật đạt: approve→form exchange→MCP,
cookie/header tài khoản khác không đổi subject, quyền client control plane,
đổi unit/actor/Origin, deny/revoke khi cổng ghi đóng, replay/clientdisable,
giới hạn/parser, header actor/unit/epoch/revision trùng bị chặn trước bind
và draining. Start request trong fixture vẫn qua backend;
chưa có GET authorize/trang consent hoặc SDK OAuth end-to-end.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_oauth_http.py' -v
```

Không quảng bá metadata hoặc resource_metadata challenge khi trang authorize
chưa có. Còn discovery, GET authorize/consent UI, trang quản lý client/grant,
SDK OAuth HTTPS end-to-end và nghiệm thu phát hành/hậu kiểm.
Manual bearer/SDK tổng hợp chưa chứng minh ChatGPT hoặc Claude đã kết nối
thật. Chưa nhận toàn R11/lộ trình hệ sinh thái đã hoàn tất.

## R11c — kiểm TLS cho token và SDK dùng token đã cấp

Ngày 17/11/2026: ba bài HTTPS cục bộ đạt. Fixture bind cổng loopback trước
khi tạo ứng dụng, nên issuer/resource giữ URL HTTPS thật từ đầu; không đổi
audience sau khi cấp quyền. CA và leaf ngẫu nhiên tồn tại trong thư mục tạm,
client chỉ tin CA này và vẫn xác minh hostname. Sai CA hoặc hostname bị chặn.

Cookie Secure đăng nhập qua TLS, bind/approve và đổi code S256 qua socket
thật; resource sai bị chặn và không tiêu thụ code. SDK chính thức dùng token
đã cấp để initialize/list/call qua TLS, chỉ thấy công cụ/dự án được cấp;
ngắt client làm lần gọi tiếp theo trả401. Logout phiên duyệt trước exchange
làm code không còn đổi được. Không gọi endpoint nghiệp vụ hoặc API tính phí.

```sh
python3 -m pip install --only-binary=:all: -r requirements-mcp-test.txt
python3 -m unittest discover -s he-dieu-hanh -p 'thu_oauth_https.py' -v
```

Start vẫn gọi backend trong fixture, token được gắn rõ cho SDK. Đây chưa là
SDK tự discovery/OAuth authorize bằng trình duyệt; các phần đó và giao diện
quản lý vẫn còn tiếp. Dependency chứng thư chỉ thuộc kiểm thử, không runtime.

## R11c — authorize và trang chấp thuận trong bản đơn vị thử

Ngày 18/11/2026: GET `/oauth/authorize` đọc query có giới hạn, chặn trùng field,
UTF8/percent không hợp lệ và ký tự điều khiển. Client/redirect/scope/S256 vẫn
qua backend; URI chưa đăng ký chỉ trả lỗi cục bộ, không redirect ra ngoài.
Yêu cầu hợp lệ chuyển303 sang `/oauth/consent`, nonce ở fragment. Trang và
asset dùng whitelist cố định trong gateway, no-store/no-referrer, CSP cùng
nguồn và frame-ancestors none. Chỉ bật ở unit preview, chưa đổi production.

Trang iOS BDSG đăng nhập thật, chọn đơn vị rồi bind yêu cầu. Người dùng chọn
công cụ/dự án/thời hạn; không chọn sẵn. Duyệt/từ chối dùng API cookie với
actor/unit epoch/revision. Đổi tài khoản hoặc membership xóa biểu mẫu, không
giữ lựa chọn cho chủ thể mới. Kiểm lại phiên trước và sau quyết định; kết quả
không rõ không tự gửi lại. Trang này chỉ cấp profile tác vụ danh mục không
AI hoặc công cụ nền tảng ngoài; giao diện profile đầy đủ còn tiếp.

Ngày 18/11/2026: 11 bài HTTP và ba bài HTTPS cục bộ đạt, fixture HTTPS đã đi
qua GET authorize thật. Kiểm Chrome headless riêng, desktop1440/mobile390:
16 nghiệm thu gồm approve đổi code thật, deny không code, mạng lỗi/thử lại,
loading/thu hồi membership, đổi tài khoản và expiry xóa biểu mẫu; 24 ảnh,
không lỗi JavaScript hoặc tràn ngang. Browser pin leaf tạm đúng fixture;
kiểm HTTPS riêng vẫn xác minh CA/hostname. Không dùng phiên Chrome người dùng.
Review tìm lỗi401 khi sai mật khẩu làm hủy yêu cầu. Đã tách đăng nhập sai
khỏi mất phiên đang duyệt; giữ nonce/form, xóa password để nhập lại. Cả hai
kích thước đều kiểm sai mật khẩu rồi đăng nhập đúng và đổi code thành công.
Hai nghiệm thu trong số trên chèn lỗi401 tại biên mạng `/api/me` để kiểm
nhánh mất phiên: biểu mẫu/nonce bị xóa và thông báo kết thúc không bị lời
nhắc mạng ghi đè. Đây là fault injection, không nhận là gateway bình thường
trả401 tại API công khai này.

Còn metadata/discovery, client SDK tự thực hiện OAuth, quản lý client/grant,
profile AI/MCP nâng cao, review/CI và phát hành/hậu kiểm. Chưa nhận toàn R11
hoặc kết nối ChatGPT/Claude thật đã hoàn tất.

## R11c — metadata và SDK tự thực hiện OAuth

Ngày18/11/2026: PRmetadata tại `/.well-known/oauth-protected-resource` và
`/.well-known/oauth-protected-resource/mcp`, ASmetadata tại
`/.well-known/oauth-authorization-server`. Origin/resource lấy cấu hình cố
định, không từ Host/Forwarded. GET/HEAD công khai, no-store; các guard query/
Origin/header/draining giữ nguyên. MCP401 quảng bá resource_metadata thật.
AS chỉ công bố code/S256/none, issuer response; không quảng bá DCR/refresh
hoặc phương thức chưa có. Metadata mô tả khả năng, không cấp quyền.

Ngày18/11/2026: 12 bài HTTP và hai bài SDK OAuth qua HTTPS cục bộ đạt. SDK2.3.0
tự discover, tạo PKCE/state, đi authorize/callback, đổi token và khởi tạo MCP,
không preset Bearer. Consent API cookie thật chọn một tool/một project;
SDK list/call chỉ đọc dự án đó. Deny có quyết định access_denied thực, không
exchange token, tạo grant hoặc gọi công cụ. Client ID được chủ quản đăng ký
trước; fixture không giả DCR. SDK bản ghim yêu cầu các scope được quảng bá,
nên client thử có trần công cụ được admin duyệt rõ, user vẫn chọn một. Không
tự nới allowlist để tương thích một client xin quá quyền.

Kiểm riêng bốn luồng SDK + Chrome1440/390: approve/deny qua trang thật đạt,
không lỗi JavaScript. SDK tự kiểm state/iss và token exchange; chỉ công cụ/
dự án đã chọn được trả. SDK tin CA tạm đúng hostname, Chrome pin leaf tạm
trong profile riêng. Không dùng tài khoản thật hoặc API trả phí.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_oauth_http.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_oauth_sdk.py' -v
```

Chưa triển khai R11 hoặc nghiệm thu client ChatGPT/Claude thật. Còn UI quản
lý client/grant, profile AI/MCP nâng cao và các cửa nghiệm thu phát hành/
snapshot/restore/hậu kiểm. Public-client profile này không là tuyên bố đã có
mọi hình thức OAuth, DCR hoặc confidential-client integration.

## R11c — quản lý quyền trong Tài khoản

Ngày18/11/2026: thêm Quyền kết nối vào Tài khoản của chế độ đơn vị thử, giữ
quản lý phiên web hiện có. Người dùng xem/cấp/thu hồi grant trong đơn vị;
quản trị đơn vị có thể thu hồi grant thành viên nhưng không nhận key hoặc
project_ids của họ. Chủ quản quản lý client OAuth ở control plane ngay cả
khi không có membership. Chỉ hai route client được bỏ header đơn vị, không
bỏ scope của bind/consent hoặc grant.

Công cụ/dự án không chọn sẵn; thời hạn rõ. Profile tác vụ mặc định không AI,
có opt-in AI và danh sách đọc/lập đề xuất từ đầu nối đã xác minh. Cấp quyền
không chạy mô hình hoặc công cụ, không cấp direct-write/approve/reconcile.
Danh sách own grant có phạm vi dự án và profile; grant của người khác chỉ
nhận metadata backend cho phép. Consent OAuth hiện vẫn profile danh mục;
giao diện profile nâng cao tại consent còn tiếp.

Key riêng chỉ hiện một lần dưới dạng che, sao chép theo thao tác rõ, không
localStorage/sessionStorage. Đóng/chuyển/ẩn cửa sổ, đổi đơn vị hoặc tài khoản
xóa key khỏi UI/closure; clipboard đã sao chép là phần riêng của thiết bị.
Phản hồi đến muộn bị loại, không tự cấp lại khi kết quả chưa rõ. Lỗi nhập
liệu/cổng ghi đóng giữ form để sửa; mất kết nối khi lưu cần làm mới kiểm tra
trước khi cấp lại. Có xác nhận trước khi thu hồi/ngắt client.

Ngày18/11/2026:20 nghiệm thu Chrome riêng ở1440/390 đạt,26 ảnh và không lỗi
JavaScript/tràn ngang. Gateway/SQLite/cookie thật qua proxy TLS fixture;
profile dùng MCP tổng hợp, không gọi API mô hình tính phí. Chèn lỗi mạng và
giữ phản hồi API thật sau khi cấp để kiểm late key; không giả tạo grant.
Kiểm clipboard thực sau nút sao chép, xóa field/list không echo, root không
unit đăng ký/ngắt client, member chỉ own và admin revoke khác có hiệu lực.
Một bài Node mới giữ ranh giới client control plane/bind/consent/grant;
đóng gói đã kiểm hai asset mới. Chưa deploy R11 hoặc nhận toàn mục tiêu xong.

## R11c — quyền AI/MCP trong chấp thuận OAuth

Ngày18/11/2026: khi người dùng chọn công cụ tác vụ, trang chấp thuận cho chọn
AI của đơn vị, đọc và lập đề xuất trên công cụ đầu nối đã xác minh. AI và
công cụ đều chưa chọn sẵn. Tắt AI hoặc bỏ tác vụ xóa lựa chọn mô-đun, không
gửi scope cũ. Chỉ cấp đọc/dự thảo, không ghi trực tiếp/duyệt/đối soát. Summary
đi qua nhân với actor/unit đã bind; tên nền tảng từ catalogue công khai.

Profile được backend chốt cùng snapshot khi quyết định, qua code/token tới
worker. Đổi account/unit/membership/expiry xóa cả DOM/options/profile. Từ
chối không cấp quyền; kết quả chưa rõ không tự gửi lại.

Ngày18/11/2026:14 bài HTTP cục bộ đạt, gồm hai bài mới: profile OAuth qua
token/worker/provider tổng hợp tạo kết quả, không gửi access token vào mô
hình; đổi revision đầu nối sau consent (kể cả xác minh lại cùng tool) chặn
exchange và không tạo grant/gọi provider. Không gọi mô hình tính phí.

SDK+Chrome1440/390: sáu luồng profile approve/deny/stale đạt, không JSerror/
overflow; toggle AI/TASK không giữ công cụ cũ, grant có đúng profile đã chọn,
thu hồi membership xóa profile và không nhận token. Kiểm cơ bản16 tình huống
consent và bốn luồng SDK cũng đạt. Bằng chứng R11c8 tách riêng; ảnh/QA R11c5
và R11c6 bị helper cũ ghi đè đã được tái tạo bằng đúng commit trong worktree
độc lập, có audit note. Helper mặc định tạo output theo thời gian, không ghi
đè báo cáo phát hành trước.

Còn review/CI và các cửa nghiệm thu R11d trước triển khai. Không nhận toàn
mục tiêu, cutover đơn vị hoặc client ChatGPT/Claude thật đã hoàn tất.
