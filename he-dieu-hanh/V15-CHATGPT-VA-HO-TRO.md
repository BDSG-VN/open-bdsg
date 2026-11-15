# V15 — ChatGPT và hỗ trợ khách hàng

Ngày nghiên cứu: 15/11/2026. Không gian Thanh Hoá bổ sung **Cài đặt ChatGPT**
cho chủ quản và **Hỗ trợ khách hàng** công khai với ba trợ lý hướng dẫn.

## Kết quả nghiên cứu OpenAI

Sign in with ChatGPT hiện có khả năng dùng hạn mức gói cho yêu cầu AI đủ điều
kiện. Tài liệu cho ứng dụng nguồn mở/chạy cục bộ khác với website được vận
hành từ xa phục vụ khách hàng: website thương mại/hosted cần OpenAI chấp thuận.
Open BDSG là nguồn mở nhưng bản chạy `thanhhoa.bdsg.vn` vẫn là dịch vụ hosted.
Đăng nhập không tự cho quyền tạo tài khoản ở nền tảng hoặc xác nhận mua hàng.

Nguồn chính thức:

- [SIWC tổng quan](https://developers.openai.com/siwc)
- [Phạm vi dùng gói cho OSS](https://developers.openai.com/siwc/token-sharing-open-source)
- [Yêu cầu Client ID](https://developers.openai.com/siwc/request-client-id)
- [Mô hình và suy luận](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Giới hạn preview](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [Tích hợp thương mại](https://learn.chatgpt.com/commerce/guides/integrate-sign-in-with-chatgpt)

Dùng gói qua SIWC vẫn gọi dịch vụ OpenAI bằng OAuth; không cần khóa API kiểu
thông thường cho quyền đó, nhưng không phải mô hình chạy offline. Route được
tài liệu chỉ định là Responses công khai, không phải endpoint backend ChatGPT.
Không trích cookie, token Codex hay thông tin từ phiên trình duyệt làm khóa.

## Trạng thái đăng ký của bản Thanh Hoá

Theo yêu cầu riêng của chủ quản, đã gửi biểu mẫu chính thức cho BDSG và đã
quan sát trang OpenAI xác nhận nhận thông tin. Đây là xác nhận nhận hồ sơ,
không phải phê duyệt hoặc Client ID. Thông tin người liên hệ không lưu trong
kho mã. Biên nhận vận hành chỉ ghi trạng thái/ngày trong tệp riêng
`chatgpt-registration.json` bên ngoài docroot và Git, quyền 0600.

`GET /api/chatgpt-connection` chỉ cho chủ quản xem trạng thái. Khách nhận 401,
operator nhận 403. Khi chưa được duyệt, `POST /api/chatgpt-connection/start`
trả 409, không tạo OAuth URL hoặc lưu token giả. Nút đăng nhập bị vô hiệu hóa
và có giải thích. **Bản này chưa triển khai hoặc kích hoạt OAuth/inference SIWC.**

Khi được cấp quyền, cần triển khai theo điều kiện client được cấp: callback
HTTPS cố định, state/nonce/PKCE, xác minh chữ ký ID token và issuer/audience,
quyền được cấp, lưu/refresh/revoke riêng theo tài khoản, kiểm model được phép,
đọc hết stream đến trạng thái hoàn tất và xử lý hết hạn mức. Không tự dùng
chung tín dụng chủ quản cho khách ẩn danh. Không bật phương án trả phí khác
khi người dùng chưa chọn.

## Ba trợ lý khách hàng

| Trợ lý | Việc dùng được | Điều chưa làm |
|---|---|---|
| Tư vấn nền tảng | Gợi ý tên/mục đích từ danh mục thật, mở website gốc | Không kiểm chứng tính năng/giá theo thời gian thực |
| Hỗ trợ tài khoản | Hướng dẫn đăng ký, đăng nhập, khôi phục và xác nhận | Không tạo tài khoản, không thu mật khẩu/OTP |
| Hỗ trợ mua hàng | Hướng dẫn chọn hàng, kiểm giá/điều kiện và xác nhận | Không tạo đơn, giữ hàng hoặc thanh toán |

Đây là **hướng dẫn có kịch bản**, không phải AI suy luận tự do. Khách chọn
trợ lý và nền tảng; không đoán đường `/signup` hoặc `/checkout`. Liên kết chỉ
lấy từ danh mục công khai. Không có đầu nối nghiệp vụ được cấp cho luồng này.
Mở website không phải đăng nhập dùng chung hoặc thực hiện nghiệp vụ.

`POST /api/customer-support` chỉ nhận agent/message/platform_id, tối đa 1000
ký tự. Không nhận tool, credential hoặc URL tùy ý. Cùng-origin bắt buộc,
20 yêu cầu/phút/IP và 200 yêu cầu/phút/toàn tiến trình. Bộ đếm có giới hạn và
chỉ ở bộ nhớ; không lưu IP gốc, câu hỏi hoặc lịch sử hội thoại vào máy chủ.
Proxy phải ghi đè `X-BDSG-Client-IP` bằng địa chỉ tin cậy, như hướng dẫn trong
README; gateway chỉ nghe loopback. Nếu CDN chưa chuyển IP khách qua cấu hình
real-IP tin cậy, nhiều khách có thể dùng chung hạn mức theo IP CDN. Không tin
header do khách tự khai để khắc phục; cần cấu hình proxy riêng khi mở rộng tải.
Không gọi mô hình tính phí hoặc công cụ có quyền. Giao diện giữ tối đa năm
lượt trong bộ nhớ, xóa khi mở lại hỗ trợ; chưa có lịch sử bền vững.

Trước khi tạo tài khoản/đơn thật: nền tảng cung cấp endpoint/công cụ xác thực,
chính sách quyền của khách, nguồn giá/tồn kho, idempotency và cơ chế xác nhận.
Không dùng tài khoản quản trị BDSG để thay mặt mọi khách hàng.

## Kiểm nghiệm

Các bài HTTP trong `thu_ho_tro.py` dùng máy chủ thật và kho tạm: hướng dẫn từ
danh mục, tài khoản/mua hàng không ghi nghiệp vụ, từ chối tool/token/URL lạ,
cross-origin, giới hạn tần suất, khách/operator bị chặn cài đặt, chủ quản thấy
chờ duyệt và không thể giả lập đăng nhập. Hai lát chức năng đầu được kiểm đỏ
trước khi triển khai. Không gọi AI trả phí hoặc API thương mại thật để thử.

Giao diện giữ hệ màu V13/`DESIGN.md`; phải kiểm desktop/mobile, bàn phím,
chọn từng trợ lý, phản hồi, lỗi, điều hướng và ranh giới chủ quản trước phát hành.
Triển khai phải có backup/hash/rollback, giữ dữ liệu và sổ tay.
