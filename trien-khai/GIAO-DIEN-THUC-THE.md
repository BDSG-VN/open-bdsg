# Triển khai giao diện Open BDSG cho một thực thể

Bản Thanh Hoá ngày 14/11/2026 gồm giao diện kinh doanh đa lĩnh vực và cổng HTTP/MCP
có xác thực. Chỉ tập trung Thanh Hoá. Hướng dẫn nghiệp vụ, cài gateway, giới hạn
kết nối và bảo vệ dữ liệu: [he-dieu-hanh/README.md](../he-dieu-hanh/README.md).

## Có gì và chưa có gì

- `/`: không gian kinh doanh trong `khong-gian/`, danh mục nền tảng lấy từ gateway.
- `/os/`, `/tac-nhan/`, `/web3/`: các trang giới thiệu gốc, liên kết nội bộ theo
  thực thể và dùng phông hệ thống để không phụ thuộc tài nguyên ngoài.
- `/tro-chuyen/`: giao diện chat gốc ở chế độ xem trước. Không nạp bộ mã gửi câu
  hỏi, không mở mô hình và không nhận dữ liệu khách hàng.
- IoT, LLM, Map5D và Twin: chưa có bản ứng dụng trong gói này, trả HTTP 503.
- API nghiệp vụ và `/mcp`: gateway riêng, phiên chủ quản hoặc Bearer token agent.
  Danh mục công khai; yêu cầu, thông điệp và nhật ký phải xác thực. Không đưa máy
  chủ chat demo một danh tính cố định ra Internet.
- Liên thông dữ liệu BDSG tổng, các nền tảng nghiệp vụ và cơ quan nhà nước:
  chưa cấu hình. Không có huy hiệu EMC hoặc tuyên bố kết nối Chính phủ.

## Đóng gói

Chỉ dùng Python chuẩn. Chọn thư mục đầu ra mới, nằm ngoài kho mã nguồn:

```sh
python3 trien-khai/thu_giao_dien.py
python3 trien-khai/dung_giao_dien.py \
  --cau-hinh trien-khai/thuc-the/thanhhoa.json \
  --ra /duong-dan-tuyet-doi/ban-phat-hanh-moi
```

Đây là danh sách cho phép xuất bản: không sao chép `.git`, Python phía máy chủ,
khóa, CSDL, sổ tay nội bộ hoặc cấu hình riêng vào thư mục web. Nginx chỉ trỏ vào
bản đóng gói, không trỏ vào gốc kho.

Mẫu `nginx-giao-dien.conf.mau` dành cho bản tĩnh cũ, chưa mở API. Nó có ba chỗ cần thay:
`__TEN_MIEN__`, `__IP_XEM_TRUOC__`, `__DOCROOT__`. Địa chỉ hạ tầng và bí mật thực tế
giữ ngoài kho công khai. Sau khi DNS trỏ đúng, cấp chứng chỉ cho tên miền trước
khi triển khai đăng nhập hoặc xử lý dữ liệu người dùng. Để chạy giao diện hiện tại,
thêm proxy API/MCP theo hướng dẫn gateway; mẫu tĩnh đơn lẻ không đủ.

## Đo lại trên máy phục vụ

```sh
python3 trien-khai/do_giao_dien.py \
  --goc http://127.0.0.1 --host ten-mien-da-khai.example \
  --docroot /duong-dan-tuyet-doi/ban-phat-hanh-moi
```

Phép đo so HTML và tài nguyên với tệp đã đóng gói, sau đó ghi trạng thái vào
`cong/trang-thai-linh-vuc.json` của bản triển khai. Không ghi kết quả của máy
thử vào bản trạng thái chung trong kho. Nhãn `giao-dien` chỉ chứng minh giao diện
được phục vụ, không chứng minh các công cụ nghiệp vụ, mô hình hay dữ liệu đã nối.

Nếu dùng CDN biến đổi HTML (ví dụ chèn mã thống kê), đo origin với
`--goc https://ten-mien-da-khai.example --ip-origin IP_ORIGIN --docroot ...`.
Chế độ này cần `curl`, dùng `--resolve` và vẫn kiểm chứng chứng thư theo tên miền,
không tắt TLS. Kiểm riêng giao diện trên tên miền công khai để phát hiện lỗi do CDN.

Kiểm các đường `.git`, `.env`, mã máy chủ và sổ tay trả 404; API riêng và MCP
trả 401 khi thiếu xác thực. Phép đo HTTP tại origin chưa xác nhận DNS, chứng chỉ hay truy cập trình
duyệt từ Internet; phải kiểm riêng các phần đó khi có DNS.

## Đóng góp và vận hành

Đưa mã và cấu hình nhận diện công khai lên nhánh riêng rồi gửi Pull Request.
Không đưa mật khẩu, địa chỉ hạ tầng, dữ liệu người dùng, nhật ký riêng hoặc tệp
đo của máy vận hành vào Pull Request. Giữ bản phát hành trước để có thể đổi lại
đường dẫn `current` khi cần hoàn nguyên.
