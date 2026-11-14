# Không gian kinh doanh và cổng MCP Thanh Hoá

Nâng cấp tích hợp thử nghiệm: [Xưởng công việc V6–V11](V6-V11.md).

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
API; riêng `location = /api/tools` đặt 64k cho ngữ cảnh dự án Unicode, các
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

Đóng gói web theo danh sách cho phép, giữ source và dữ liệu ngoài docroot.
Chạy dưới tài khoản dịch vụ không đăng nhập, filesystem chỉ đọc trừ thư mục
dữ liệu, giới hạn tài nguyên và không cấp sudo. Giữ bản phát hành trước;
kiểm cấu hình proxy, sức khoẻ loopback và phiên mới trước khi chuyển symlink.
Quay lại bằng symlink cũ và cấu hình proxy trước, dừng gateway mới nếu cần;
không xoá dữ liệu vận hành khi quay lại giao diện. Sao lưu dữ liệu bằng SQLite
backup API hoặc dừng dịch vụ, không chỉ chép tệp db lúc WAL đang ghi.
