---
name: "BDSG Thanh Hoá"
description: "Không gian vận hành trung tính theo tham chiếu Manus, giữ nhận diện BDSG."
colors:
  primary: "#1a1a19"
  primary-hover: "#333330"
  bg: "#f8f8f6"
  surface: "#fff"
  surface-subtle: "#f4f4f1"
  surface-muted: "#ededea"
  surface-hover: "#e7e7e3"
  text: "#454541"
  muted: "#6b6b66"
  line: "#e3e3df"
  focus: "#555550"
  nav-active: "#e7e7e2"
typography:
  display:
    fontFamily: '"BDSG Lora", Georgia, serif'
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: "-0.025em"
  headline:
    fontSize: "27px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI Variable Display", "Segoe UI", Helvetica, Arial, sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontSize: "13px"
    fontWeight: 600
  title:
    fontSize: "14px"
    fontWeight: 500
rounded:
  control: "8px"
  field: "10px"
  panel: "12px"
  studio: "18px"
  composer: "20px"
  template: "100px"
spacing:
  inline: "8px"
  control: "12px"
  sidebar: "16px"
  compact: "18px"
  section: "20px"
  card: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  button-subtle:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.field}"
    padding: "12px"
  navigation:
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px"
  navigation-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.primary}"
  task-template:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.template}"
    padding: "9px 13px"
  studio-card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.studio}"
    padding: "24px"
  task-composer:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.composer}"
---

# Design System: BDSG Thanh Hoá

## Overview

**Creative North Star: "Không gian giao việc trung tính"**

Hệ thống ghi nhận từ bản giao diện ngày 15/11/2026: nền trắng ngà nhạt,
panel trắng, sidebar xám ấm, chữ đen than và nút chính gần đen. Tham chiếu
Manus là quyết định về diện mạo; tên, biểu tượng và ngôn ngữ vẫn là BDSG.

Khoảng trống và chênh lệch sắc độ phân lớp nội dung. Tiêu đề giao việc dùng
serif có bộ chữ tiếng Việt riêng; nội dung vận hành và điều khiển dùng sans-serif.
Phạm vi ghi nhận là các stylesheet của `khong-gian/index.html`, với
`dien-mao.css` nạp sau cùng. Các giá trị dưới đây được đối chiếu mã ngày
15/11/2026; đây không phải số liệu đo hiệu năng hoặc tuyên bố đã rà mọi màn hình.

**Key Characteristics:**

- Nền trung tính ấm và hành động chính màu đen than.
- Bề mặt tĩnh phẳng, đường viền mảnh, góc mềm.
- Chữ serif dành cho tiêu đề giao việc; sans-serif phục vụ vận hành.
- Trạng thái bàn phím có đường bao nhìn thấy được.

## Colors

Bảng màu chủ đạo là các sắc trung tính ấm; token ở đầu tệp là giá trị chuẩn.

### Primary

- **Đen than** (`primary`): chữ chính, nút chính, nút chạy và tab đang chọn.
- **Đen than khi trỏ** (`primary-hover`): nền nút chính khi rê chuột.

### Neutral

- **Trắng ngà** (`bg`): nền ứng dụng và thanh trên.
- **Trắng panel** (`surface`): ô nhập, thẻ, nút phụ và vùng soạn mục tiêu.
- **Xám ấm nhẹ** (`surface-subtle`): sidebar, nút nhẹ, vùng mã và hàng khi trỏ.
- **Xám trung tính dịu** (`surface-muted`): lớp phụ qua biến màu đang có trong mã.
- **Xám tương tác** (`surface-hover`): điều hướng và mẫu công việc khi trỏ.
- **Chữ vận hành** (`text`), **chữ phụ** (`muted`): phân biệt nội dung với giải thích.
- **Viền mảnh** (`line`): ngăn khu vực và bao điều khiển.
- **Đường bao bàn phím** (`focus`): nhận biết điều khiển đang được chọn bằng phím.
- **Điều hướng đang chọn** (`nav-active`): nền mục đang mở trong sidebar.

**The Nền ấm, hành động than Rule.** Dùng nền `bg` và hành động `primary`
đã chốt; không đổi bảng màu chính thành xanh. Các màu trạng thái nghiệp vụ
hiện có không phải màu thương hiệu mới.

## Typography

**Display Font:** BDSG Lora, dự phòng Georgia và serif; có font cục bộ cho
tiếng Việt. **Body Font:** chuỗi sans-serif của token `body`.

### Hierarchy

Các giá trị và công thức trong phần này đối chiếu mã ngày 15/11/2026.

- **Display:** token `display`, cỡ linh hoạt (`clamp(29px, 3.2vw, 40px)`),
  dành cho tiêu đề giao việc. Công thức CSS được giữ ở văn bản vì định dạng
  dimension của schema chỉ nhận đơn vị px, em, rem.
- **Headline:** token `headline`, tiêu đề trang vận hành; xuống (`24px`) ở
  breakpoint điện thoại (`600px`).
- **Title:** token `title`, tiêu đề nhóm công việc gần đây.
- **Body:** token `body`; lời dẫn giao việc dùng giãn dòng (`1.7`).
- **Label:** token `label`, nút thông thường; mẫu công việc dùng cỡ (`12px`).

**The Hai giọng chữ Rule.** Giữ Lora cho tiêu đề giao việc và sans-serif
cho điều khiển; không suy rộng font hệ thống thành font display.

## Layout

Đối chiếu mã ngày 15/11/2026: sidebar cố định rộng (`240px`), phần chính
dịch theo sidebar; vùng nội dung chung tối đa (`1510px`). Vùng giao việc
tối đa (`1040px`); ô soạn và danh sách gần đây tối đa (`760px`), căn giữa.
Mẫu công việc xếp flex, tự xuống hàng, có khoảng cách (`9px`). Đây là bố cục
của trang giao việc, không phải khuôn bắt buộc cho mọi màn hình.

Tại (`900px`) trở xuống, phần chính chiếm toàn chiều rộng và sidebar mở
dạng ngăn trượt có lớp che. Tại (`600px`) trở xuống, lề chính là
(`22px 18px 30px`), mẫu công việc cách nhau (`7px`), vùng bấm mẫu và thanh
mở ngữ cảnh đạt chiều cao tối thiểu (`44px`). Nhịp khoảng cách lấy từ các
token đã quan sát; mã không dùng một bội số duy nhất cho toàn bộ bố cục.

## Elevation & Depth

Ô soạn, panel và thẻ Studio phẳng ở trạng thái tĩnh. Viền và màu nền tạo
phân lớp. Bóng dành cho lớp nổi đang có trong mã; không có quy tắc cấm bóng
toàn ứng dụng. Giá trị đối chiếu ngày 15/11/2026:

- **Danh sách chọn mô-đun:** (`0 13px 35px #00000020`), tách menu khỏi ô soạn.
- **Thông báo nổi:** (`0 8px 30px #00000026`), giữ thông báo trên nội dung.

**The Bề mặt phẳng Rule.** Giữ ô soạn và thẻ Studio không bóng; dùng bóng
của lớp nổi theo đúng vai trò. Bóng và chuyển động đầy đủ nằm ở sidecar.

## Shapes

Góc mềm phân biệt điều khiển nhỏ, panel, thẻ Studio và ô soạn theo nhóm
`rounded`. Mẫu công việc có dạng viên thuốc. Nút chạy là hình tròn
(`border-radius: 50%`), kích thước (`38px × 38px`), theo mã ngày 15/11/2026.
Viền thông thường là (`1px`) dùng `line`; biểu tượng dùng SVG nét mảnh.

## Components

### Buttons

Nút rõ hành động, không dùng màu trang trí làm lớp phân cấp.

- Nút chính dùng token `button-primary`, nút phụ dùng `button-secondary`,
  nút nhẹ dùng `button-subtle`.
- Khi trỏ, nút thường nhích lên (`translateY(-1px)`); chuyển nền và vị trí
  trong (`0.15s`). Nút chính đổi sang token `button-primary-hover`.
- Khi dùng phím, đường bao (`2px`) màu `focus`, lệch ngoài (`3px`).
- Nút vô hiệu hóa dùng độ mờ (`0.6`); nút chạy dùng (`0.5`).

### Chips

Mẫu công việc là nút dạng viên thuốc theo token `task-template`: nền trong,
viền `line`, icon SVG và chữ; khi trỏ đổi nền `surface-hover` và viền
(`#c8c8c0`). Không suy diễn chúng thành trạng thái bộ lọc được chọn.

### Cards / Containers

Panel thông thường dùng góc `panel`; Studio dùng `studio-card`, viền
`line`, không bóng. Tại điện thoại (`600px`), padding thẻ Studio giảm về
(`18px`). Danh sách công việc phân hàng bằng viền, rê chuột đổi nền nhẹ.

### Inputs / Fields

Trường Studio dùng token `field`, viền `line`, có đường bao bàn phím chung.
Ô soạn mục tiêu nằm trong token `task-composer`; vùng gõ có cỡ (`15px`),
giãn dòng (`1.7`), đệm (`22px 24px 12px`). Khi focus bên trong, viền ô soạn
đổi sang (`#8c8c84`), thay cho đường bao riêng của textarea. Ở điện thoại
(`600px`), cỡ chữ ô soạn là (`16px`) và đệm (`18px`).

### Navigation

Sidebar dùng nền `surface-subtle`, chữ `text`; mục hiện tại dùng
`navigation-active`, độ đậm (`600`). Rê chuột dùng `surface-hover`; bàn phím
dùng đường bao chung. Kích thước mục tối thiểu (`42px`), theo mã ngày
15/11/2026; trên màn hình hẹp dùng ngăn trượt mô tả ở Layout.

### Ô soạn giao việc

Tiêu đề và ô nhập tạo điểm chính. Nút chạy tròn dùng màu hành động;
chọn mô-đun là menu nhẹ. Ngữ cảnh và quyền nằm trong khối có thể mở rộng;
biểu tượng xoay khi mở với chuyển động (`160ms ease-out`). Nhãn chế độ là
thông tin phụ dưới tiêu đề, không nâng thành nhãn trang trí phía trên.

Các thông số Components đối chiếu mã ngày 15/11/2026. Chế độ giảm chuyển
động bỏ transition và animation, giữ cuộn trực tiếp.

## Do's and Don'ts

### Do:

- **Do** giữ nền trắng ngà, nút đen than và nhận diện BDSG đã chốt.
- **Do** dùng khác biệt sắc độ và viền để phân lớp bề mặt tĩnh.
- **Do** giữ font tiếng Việt và đường bao bàn phím của từng điều khiển.
- **Do** đọc lớp diện mạo nạp cuối trước khi tái dùng giá trị CSS cũ.

### Don't:

- **Don't** thay thương hiệu BDSG bằng Manus.
- **Don't** biến màu trạng thái nghiệp vụ thành màu nhấn chung.
- **Don't** lấy các khai báo cũ đã bị ghi đè làm chuẩn mới.
- **Don't** xem bố cục trang giao việc là khuôn cố định cho mọi màn hình.

Không chuẩn hoá thành quy tắc: kicker/eyebrow, glyph icon hoặc font hệ thống
cho tiêu đề display ở các nhánh cũ chưa được rà toàn bộ. Tệp này không xác
nhận hay sửa các nhánh đó; chỉ ghi nhận hệ thống từ nguồn và phạm vi nêu trên.
