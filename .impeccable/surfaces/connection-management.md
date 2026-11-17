---
version: 1
slug: connection-management
primary_target: khong-gian/quyen-ket-noi.js
related_targets: [khong-gian/quyen-ket-noi.css, khong-gian/phien-web.js]
---
# Quyền kết nối trong Tài khoản — 18/11/2026

Mode: Operate. Phần bổ sung Tài khoản đã có mục đích rõ, không là một visual
world mới. PIN: “Chuyển toàn bộ giao diện theo phong cách iOS”, quyết định
chủ quản ngày17/11/2026 lưu trong PRODUCT.md và webos-v27.md.

THESIS: Người dùng xem/cấp/thu hồi quyền theo đơn vị, chủ quản đăng ký trần
ứng dụng OAuth ở cấp hệ thống. Hai mặt phẳng quyền không trộn lẫn.

OWN-WORLD: Giữ nhóm trắng/nền xám, chữ hệ thống/hành động xanh của Tài khoản.
Màu nguy hiểm kế thừa phien-web.css; không thêm tài sản hoặc palette mới.

STORY: Tài khoản → Quyền kết nối → xem quyền trong đơn vị hoặc registry của
chủ quản → tự chọn công cụ/dự án/thời hạn/profile → cấp khóa một lần hoặc
đăng ký client → sao chép theo thao tác rõ/đóng khóa → thu hồi khi cần.

FIRST VIEWPORT: Giữ nguyên Tài khoản/phiên web. Nút Quyền kết nối ở đầu trang
đưa tới phần mở rộng. Tab ghi rõ scope, công cụ chưa chọn sẵn; client registry
không yêu cầu chủ quản là thành viên đơn vị. Cấp khóa và đăng ký là hành động
chính xanh. Mobile một cột, nội dung theo thứ tự hành động, không tràn ngang.

FORM: code-led, phần mở rộng hẹp của account. Không seed/comp mới, không đổi
PRODUCT.md/DESIGN.md. Nguồn thế giới đã chốt: webos-v27.md và ảnh account.

SIGNATURE: Khóa một lần bị xóa khi đóng/chuyển/ẩn cửa sổ hoặc đổi context;
phản hồi đã cấp nhưng đến muộn không đem key vào đơn vị mới. Đóng form vì
kết quả chưa rõ không tự mint lại. Clipboard do người dùng sao chép tồn tại
riêng; không hứa xóa clipboard khi xóa DOM.

FINISH: Desktop1440/mobile390; registry/root không unit, validation/retry,
gate đóng, one-time/copy/hide/list/revoke, AI/read/draft opt-in không chạy
công cụ khi cấp, iframe hide, late key khi đổi unit, list error/retry,
admin revoke other/member only own. Toàn dữ liệu tổng hợp. Capture đầy đủ
tài liệu workspace từ đầu; kiểm hostOS/iframe bằng tương tác riêng, không
dùng ảnh viewport iframe bị cắt làm bằng chứng đầy đủ của biểu mẫu.
