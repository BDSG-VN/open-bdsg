# Không gian kinh doanh và cổng MCP Thanh Hoá

[V29 R6 — cấu hình, tác vụ và HTTP AI theo đơn vị thử nghiệm](V29-R6-AI-THEO-DON-VI.md).

[V29 R5 — nền hạn mức AI theo đơn vị và cổng công cụ trong nhân](V29-R5-HAN-MUC-AI-DON-VI.md).

[V29 R4 — yêu cầu tạo tệp và phiên tải Office theo đơn vị thử nghiệm](V29-R4-YEU-CAU-OFFICE.md).

[V29 R3 — HTTP/tác vụ đơn vị thử nghiệm và chống worker/callback ghi nhầm lượt](V29-R3-HTTP-VA-TAC-VU.md).

[V29 — quản lý phiên đăng nhập web và hướng tách dữ liệu theo đơn vị](V29-PHIEN-WEB.md).
[V29 R2 — backend đơn vị/dự án/tệp trên dữ liệu thử, chưa bật production](V29-R2-DON-VI-DU-AN.md).

[V28 R2 — cổng phục hồi và biên nhận ngoài máy](V28-R2-PHUC-HOI-OFFSITE.md).
[V28 — quản trị nút máy chủ và phục hồi dữ liệu](V28-VAN-HANH.md).

[V27 — hệ điều hành ứng dụng, nhiều cửa sổ và trình duyệt](V27-HE-DIEU-HANH-UNG-DUNG.md).
[Lộ trình hệ sinh thái và máy chủ đầu tiên](LO-TRINH-HE-SINH-THAI-BDSG.md).

[V26 — độ tin cậy và điều khiển đồng bộ](V26-HOAN-THIEN-VAN-HANH.md).

[V25 — đăng nhập Google công khai](V25-GOOGLE-CONG-KHAI.md).

[V24 — đăng nhập Google theo lời mời](V24-DANG-NHAP-GOOGLE.md).

[V23 — Trung tâm AI và LiteLLM](V23-TRUNG-TAM-AI.md).

[V22 — nhân sự Agent từ 36 nguồn kỹ năng quốc tế](../nhan-su/README.md).

[V21 — tích hợp ứng dụng Việt Nam và mục tiêu mã nguồn](V21-TICH-HOP-VIET-NAM.md).

Tiếp nối: [V20 — readiness, giới hạn kết nối và sao lưu–phục hồi](V20-VAN-HANH-MAY-CHU.md).

V16: [38 trợ lý nền tảng với bộ cấu hình riêng](V16-TRO-LY-NEN-TANG.md) và
[danh sách đầy đủ](DANH-SACH-TRO-LY.md). Kết nối ChatGPT đang chờ cấp quyền,
xem [V15](V15-CHATGPT-VA-HO-TRO.md).

Văn phòng bản đầu: [V17 — giao diện tệp, văn bản, quyền và phiên bản](V17-VAN-PHONG.md).
Có sửa TXT/MD/CSV; chưa có editor DOCX/XLSX/PPTX hoặc kết nối Google.
Tiếp nối: [V18 — tệp 8 MiB, truyền từng phần và tiếp tục sau gián đoạn](V18-TRUYEN-TEP.md).
Tiếp nối: [V19 — soạn thảo Office, quét virus và mã kết nối Google](V19-OFFICE-ENGINE.md).
V19 đã kiểm engine thật; Google vẫn cần cấu hình và cấp quyền tài khoản thật.

Nâng cấp tích hợp thử nghiệm: [Xưởng công việc V6–V11](V6-V11.md).
Tiếp nối ngày 15/11/2026: [V12 — phê duyệt thao tác trình duyệt](V12-PHE-DUYET-TRINH-DUYET.md).
Giao diện V13 ngày 15/11/2026 áp dụng Impeccable và tham chiếu Manus theo yêu
cầu chủ quản: nền trung tính, nút đen, tiêu đề serif tiếng Việt và ô giao việc
làm trọng tâm. Quy chuẩn tại [DESIGN.md](../DESIGN.md), ngữ cảnh sản phẩm tại
[PRODUCT.md](../PRODUCT.md). Phông Lora phục vụ cùng tên miền, kèm giấy phép OFL.

Bản thử nghiệm thực thi mới: [Tác vụ, mô-đun và cấu hình OpenAI/Claude](THUC-THI-VA-MO-DUN.md).
Cơ sở tham khảo và giới hạn phép phân tích REA: [Đối chiếu Manus](DOI-CHIEU-MANUS.md).

Bản đóng góp ngày 14/11/2026 mở rộng giao diện Open BDSG thành không gian phát
triển kinh doanh đa lĩnh vực. Danh mục có 38 mục sản phẩm, tương ứng 37 địa chỉ
web riêng biệt; App và Messenger dùng chung địa chỉ. Nguồn công khai được ghi
trong `nen-tang/danh-muc.json`. Liên kết mở ứng dụng gốc trong tab mới. Không có
đăng nhập dùng chung, sao chép dữ liệu hoặc cam kết các ứng dụng gốc hoạt động.

## Chạy và kiểm tra

Yêu cầu Python 3.11 trở lên, chỉ dùng thư viện chuẩn. Từ gốc kho:

```sh
python3 he-dieu-hanh/thu_may_chu.py -v
python3 trien-khai/thu_giao_dien.py -v
python3 trien-khai/dung_giao_dien.py --cau-hinh trien-khai/thuc-the/thanhhoa.json --ra /tmp/bdsg-web-moi
python3 he-dieu-hanh/may_chu.py init --data /duong-dan-rieng --output /tep-rieng/chu-quan.json
python3 he-dieu-hanh/may_chu.py create-agent --data /duong-dan-rieng --id agent-a --name 'Agent A' --output /tep-rieng/agent-a.json
BDSG_DATA_DIR=/duong-dan-rieng BDSG_ALLOW_WRITES=1 python3 he-dieu-hanh/may_chu.py serve
```

Chứng thư chỉ xuất một lần vào tệp do người vận hành chọn, không in ra stdout.
Thư mục này phải nằm ngoài web và Git. Người vận hành chuyển chứng thư qua
kênh riêng, giới hạn quyền đọc rồi xoá bản trung chuyển. Khi chạy bằng tài khoản
dịch vụ, toàn bộ thư mục dữ liệu phải thuộc tài khoản đó. Cần HTTPS ở reverse
proxy; cookie Secure không hoạt động qua HTTP. Cổng Python chỉ nghe loopback.

Proxy `/api/` và `/mcp` tới `http://127.0.0.1:8766`, giữ nguyên đường dẫn;
ghi đè `X-BDSG-Client-IP` bằng IP kết nối đáng tin, không nhận trực tiếp tiêu đề
do khách khai. Đặt `client_max_body_size 16k`, giới hạn tốc độ đăng nhập và gọi
API; riêng `location = /api/tools` đặt 64k cho ngữ cảnh dự án Unicode;
riêng `/api/upload` đặt 1500k cho tệp base64, các đường khác giữ 16k.
Không ghi Authorization, cookie hoặc thân yêu cầu vào nhật ký. Origin
trong `BDSG_ORIGIN` phải khớp chính xác tên miền HTTPS của giao diện.

## Nghiệp vụ thật

- Danh mục, tìm kiếm tiếng Việt không dấu, nhóm lĩnh vực, lưu ứng dụng trên trình duyệt.
- Chủ quản đăng nhập để tạo yêu cầu, quản lý bốn chặng và xem nhật ký thao tác.
- SQLite lưu yêu cầu, phiên và thông điệp riêng ngoài web. Mật khẩu dùng scrypt;
  phiên và token chỉ lưu SHA-256. Phiên hết hạn sau tám giờ.
- Mỗi agent có chứng thư riêng. Người gửi lấy từ xác thực. Hộp thư chỉ trả thông
  điệp do danh tính đó gửi hoặc nhận. Thu hồi bằng lệnh `revoke-agent --id ...`.
- Hộp thư là kênh thông điệp, không tự trả lời. Worker tác vụ riêng đã có;
  mô hình API chỉ hoạt động khi chủ quản cấu hình. Không có bảo đảm thực hiện
  nghiệp vụ liên nền tảng đúng một lần hoặc retry tự động.

## MCP và kết nối nền tảng

Endpoint `/mcp` dùng Streamable HTTP, phản hồi JSON, stateless. Hỗ trợ phiên bản
2025-06-18 và tiêu đề tương thích 2025-03-26; kết quả initialize khai 2025-06-18.
Không cung cấp SSE chủ động. Khách gửi Bearer token riêng, Content-Type JSON và
Accept `application/json, text/event-stream`. Không mở CORS. Danh tính trong
initialize hoặc arguments không thay thế danh tính đã xác thực.

Mọi công cụ đi qua nhân `nhan/`: quyền đọc/ghi cụ thể, cổng ghi, hạn mức và nhật ký.
Agent có quyền danh mục, đọc hộp thư và gửi tin; operator thêm nghiệp vụ của chính
mình. Chủ quản web quản lý yêu cầu và đầu nối; token agent không có quyền chủ quản.
Cổng ghi mặc định đóng, chỉ mở khi người vận hành đặt `BDSG_ALLOW_WRITES=1`.
Nhật ký nhân ghi tên trường/kích thước, không ghi nội dung thông điệp.

Đầu nối nền tảng mặc định là danh sách rỗng. Cấu hình riêng qua
`BDSG_CONNECTIONS=/tep-rieng/connections.json`, ví dụ cấu trúc:

```json
[{"platform_id":"bdsg_crm","url":"https://crm.bdsg.vn/DUONG_DAN_MCP_DO_BEN_QUAN_TRI_CUNG_CAP",
  "token_env":"BDSG_CRM_TOKEN","roles":["quan-tri"],
  "read_tools":["TEN_CONG_CU_DOC_DA_DUYET"],"write_tools":[]}]
```

Đây chỉ là mẫu, **không phải endpoint đã tồn tại**. URL cố định từ tệp riêng,
HTTPS trong miền con bdsg.vn, DNS công khai, không theo redirect, giới hạn phản
hồi và thời gian. Chỉ gọi công cụ được liệt kê đúng tên; không chạy chỉ dẫn từ
kết quả. Công cụ ghi phải có quyền ghi và cổng ghi mở. Bản này hỗ trợ đầu nối
Bearer, chưa triển khai OAuth/discovery, giao dịch phân tán hoặc đồng bộ tự động.
Danh mục ghi “đã khai báo” thay vì tự khẳng định kết nối thành công.

`kiem_web.py --ra /thu-muc-du-lieu/web-status.json` đo HTTP công khai một lần,
giới hạn đồng thời, kiểm chứng TLS; mốc đo thể hiện trên giao diện. HTTP 200
không chứng minh đăng nhập, dữ liệu hay MCP đã hoạt động. Không liên thông với
hệ thống chính phủ và không tự gắn nhãn EMC.

## Triển khai và quay lại

Giao diện chọn đơn vị thử nghiệm, quyền ứng dụng và các giới hạn chuyển đổi:
[V29 R7](V29-R7-GIAO-DIEN-DON-VI.md). Mã mới không tự bật chế độ đơn vị trên
dữ liệu đang vận hành.

Đóng gói web theo danh sách cho phép, giữ source và dữ liệu ngoài docroot.
Chạy dưới tài khoản dịch vụ không đăng nhập, filesystem chỉ đọc trừ thư mục
dữ liệu, giới hạn tài nguyên và không cấp sudo. Giữ bản phát hành trước;
kiểm cấu hình proxy, sức khoẻ loopback và phiên mới trước khi chuyển symlink.
Quay lại bằng symlink cũ và cấu hình proxy trước, dừng gateway mới nếu cần;
không xoá dữ liệu vận hành khi quay lại giao diện. Sao lưu dữ liệu bằng SQLite
backup API hoặc dừng dịch vụ, không chỉ chép tệp db lúc WAL đang ghi.
