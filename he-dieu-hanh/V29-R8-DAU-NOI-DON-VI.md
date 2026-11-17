# V29 R8 — nền đầu nối theo đơn vị

Cập nhật 17/11/2026. Phần backend thử nghiệm, tiếp nối giao diện đơn vị R7.
Chưa bật chế độ đơn vị trên dữ liệu sản xuất và chưa hoàn tất giao diện đầu nối.

`DauNoiDonVi` lưu cấu hình trong SQLite theo `(unit_id, platform_id)`, không
sửa cấu hình toàn cổng theo từng request. Chỉ quản trị đơn vị được khai báo,
kiểm và ngắt. Chủ quản hệ thống không tự có quyền nội dung. Danh mục mô-đun
chỉ nhận metadata đã lọc của đơn vị hiện hành, không có URL/chứng thư toàn cổng.

Mặc định công cụ đọc chỉ cấp cho vai `admin`. Muốn cấp cho `member`, quản trị
phải khai rõ `read_roles`. Discovery không tự cấp công cụ. Gọi đọc cần tên đã
được cấp, xuất hiện trong danh mục kiểm và đầu nối còn được xác minh. Việc đặt
một tên vào allowlist đọc là quyết định tin cậy của quản trị, không chứng minh
upstream không có tác động ghi. Chứng thư nên có quyền nhỏ nhất ở nền tảng gốc.

Mỗi lần gọi giữ snapshot cấu hình và membership; kiểm lại trước mỗi bước HTTP
và sau khi nhận kết quả. Đổi khóa/endpoint, ngắt, thay quyền hoặc thu hồi chặn
gửi tiếp và chặn kết quả cũ. Lời gọi đã gửi ra ngoài không thể bảo đảm rút lại.
Không giữ writer SQLite trong lúc chờ mạng, không tự retry nghiệp vụ.

`TruyenTaiMCP` dùng phiên bản ghim `2025-06-18`, hỗ trợ phản hồi JSON/SSE.
Resolver phải trả toàn địa chỉ công khai; kết nối socket dùng IP đã kiểm,
TLS vẫn xác minh hostname ban đầu. Không dùng proxy môi trường hoặc redirect.
Giới hạn thân phản hồi, kiểm JSON-RPC ID, phiên bản, kiểu result và session
header; không thực thi yêu cầu sampling/chỉ dẫn do server gửi. Timeout mạng
không phải cam kết thời gian DNS của hệ điều hành.

Chứng thư nằm trong SQLite riêng và snapshot được bảo vệ như dữ liệu bí mật;
không có cơ chế mã hóa riêng cho từng dòng ở bản này. Không trả chứng thư trong
metadata/nhật ký; phản hồi upstream phản chiếu đúng token cũng được che lại.
Ngắt xóa token đang hoạt động trong bản ghi hiện hành; không tự xóa lịch sử
SQLite hoặc bản sao lưu đã có. Phục hồi cần giữ database cùng membership.

## Đường đã nối và giới hạn

Các công cụ `cau_hinh.dau_noi`, `luu_dau_noi`, `kiem_tra_dau_noi`, `ngat_dau_noi`,
`nen_tang.ket_noi`, `ket_noi.doc` và danh mục mô-đun đi qua nhân/HTTP unit preview.
Metadata epoch/revision không thay xác thực. Luồng legacy giữ cấu hình cũ và
không tự đọc hoặc chuyển chứng thư legacy sang đơn vị.

Công cụ ghi, phê duyệt theo đơn vị, MCP inbound và cấp token agent theo đơn vị
chưa được mở. Tác vụ AI chưa được cấp đọc MCP đơn vị; không dùng việc cho phép
gọi đọc thủ công để tự mở quyền cho worker. Biểu tượng Kết nối vẫn chưa được
bật trong vỏ đơn vị khi giao diện chưa nghiệm thu. Chưa có endpoint/chứng thư
nghiệp vụ thật được đối soát trong phạm vi bản này.

## Kiểm tra

Ngày 17/11/2026: các bài công khai của module, giao thức và HTTP đã kiểm hai
đơn vị cùng nền tảng khác token, quyền admin/member, rotate/revoke giữa bước,
hai worker xen kẽ, JSON/SSE, IP riêng, redirect, giới hạn thân, header lỗi và
snapshot/restore. Dùng dữ liệu tổng hợp và transport giả, không gọi Internet.

Phép thử riêng trên Linux dùng HTTPS/TLS thật trong network namespace chỉ có
loopback, không có đường ra ngoài: JSON/SSE và đóng phiên đạt; sai hostname,
CA không được tin cậy, IP riêng và redirect bị chặn. Tái hiện lỗi đọc khi
`HTTPResponse` đóng socket ngay sau Content-Length; đã sửa kiểm EOF trước khi
đặt timeout. Đây là kiểm transport với endpoint tổng hợp, không xác nhận CRM
hay một nền tảng BDSG thật đã kết nối. Chưa thay cho kiểm provider thực tế.

```sh
python3 he-dieu-hanh/thu_dau_noi_don_vi.py -v
python3 he-dieu-hanh/thu_mcp_truyen_tai.py -v
python3 he-dieu-hanh/thu_don_vi_http.py -v
```

Đối chiếu [MCP Streamable HTTP 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports):
POST JSON-RPC, Accept JSON/SSE, notification 202 và session HTTP. Xem thêm
[hướng dẫn bảo mật MCP](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices)
về SSRF và phạm vi quyền. Bản này dùng Bearer được cấp riêng, chưa triển khai
discovery/OAuth authorization; không dùng token đăng nhập BDSG để chuyển tiếp.
