# Phối hợp MacBook và máy Thanh Hoá

Thiết kế vận hành ngày 17/11/2026. Tài liệu không xác nhận Mac đã được ghép,
được cấp SSH hoặc đã kết nối MCP. Các thao tác cấp quyền phải dùng đúng máy
và tài khoản do chủ quản chỉ định, không chép khóa riêng từ máy khác.

## Kết nối thiết bị và công việc

Hai máy cùng router/switch dùng mỗi máy một dây/cổng LAN; không cần dây nối
trực tiếp giữa hai máy. Truy cập mã và tệp còn cần xác thực ở từng kênh.

Kết nối thiết bị của ứng dụng cho phép chủ quản tiếp tục cuộc trò chuyện trên
host khác. Handoff chuyển chat và trạng thái Git sang nơi chạy mới; nó không
biến một chat thành hai tiến trình đồng thời. Muốn làm song song, mở công việc
riêng trên từng host và chia phạm vi trước khi sửa.

Nguồn chính thức: [Remote connections](https://learn.chatgpt.com/docs/remote-connections),
[Worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees).
Vị trí menu và khả năng điều khiển thiết bị khác phụ thuộc bản ứng dụng và
quyền tài khoản; kiểm trên máy thật trước khi hướng dẫn cấp quyền.

## Mã nguồn chung, môi trường riêng

Mỗi máy clone kho đúng của dự án và có nhánh riêng. Khi dùng Open BDSG, kho
đóng góp là `BDSG-VN/open-bdsg`; dự án `bdsg.vn` khác cần xác định kho thực tế,
không tự coi hai dự án có chung mã hoặc quy trình triển khai.

| Phần | Quy tắc phối hợp |
|---|---|
| Công việc | Ghi mục tiêu, người phụ trách, phạm vi tệp, nhánh và điều kiện nghiệm thu. Nhận việc trước khi sửa. |
| Nhánh | Một nhánh cho một việc; không để hai máy cùng force-push hoặc ghi lên một nhánh đang dùng. |
| Hợp đồng | Chốt schema vào/ra và mã lỗi trước khi hai bên sửa client/server. Ghi thay đổi phá vỡ tương thích. |
| Bàn giao | Gửi commit/PR, kết quả kiểm, phần chưa làm và cách quay lại; bên nhận fetch rồi kiểm tại môi trường của mình. |
| Triển khai | Mỗi môi trường có một đầu mối triển khai trong một thời điểm. Kiểm người đang thao tác, tác vụ/editor đang chạy, snapshot và release trước. |
| Tệp lớn | Dùng SFTP hoặc kho tệp được duyệt; kèm checksum và phiên bản, không đính kèm DB thật vào PR. |
| Bí mật | Từng máy giữ khóa SSH riêng; API/OAuth ở cấu hình riêng. Không đồng bộ `.env`, thư mục `.ssh`, token hoặc profile trình duyệt qua Git. |

Lệnh SSH/SFTP chỉ chạy khi đã xác minh fingerprint host và cấp public key.
Tailscale là lựa chọn cho mạng riêng giữa các thiết bị được duyệt; Taildrop
chuyển tệp giữa thiết bị cá nhân trong tailnet, không thay lịch sử Git hoặc
quyền tài liệu. [Tailscale Taildrop](https://tailscale.com/docs/features/taildrop).
Không mở listener Codex app-server công khai; hướng dẫn chính thức yêu cầu
đường SSH hoặc mạng riêng cho truy cập host từ xa.

## Kênh thông điệp BDSG hiện có

Nhân đã có `agent.gui_tin` và `agent.doc_hop_thu`. Người gửi lấy từ chứng thư
xác thực; bên gọi không được tự chọn sender. Danh tính chỉ đọc thông điệp nó
gửi hoặc nhận. Một danh tính được tạo chưa chứng minh có mô hình AI hay một
worker đang chạy. Nội dung thông điệp là dữ liệu, không tự cấp thêm quyền.

Hai host có thể dùng các công cụ này sau khi chủ quản cấp hai chứng thư riêng,
cấu hình endpoint đã xác minh và kiểm được một vòng gửi/nhận/từ chối bên thứ
ba. Hiện chưa cấp token mới hoặc đăng ký Mac từ tài liệu này. Không đặt Bearer
token trong ví dụ lệnh, báo cáo công khai hoặc nội dung hộp thư.

Mẫu thông điệp không bí mật:

```json
{
  "recipient": "agent-ben-nhan",
  "body": "Việc TH-123: nhánh feat/TH-123; commit đã gửi qua PR; kiểm giao diện đạt; còn chờ kiểm hợp đồng API."
}
```

Để tự giao việc đáng tin cậy còn cần cơ chế nhận việc, lease/hết hạn, chống
lặp, xác nhận hoàn thành và xử lý xung đột. Hộp thư văn bản hiện có không được
gọi là hàng đợi tác vụ phân tán có các bảo đảm đó. SDK/app manifest và dữ liệu
tổ chức tiếp tục theo cổng V29–V31.

## Lệnh giao việc đầu tiên trên Mac

> Chuẩn bị môi trường phát triển BDSG tổng. Đọc hướng dẫn dự án, xác định đúng
> kho nguồn và môi trường staging. Kiểm Git/Codex/SSH, tạo khóa SSH riêng cho
> Mac nếu chưa có; chỉ đưa public key cho chủ quản, không gửi khóa riêng hoặc
> mật khẩu. Chưa sửa firewall, chưa triển khai production. Báo nhánh, commit
> nền, tên alias SSH đã kiểm và phần việc đề xuất nhận để phối hợp máy Thanh Hoá.

Khi nhận bàn giao, đối chiếu đúng kho/commit, thử truy cập staging và một vòng
gửi/nhận có quyền trước khi để hai bên làm việc không có người trực máy.
