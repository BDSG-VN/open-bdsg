---
version: 1
slug: "khong-gian-phe-duyet-js"
primary_target: "khong-gian/phe-duyet.js"
related_targets: ["khong-gian/ket-noi.js", "khong-gian/studio.js", "khong-gian/studio.css", "khong-gian/cong-viec.js"]
---

# Phê duyệt ghi theo doanh nghiệp — 17/11/2026

Mode: Operate. Mở rộng cục bộ Kết nối và tab Phê duyệt trong Xưởng việc hiện
có, code-led. Giữ PRODUCT/DESIGN và quyết định iOS của chủ quản; không đổi
thế giới hoặc tạo một first surface mới.

THESIS: Người giao việc biết nội dung nào mới là dự thảo, ai có thể duyệt,
và yêu cầu nào phải đối soát trước khi gửi tiếp.

OWN-WORLD: Giữ form/list, chữ hệ thống, nền sáng, nhóm trắng và hành động xanh
của iOS BDSG hiện tại. Không ảnh/tài sản mới. Body/label tối thiểu14px,
input16px, nút/label tương tác44px. Kế thừa DESIGN.md, không đổi token bền.

STORY: Admin khai báo riêng tool ghi và tick đồng ý → kiểm MCP → thành viên
chọn task/mô-đun/tool hợp lệ, nhập arguments nghiệp vụ → lưu dự thảo chưa tác
động → admin có quyền dự án kiểm payload/digest rồi duyệt hoặc từ chối.
Unknown cần admin đối soát và nhập kết quả; không tự kiểm upstream hoặc retry.
Agent chỉ lập dự thảo khi opt-in, không có công cụ duyệt/đối soát/gửi ghi.

FIRST VIEWPORT: Giữ heading và form/list Xưởng việc. Desktop1440 đọc form rồi
danh sách; mobile390 một cột cuộn trong app. Theo unit chỉ hiện phê duyệt và
đường tới ứng dụng đã hỗ trợ, không quảng cáo lịch/runtime chưa chuyển.
Nêu quyền theo doanh nghiệp, hiển thị tên tool và payload trước hành động.
Member không có nút duyệt/đối soát; admin không tự có quyền mọi dự án.

SIGNATURE: Duyệt đúng bản nội dung bất biến; đổi đơn vị/role đóng iframe, xóa
form/cache và vô hiệu request cũ. Mutation có epoch/operation/scope guard,
không tự gửi lại khi mạng lỗi. Trạng thái chờ/hết hạn/hủy/thực thi/unknown/
đối soát rõ bằng chữ, không chỉ bằng màu. JSON/tool/digest dài không tràn.

FORM: seed:none (local extension, new-work.md §3 “Inherit its world and
composition” / “Never run the script for a local extension”). Không coi đây
là pin bố cục mới của chủ quản. Baseline Kết nối R9 đã kiểm, Xưởng việc R9
thực tại outputs/BDSG-V29-R10/bdsg-v29r10-baseline/desktop.png và mobile.png.

FINISH: Gateway/SQLite thật, mô hình/MCP tổng hợp; desktop/mobile cho empty,
form, member/admin/root-member, dài, loading/error/retry, propose/reject/
approve/unknown/reconcile, scope và late response. Detector một lần trên
targets đổi, finish reviewer fresh theo scope này. Không dùng FBG Chrome.
