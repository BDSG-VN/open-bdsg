---
version: 1
slug: sessions-v29
primary_target: khong-gian/phien-web.js
related_targets: [khong-gian/phien-web.css]
---
# Tài khoản — phiên web, 17/11/2026
Mode: Operate. Local extension of existing iOS webOS account/settings behavior.

## Direction contract
THESIS: Người dùng nhận biết và thu hồi phiên web của chính mình mà vẫn giữ phiên đang dùng; không trình bày như quản lý thiết bị được chứng nhận.
OWN-WORLD: Hệ iOS BDSG hiện có: chữ hệ thống, nhóm trắng trên nền #f2f2f7, chữ #1c1c1e và #62626c, xanh #0067dc, bo 12–16px. Đỏ dành riêng hành động thu hồi có xác nhận; không đổi DESIGN.md cho phần mở rộng này.
STORY: Màn hình chính → Tài khoản → đọc phiên hiện tại/khác → đặt tên hoặc xác nhận đăng xuất → phản hồi đã thực hiện. Ghi rõ quyền Office/Google/SSH/token riêng vẫn độc lập.
FIRST VIEWPORT: Tiêu đề 32px và tên tài khoản trên; nút làm mới; danh sách hàng phiên với badge hiện tại, mốc thời gian thật và hành động bên phải. Mobile xếp hành động xuống hàng; giới hạn 880px desktop. Điều khiển thu hồi hàng loạt nằm sau danh sách; dialog đặt Giữ lại trước và focus vào đó.
FORM: code-led, local extension inherits established webOS settings composition; seed: none (pinned). Chủ quản: “Chuyển toàn bộ giao diện theo phong cách iOS”; yêu cầu phiên web theo SPEC.md. No new world, comp, raster, or concept tournament.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance. Compare to incumbent DESIGN.md; preserve system files; no shipping raster added.
