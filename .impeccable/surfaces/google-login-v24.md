---
version: 1
slug: google-login-v24
primary_target: khong-gian/index.html
related_targets: [khong-gian/ung-dung.js, khong-gian/dien-mao.css]
---

# Đăng nhập Google, mở rộng cục bộ ngày 17/11/2026

Mode: Operate. Chỉ mở rộng hộp đăng nhập hiện có; giữ DESIGN.md và PRODUCT.md.

THESIS: Người được mời có thể vào không gian bằng Google, hoặc dùng tài khoản
BDSG hiện có. Không tự cấp quyền chủ quản hay yêu cầu quyền Drive.

OWN-WORLD: Giữ giao diện trung tính theo Manus đã chốt: panel trắng, chữ đen,
viền và chữ phụ xám ấm. Google G là dấu nhận diện nhà cung cấp, không phải
thay hệ màu. Không thêm ảnh raster, font hay SDK theo dõi bên ngoài.

STORY: Mở đăng nhập → chọn Google → chọn tài khoản → trở về giao việc.
Chờ/lỗi/hủy có lời giải thích và thử lại. Mật khẩu vẫn dùng được.

FIRST VIEWPORT: Hộp đăng nhập có tiêu đề, lựa chọn Google và lời giải thích,
phân cách rồi tên/mật khẩu. Các điều khiển dùng được trên 1440×1000 và 390×844.
Lỗi Google ở sát lựa chọn đó, có role alert và focus; không tràn ngang.

FORM: seed none, mở rộng thế giới hiện hữu, code-led. Không có comp hoặc
quyết định đổi nhận diện. Nút và luồng thực hoạt động là tiêu chí chính.

FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md preserved, and no new shipping raster.

QA trong .impeccable/review/v24 dùng danh tính tổng hợp có nhãn rõ.
Kiểm Google thật thực hiện riêng trên production, không đồng nhất với fixture.
