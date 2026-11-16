# V23 — Trung tâm AI, chọn mô hình và tác vụ được tài trợ

Đang nghiệm thu ngày **17/11/2026**. Tích hợp [LiteLLM](https://github.com/BerriAI/litellm)
v1.109.1 theo giấy phép MIT cho phần OSS; `enterprise/` có điều khoản riêng,
không được bật hay sao chép vào ứng dụng này. Bản nguồn đầy đủ ở máy phát
triển ngoài Git. Commit, SHA archive và image có chữ ký ở
[`source-lock.json`](../trien-khai/litellm/source-lock.json).

## Người dùng

Trong **Giao việc**, chọn **Tự động theo công việc** hoặc mô hình được admin
khai báo. Agent tổng thấy danh mục/năng lực và có thể chọn `model_id` cho
từng chuyên môn. Nếu không đề nghị model cụ thể, chính sách ưu tiên kỹ năng,
nhóm năng lực rồi mô hình mặc định. Lựa chọn thủ công được giữ ở mọi bước.
Mô hình ngoài danh mục bị từ chối; lỗi không tự đổi nhà cung cấp hoặc retry.
Màn đội ngũ ghi mô hình đã được chọn trước lượt gọi, khác xác nhận API thành công.

Mặc định dự án tặng **5 tác vụ/người/ngày** theo giờ Việt Nam; mỗi lượt
tiếp tục dùng một suất mới. Đây là hạn mức BDSG tài trợ, chủ quản trả chi
phí provider. Một tác vụ có thể cần nhiều lượt mô hình và có thể hết trần
token/chi phí trước khi hoàn tất. Hạn mức không bảo đảm năm tác vụ thành công.
Không phải token miễn phí do LiteLLM/OpenAI/Anthropic cấp.

## Chủ quản

Trang **Trung tâm AI** thêm/sửa/gỡ mô hình, nhập API key, tên model chính
thức, năng lực, kỹ năng ưu tiên và đơn giá USD trên một triệu token input/
output. Hiện có namespace OpenAI, Anthropic, Gemini, DeepSeek, Mistral,
Groq và xAI. Không mặc định mọi model của các hãng đều hỗ trợ tool calling
hoặc dùng được với tài khoản đang có; lỗi phải được kiểm bằng cấu hình thật.

Đơn giá và năng lực do chủ quản đối chiếu tài liệu provider. Khóa mới chỉ
gửi về máy chủ, ô nhập được xóa sau submit; API quản trị chỉ trả `has_api_key`.
Để trống giữ khóa cho đúng upstream model cũ; đổi upstream cần nhập lại.
Lưu cấu hình không xác nhận quyền hoặc số dư API. Không nhập khóa vào chat.

Bật danh mục, chọn model mặc định và trần tài trợ. Các mức ban đầu do dự
án chọn ngày 17/11/2026, có thể sửa trong admin:

| Hạn mức ngày | Ban đầu |
|---|---:|
| Tác vụ/người | 5 |
| Lượt API/người | 64 |
| Lượt API/toàn hệ thống | 500 |
| Token input giữ trước/người | 500.000 |
| Token output giữ trước/người | 100.000 |
| Token output giữ trước/dự án | 131.072 |
| Token output giữ trước/toàn hệ thống | 524.288 |
| Dự phòng USD/người | 0,50 |
| Dự phòng USD/toàn hệ thống | 5,00 |

Nhận tác vụ và trừ suất cùng transaction SQLite. Mỗi request giữ trước
token/chi phí bằng `BEGIN IMMEDIATE`: số byte UTF-8 của hội thoại/công cụ
cộng dự phòng bao gói, và tối đa 8192 token output (điều chỉnh 17/11/2026 sau lượt
nghiệm thu tạo website với Claude). Đây là tính bảo thủ theo
giá chủ quản khai báo, chưa phải hóa đơn; không tự hoàn khi provider lỗi
hoặc thiếu usage. Chi phí thật còn phụ thuộc biểu phí và tài khoản provider.
Lượt API/token output đã giữ trong luồng legacy cùng ngày vẫn được cộng
vào kiểm hạn mức mới, không đặt lại ngân sách khi đổi cấu hình. Chi phí/input
token legacy chưa biết không được bịa thành giá trị đã đo.

## Vận hành

Hai tệp ngoài Git/web: `ai-models-private.json` và `litellm-config.json`,
quyền 0600 trong kho riêng. LiteLLM chỉ nhận yêu cầu server tại loopback
4000, master key không tới trình duyệt. Container có UID của tài khoản
dịch vụ, rootfs chỉ đọc, bỏ capabilities, không mount thư mục dữ liệu khác.
Tắt telemetry theo `LITELLM_TELEMETRY_DISABLED=true`; không lưu prompt,
callback/spend log, Docker log hoặc stdout/stderr production.

Admin không đổi cấu hình khi có công việc đang chạy. Alias model kèm
revision ngẫu nhiên; `systemd.path` restart proxy khi tệp config thay đổi.
BDSG kiểm `/v1/models` có đúng alias trước nhận tác vụ và trước lượt gọi;
trong lúc nạp lại thì báo chờ, không trừ suất mới. Chưa kết nối provider thật
khác việc gateway đã nạp đúng cấu hình. Không public cổng hoặc trang admin LiteLLM.

Snapshot giữ khóa writer SQLite qua cả khoảng chụp DB và sao cặp cấu hình;
lưu cấu hình AI cũng dùng khóa này. Nếu cặp đã đổi ngoài cơ chế khóa khi sao lưu
thì gói bị từ chối, không nhận là phục hồi được. Hướng dẫn dịch vụ ở
[`trien-khai/litellm`](../trien-khai/litellm/README.md).

## Giới hạn nghiệm thu

Đã có bài kiểm tổng hợp cho giới hạn đồng thời, quyền, cấu hình, định
tuyến và rollback tệp; stock image đã kiểm mock_response, khóa truy cập,
UID thường, rootfs chỉ đọc và loopback. Lỗi 503 từ provider tổng hợp chỉ
được gửi một lần, không retry. Đã thử file watcher với tạo cấu hình lần
đầu và atomic replace: dịch vụ nạp đúng alias revision mới.
UI desktop/mobile đã đạt finish review SHIP; lỗi lưu ở cạnh nút và chuyển
focus đúng form. Ngày 17/11/2026: 223 bài Python, 208 đạt và 15 bỏ qua theo
môi trường; 4 bài đóng gói đạt. Kiểm tổng hợp không thay nghiệm thu AI thật.
Ngày 17/11/2026 đã nghiệm thu Claude Sonnet 5.5 thật qua tài khoản operator:
Agent tổng giao chuyên gia frontend tạo tệp HTML bằng Python cô lập, rồi
tổng hợp kết quả. Lượt đạt dùng 4 request, 24.493 token input và 9.142 token
output do API báo. Tệp HTML 9.870 byte được giữ nguyên khi kiểm trình duyệt:
tìm kiếm, giỏ hàng, tổng tiền và đặt hàng mô phỏng đạt trên desktop/mobile;
không có lỗi JavaScript hoặc request ra ngoài. Đây là demo dữ liệu giả lập,
không phải hệ thống đơn hàng/thanh toán thật; kết quả sinh không đưa vào Git.

Đầu nối LiteLLM bỏ temperature để tương thích Claude mới, giữ trước 8.192
token output mỗi request và chờ tối đa 60 giây/request, vẫn giữ giới hạn
180 giây mỗi lượt chuyên môn. 60 bài kiểm AI/adapter/tác vụ/đội ngũ đạt sau
thay đổi; các bộ kiểm cũ ở trên thuộc mốc trước. Chưa nghiệm thu các provider
còn lại hay so sánh chất lượng/chi phí. Không có thuật toán riêng hay mã nguồn nội bộ Manus;
chỉ tham chiếu cách chọn mô hình và trải nghiệm vận hành theo yêu cầu.
