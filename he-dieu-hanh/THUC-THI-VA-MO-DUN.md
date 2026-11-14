# Không gian thực thi Thanh Hoá — thử nghiệm 14/11/2026

## Thiết kế và phạm vi

Trang giao việc nhận mục tiêu, mô-đun được chọn và một trong ba quy trình.
Công việc được lưu trong SQLite riêng, chạy bởi tối đa hai worker, hàng đợi tối
đa 16 tác vụ. Mỗi danh tính có tối đa 100 tác vụ và mỗi tác vụ tối đa 10 lượt.
Người dùng xem tiến trình thật, bổ sung ngữ cảnh, dừng giữa các bước và tải báo
cáo Markdown. Khởi động lại đánh dấu công việc đang chạy là gián đoạn; không
tự chạy lại công cụ. Tác vụ đã hoàn tất và báo cáo được giữ nguyên.

Mọi công cụ nghiệp vụ vẫn đi qua nhân Open BDSG. Agent mô hình chỉ được cấp
bốn công cụ đọc danh mục, đầu nối, mô-đun và yêu cầu kinh doanh trong phạm vi
danh tính. Không có công cụ shell hoặc trình duyệt từ xa; không tự ghi CRM,
gửi email hay chạy mã do mô hình sinh. Công cụ MCP đọc bên ngoài có thể được
chủ quản gọi rõ ràng từ trang mô-đun khi đã khai báo và cấp quyền. Adapter
hiện chưa cho mô hình tự gọi các công cụ bên ngoài này.

## Cấu hình OpenAI, Claude hoặc BDSG

Chủ quản đăng nhập website, chọn **Cấu hình mô hình AI**, chọn nhà cung cấp,
nhập đúng tên mô hình và khóa API. Lưu cấu hình không tự kiểm chứng quyền hay
hạn mức của khóa bằng một lời gọi tính phí. Tác vụ đầu tiên sử dụng cấu hình
đó mới gọi API; lỗi được báo rõ, không đổi nhà cung cấp hoặc giả kết quả.
Khóa không được trả lại giao diện và biểu mẫu xóa khóa khi đóng.

Tệp `model-private.json` nằm trong thư mục dữ liệu riêng, quyền 0600. Chỉ
chủ quản được sửa qua công cụ `cau_hinh.mo_hinh`; nhật ký chỉ lưu metadata,
không lưu khóa. Ngữ cảnh và kết quả công cụ đọc được gửi tới nhà cung cấp do
chủ quản chọn. Cấu hình mới áp dụng cho lượt chạy mới, không thay chứng thư
của lượt đang chạy. Sao lưu thư mục dữ liệu phải được bảo vệ như bí mật.

Người vận hành cũng có thể đặt biến môi trường, thay vì nhập trên giao diện:

```text
BDSG_MODEL_PROVIDER=openai
OPENAI_MODEL=<ten-mo-hinh-duoc-cap>
OPENAI_API_KEY=<khoa-rieng>
```

Hoặc `BDSG_MODEL_PROVIDER=anthropic`, `ANTHROPIC_MODEL`, `ANTHROPIC_API_KEY`.
Với BDSG: `BDSG_MODEL_PROVIDER=bdsg`, `BDSG_MODEL_BASE_URL`,
`BDSG_MODEL_NAME`, `BDSG_MODEL_API_KEY`. Endpoint công khai được BDSG giới
thiệu là `https://llm.bdsg.vn/v1`; vẫn cần khóa được cấp hợp lệ.
Cấu hình lưu từ giao diện được ưu tiên khi khởi động lại. Không dùng phiên
đăng nhập Codex/ChatGPT làm khóa API.

Không cấu hình → quy trình có kịch bản, đối sánh danh mục và xuất báo cáo;
giao diện ghi rõ chưa có mô hình AI. Cấu hình thiếu hoặc sai → báo lỗi;
không âm thầm chuyển về quy trình. Không cài trọng số hoặc tự tải mô hình.

OpenAI dùng Chat Completions tại endpoint cố định; Claude dùng Messages với
`tool_use`/`tool_result`. Giới hạn tám lượt, bốn lời gọi công cụ/lượt, phản hồi
tối đa 1 MiB và thời gian mỗi yêu cầu 30 giây. Mô hình phải hỗ trợ giao thức
và công cụ tương ứng. Không khẳng định tương thích mọi model trong tài khoản.

Tài liệu đối chiếu:
- [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat)
- [Claude tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)

## Mô-đun

Danh mục 38 mục được dùng chung cho cổng ứng dụng và chọn công cụ cho tác vụ.
Mô-đun web mở ứng dụng gốc, không tạo SSO. Mô-đun MCP hiển thị trạng thái
khai báo và danh sách công cụ đọc/ghi từ cấu hình riêng đã được chủ quản duyệt.
Khách chưa đăng nhập không nhận metadata công cụ kết nối riêng.
Không coi URL web là endpoint MCP, không tự cấp quyền khi chọn mô-đun.

## Kiểm tra

```sh
python3 he-dieu-hanh/thu_cong_viec.py -v
python3 he-dieu-hanh/thu_mo_hinh_bdsg.py -v
python3 he-dieu-hanh/thu_may_chu.py -v
python3 trien-khai/thu_giao_dien.py -v
```

Các test dùng dữ liệu tạm và mô phỏng nhà cung cấp, không khóa thật, không
gọi API tính phí hoặc dữ liệu khách hàng. Kiểm nghiệm nhà cung cấp thật cần
khóa/mô hình hợp lệ. Đây là nền tảng thử nghiệm thực thi có giới hạn; chưa
tương đương toàn bộ máy tính ảo, trình duyệt và sản phẩm của Manus.
