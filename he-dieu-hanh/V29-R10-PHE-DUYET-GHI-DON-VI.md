# V29 R10 — phê duyệt ghi MCP theo đơn vị, đang phát triển

Ngày 17/11/2026, tiếp [R9](V29-R9-TAC-VU-MCP-DON-VI.md). Backend đầu tiên đã
có; chưa nhận R10 hoàn tất, chưa triển khai thay R9 hoặc bật tenant production.

## Hợp đồng backend

Thành viên đề xuất đúng công cụ ghi của mô-đun trong tác vụ do mình giao.
Đề xuất chia sẻ payload cần duyệt với admin đơn vị có quyền dự án; không trao
quyền xem toàn bộ tác vụ/dự án. Global owner chỉ là member không được duyệt.
Mỗi dự thảo lưu unit, owner membership epoch/revision, task/run, project,
connector revision và expiry trong payload canonical có digest. Hiệu lực
15 phút; client duyệt ID/digest chính xác, không gửi lại payload thay thế.

Connector cần allow_writes tường minh cùng danh sách write_tools được khám
phá/xác minh. Danh sách đọc/ghi phải rời nhau để không dùng đường đọc bỏ qua
phê duyệt. Discovery không tự cấp quyền. Chứng thư không vào action/prompt.

Claim awaiting→executing là cập nhật SQLite nguyên tử. Thực thi bằng danh
tính admin duyệt qua nhân, không nâng role của người đề xuất. Permit nội bộ
gắn actor, scope, revision và arguments, chỉ dùng một lần; không là trường
JSON/HTTP hoặc token cấp cho agent. Gọi ghi trực tiếp không có permit bị chặn.

Guard kiểm lại cả người đề xuất/người duyệt, quyền dự án, task/run/cancel,
expiry và cấu hình trước từng HTTP/sau kết quả. Không giữ writer SQLite trong
lúc chờ mạng. Hủy lượt cũng vô hiệu dự thảo của lượt đã hoàn thành. Thu hồi
người đề xuất rồi thêm lại không khôi phục phê duyệt cũ.

Lỗi, timeout hoặc MCP báo isError sau claim là unknown: cần đối soát nền tảng,
không tự retry ghi. Restart chuyển executing sang unknown, không replay.
Không bảo đảm exactly-once ở upstream hoặc rút lại được yêu cầu đã gửi.
Ngắt đầu nối không xóa chứng thư trong snapshot cũ.

Action ở bảng unit_actions riêng, list/get lọc unit và quyền dự án. Bảng này
cùng dấu hủy bền unit_action_cancelled_runs được đối chiếu identity/scope
khi phục hồi gateway. Dấu hủy được kiểm lại trong giao dịch tạo action để
chặn cả dự thảo đến muộn sau khi hủy lượt đã hoàn thành.

Một công cụ của một nền tảng/đơn vị đang executing hoặc unknown chặn đề xuất
mới và duyệt các dự thảo khác đã chờ. Khóa này cố ý theo công cụ, không chỉ
arguments/task: upstream chưa có hợp đồng idempotency chung, đổi tham số
không được dùng để bỏ qua đối soát. Các công cụ/đơn vị khác không bị chặn.
Admin có quyền dự án xác nhận đúng ID/digest qua hanh_dong.doi_soat, ghi kết
quả applied/not-applied cùng ghi chú kiểm chứng. Thao tác này không gọi mạng
và không tự gửi lại; đây là xác nhận do người quản trị nhập, chưa là hệ thống
tự kiểm upstream. Muốn thử lại cần đề xuất/duyệt riêng sau đối soát.

## Cổng còn lại trước khi phát hành R10

Giao diện cấu hình write_tools, dự thảo/xem/duyệt/từ chối theo vai, kiểm browser
điện thoại/máy tính và luồng agent đề xuất còn tiếp. Chưa mở browser action,
kinh doanh legacy hoặc inbound MCP theo đơn vị. Rà soát độc lập, CI Linux,
backup/restore action, snapshot/rollback và hậu kiểm chưa được coi là đạt khi
chưa có bằng chứng tương ứng. Không dùng endpoint thật hoặc API tính phí để thử.

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_hanh_dong_don_vi.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_don_vi_http.py' -v
```
