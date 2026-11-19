---
version: 1
slug: "khong-gian-ket-noi-js"
primary_target: "khong-gian/ket-noi.js"
related_targets: []
---

# Đầu nối doanh nghiệp và quyền MCP theo tác vụ — 17/11/2026

Mode: Operate. Mở rộng cục bộ trang Kết nối hiện có và checkbox cấp quyền trong
Giao việc, giữ thế giới iOS. Không đổi PRODUCT.md, DESIGN.md hoặc first surface.

THESIS: Quản trị biết đang cấu hình đầu nối cho đơn vị nào, ai được đọc công cụ
và kiểm được trạng thái thật; thành viên chỉ thấy quyền đã cấp, không thấy khóa.

OWN-WORLD: Canonical DESIGN.md/PRODUCT.md, quyết định ngày 17/11/2026:
“Chuyển toàn bộ giao diện theo phong cách iOS”. Giữ chữ hệ thống, bề mặt trắng,
nhóm bo góc, hành động xanh, Home/Dock và bố cục form/list hiện có. Nhãn/body
trong phần sửa tối thiểu14px, input16px, control44px. Không ảnh/tài sản mới.

STORY: Chọn đơn vị → Kết nối → admin lưu endpoint/token/allowlist và vai đọc →
kiểm MCP → xem trạng thái; ngắt cần xác nhận. Token xóa khỏi form sau gửi,
không hiện lại. Member có view đọc metadata và đường sang giao việc; không có
form/quyền probe/disconnect. Owner là member cũng không được cấu hình.
Giao việc: chọn mô-đun đã cấp → tick đồng ý đọc riêng cho tác vụ, mặc định tắt.
Ghi/Python/Vietnam/delegation chưa chuyển không được hiện như đã hoạt động.

FIRST VIEWPORT: Desktop1440 giữ hai cột form/list; mobile390 một cột cuộn trong
app. Tên đơn vị đầy đủ đã ở selector ngoài iframe. Trong app nêu rõ cấu hình
thuộc đơn vị đang chọn, quyền admin/member và kiểm MCP khác nghiệp vụ thành công.
Empty/loading/error/retry, role change/revoke và tên endpoint/tool dài đọc được.

SIGNATURE: Chuyển đơn vị đóng iframe và xóa form/token/cache; async cũ không
ghi feedback hoặc đổi trạng thái của phạm vi mới. Mỗi mutation có operation id,
epoch và scope check; action/probe đang chạy không làm mất kiểm soát trạng thái.
Lưu không gọi mạng; probe không tự cấp tool; grant mới không mở rộng tác vụ cũ.

FORM: code-led; seed:none (local extension, exempt under new-work.md §3:
“Inherit its world and composition” / “Never run the script for a local extension
or a precisely specified narrow request”). Không nhận là có pin riêng của chủ
quản cho bố cục first surface. Baseline thực từ mã R8, HTTPS loopback và root
tổng hợp: outputs/BDSG-V29-R9/bdsg-v29r9-baseline/desktop.png và mobile.png.

FINISH: Browser synthetic actual gateway desktop/mobile admin/member/rootmember,
save/reuse/probe/failure/retry/disconnect/cancel, A/B và late result/secret clear,
grant checkbox disabled/enabled, task MCP khi backend sẵn sàng. Detector một
lần, finish reviewer fresh; preserve DESIGN/PRODUCT. Không thao tác FBG Chrome.
