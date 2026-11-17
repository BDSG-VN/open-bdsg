# V29 R5 — nền hạn mức AI theo đơn vị

Ngày 17/11/2026. Tiếp nối [V29 R4](V29-R4-YEU-CAU-OFFICE.md).
Đây là nền backend để tiếp tục cấu hình AI theo đơn vị; chưa mở gọi AI theo
đơn vị trên website hoặc cấp khóa nhà cung cấp cho đơn vị mới.

## Hai lớp hạn mức

`NganSachAI` nhận registry đơn vị rõ ràng để kiểm tư cách hiện hành. Suất tác
vụ, lượt gọi và token/chi phí giữ trước thuộc danh tính và đơn vị làm việc.
Cùng một người có hạn mức riêng ở mỗi đơn vị. Các trần `calls_global`,
`output_tokens_global`, `usd_global` trong chính sách đơn vị áp dụng cho tổng
của đơn vị đó. Trần tài nguyên host là chính sách vận hành riêng, không trả
thống kê sử dụng của đơn vị khác trong trạng thái người dùng.

Giữ suất tác vụ cùng giao dịch admission. Trước giữ ngân sách gọi mô hình,
đối chiếu tác vụ đã lưu, chủ sở hữu, đơn vị, lượt chạy và dự án thực tế;
kiểm quyền dự án trong cùng giao dịch ghi. Có quyền trên dự án chia sẻ
không cho phép dùng tác vụ hoặc suất đã giữ ở đơn vị khác.

Các bảng legacy giữ nguyên. Metadata đơn vị của suất tác vụ và reservation
nằm trong SQLite nên đi cùng snapshot. Không tự phân loại lịch sử cũ cho
đơn vị mới. Lượt/token cũ được tính vào bảo vệ tài nguyên host theo số đo
hiện có; dữ liệu legacy không có giá USD thì không thể suy thành chi phí
USD chính xác. Sổ giữ trước vẫn chưa là hóa đơn nhà cung cấp.

## Cổng công cụ

Chế độ HTTP preview tiếp tục từ chối công cụ chưa hỗ trợ đơn vị. Nhân cũng
chỉ cấp tập công cụ đã chuyển và danh mục nền tảng công khai cần cho quy
trình có kịch bản. Nhờ vậy lời gọi nội bộ bằng danh tính scoped không thể
đọc cấu hình AI, ngân sách hoặc đầu nối legacy qua nhân.

Mặc định production vẫn giữ không gian hiện có. Không bật tenant, chạy
migration dữ liệu thật, đổi cấu hình proxy hoặc gọi API trả phí ở bản này.
Các đường AI theo đơn vị vẫn đóng đến khi hoàn tất cấu hình, chứng thư,
worker, ngân sách và sao lưu/phục hồi như một luồng thống nhất.

## Kiểm tra và bước tiếp

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_ngan_sach_ai_don_vi.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_don_vi_http.py' -v
```

Kiểm bằng SQLite và nội dung tổng hợp qua giao diện công khai, không gọi nhà
cung cấp. Tài liệu [đối chiếu LiteLLM](../docs/nghien-cuu/V29-AI-DON-VI-LITELLM.md)
phân biệt khả năng proxy hiện tại với phương án cấu hình theo đơn vị. Khóa
master loopback dùng chung chưa phải cơ chế khóa riêng được proxy cưỡng chế.
