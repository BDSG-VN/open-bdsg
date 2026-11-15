# V16 — Mỗi nền tảng, một trợ lý

Đối chiếu danh mục và kiểm nghiệm ngày 15/11/2026.

Danh mục BDSG hiện có **38 mục**, tương ứng 38 hồ sơ trợ lý chuyên trách.
App và Messenger dùng chung website nhưng có mục đích và hồ sơ riêng.

## Bộ não riêng là gì?

Mỗi hồ sơ trong `nen-tang/bo-nao-tro-ly.json` có danh tính trợ lý, ID bộ não,
phiên bản, nhiệm vụ, chỉ dẫn hệ thống, nguồn kiến thức, câu hỏi làm rõ nhu cầu,
quy trình hướng dẫn và câu hỏi khởi đầu riêng. Ví dụ:

- CRM: chuẩn bị trường dữ liệu và các giai đoạn chăm sóc khách hàng.
- ERP: xác định quy trình, bộ phận và dữ liệu đối soát.
- Shop: kiểm tra sản phẩm, giá/điều kiện thực tế và xác nhận của khách.
- Travel: chuẩn bị nhu cầu hành trình và điều kiện thay đổi/huỷ cần kiểm tra.
- IoT: xác định số đo, thiết bị và phạm vi tenant.
- Law: chuẩn bị câu hỏi cho chuyên gia, không kết luận pháp lý thay họ.

Kiến thức hiện gồm danh mục công khai và hướng dẫn biên soạn riêng. Đây không
phải tài liệu nội bộ lấy từ ứng dụng gốc hoặc bộ dữ liệu huấn luyện mô hình.
Chỉ dẫn được lưu để chuẩn bị kết nối AI; khi đang chạy hướng dẫn có kịch bản,
không có LLM đang thực thi các chỉ dẫn này.

Mỗi hồ sơ có `tools.read/write` rỗng và `model_state=chua-cau-hinh`. Cấu hình
không tạo tài khoản điều hành, chứng thư hoặc worker riêng trên máy chủ. Không
lấy tín dụng chủ quản để phục vụ khách hoặc tự cấp công cụ theo tên nền tảng.
38 bộ cấu hình không phải 38 mô hình đã được huấn luyện hoặc hoạt động tự chủ.

## Dùng trên giao diện

Mở **Hỗ trợ khách hàng**, tìm theo tên/lĩnh vực có hoặc không dấu rồi chọn
trợ lý. Mỗi trợ lý có đường riêng, ví dụ `/#support/tro-ly-bdsg_crm`. Khách
chọn mục đích tìm hiểu/triển khai, tài khoản hoặc mua hàng/dịch vụ trong đúng
phạm vi nền tảng đó. Trợ lý cho các bước và câu hỏi làm rõ, mở website gốc.
Nguồn và chỉ dẫn có thể xem tại trang trợ lý.

Hội thoại được giữ riêng theo ID trợ lý trong bộ nhớ trình duyệt, tối đa năm
lượt mỗi trợ lý. Đổi trợ lý không gửi kèm hội thoại cũ. Quay lại thấy các lượt
của đúng trợ lý trong cùng trang đang mở; tải lại/đăng xuất xóa bộ nhớ. Nút xóa
chỉ xóa hội thoại đang chọn. Không có lịch sử bền vững hoặc chia sẻ giữa thiết bị.

## Giao diện HTTP và phạm vi

- `GET /api/customer-agents`: 38 bản tóm tắt trợ lý và ba mục đích trong `topics`.
- `GET /api/customer-agent?id=…`: hồ sơ công khai của một trợ lý; ID lạ trả 404.
- `POST /api/customer-support`: thêm `assistant_id` để khóa nền tảng và trả
  `brain_id`, nhiệm vụ, các bước và câu hỏi làm rõ. Chọn nền tảng khác với trợ
  lý bị từ chối. Không nhận brain tùy ý, lịch sử trợ lý khác, tool hoặc khóa.
- Lời gọi cũ không có `assistant_id` vẫn dùng được ba loại hướng dẫn tổng quát.

API không lưu hội thoại hoặc nhận lịch sử; phần tách bộ nhớ hiện nằm ở giao
diện. Không tự diễn giải đây là phân vùng RAG/tenant hoặc kết nối mô hình đã
hoạt động. Giới hạn yêu cầu vẫn theo V15; không nới để thử nhiều trợ lý.

Khi có mô hình/đầu nối thật, cần thêm cấu hình riêng theo trợ lý, kho tri thức
được cấp quyền, nhận diện khách, cách ly lịch sử phía máy chủ và kiểm công cụ
qua nhân. Trạng thái SIWC chờ OpenAI duyệt không thay đổi trong V16.

## Kiểm nghiệm và phát hành

Ngày kiểm: 15/11/2026. Tái lập bằng tài khoản không phải root trên Linux:

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_ho_tro.py' -v
```

Bài HTTP kiểm đủ 38 hồ sơ, ID/nhiệm vụ riêng và phản hồi đúng nền tảng. Kiểm
từ chối gán lại nền tảng, brain hoặc lịch sử khác; giữ các kiểm quyền/hạn mức
V15. Bài đầu tiên thất bại trên mã cũ vì chỉ có ba trợ lý tổng quát, sau sửa
kiểm đủ 38 mới đạt. Kiểm UI cần chứng minh deep-link, tìm không dấu, lịch sử
tách biệt, xóa riêng, lỗi, phản hồi đến muộn, logout và desktop/mobile.

Không gọi AI trả phí hoặc tạo đơn/tài khoản thật để kiểm. Triển khai có
backup/SHA/rollback, giữ nguyên dữ liệu và sổ tay; đóng góp qua PR draft.
