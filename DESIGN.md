---
name: "BDSG Thanh Hoá"
description: "Không gian ứng dụng BDSG theo phong cách iOS, vận hành qua web."
colors:
  primary: "#0067dc"
  primary-hover: "#004fae"
  bg: "#f2f2f7"
  surface: "#fff"
  surface-muted: "#e8e8ed"
  surface-hover: "#e5eefb"
  text: "#303038"
  ink: "#1c1c1e"
  muted: "#62626c"
  line: "#d8d8df"
  link: "#005bc4"
  selection: "#c8e0ff"
typography:
  display:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "44px"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "32px"
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "16px"
    lineHeight: 1.6
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "14px"
    fontWeight: 600
rounded:
  browser-control: "10px"
  control: "12px"
  panel: "16px"
  icon: "18px"
  window: "20px"
  dock: "26px"
spacing:
  small: "8px"
  control: "12px"
  inset: "20px"
  section: "24px"
  group: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "12px 18px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.link}"
    padding: "10px 0"
  search:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "0 18px"
  navigation-selected:
    textColor: "{colors.link}"
    padding: "10px 16px"
  app-icon:
    textColor: "{colors.surface}"
    rounded: "{rounded.icon}"
    size: "68px"
  session-card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.window}"
    padding: "30px 24px"
---

# Design System: BDSG Thanh Hoá

## Overview

**Creative North Star: "Không gian ứng dụng iOS BDSG"**

Chủ quản chọn thay toàn bộ diện mạo sang phong cách iOS ngày 17/11/2026.
Bề mặt sáng, chữ hệ thống, hành động xanh và biểu tượng vuông bo góc tạo
không gian mở ứng dụng, làm việc rồi quay lại. Tên, biểu tượng và tiếng Việt
vẫn thuộc BDSG; không dùng tài sản Apple.

Tài liệu ghi nhận mã ngày 17/11/2026: `ios.css` là stylesheet nạp cuối của
`index.html`, ghi đè các lớp cũ; trình duyệt riêng dùng `trinh-duyet.css`.
Đây là kết quả quét nguồn, không phải xác nhận kiểm thử hình ảnh hay triển
khai. Bố cục từng ứng dụng giữ nhu cầu nghiệp vụ; vỏ webOS là ngữ cảnh chung.

**Key Characteristics:**

- Hành động xanh và chữ tối trên bề mặt sáng.
- Chữ hệ thống dùng cho tiêu đề, nội dung và điều khiển.
- Nhóm nội dung bo góc; Dock và cửa sổ có chiều sâu nhẹ.
- Focus bàn phím rõ, có tùy chỉnh chữ lớn và giảm chuyển động.

## Colors

Token đầu tệp là giá trị chuẩn; bảng màu sáng phân biệt nội dung, tương tác
và lớp nổi. Các màu biểu tượng phân biệt ứng dụng, không thay màu hành động.

### Primary

- **Xanh hành động** (`primary`): nút chính, trạng thái chọn và focus.
- **Xanh khi trỏ** (`primary-hover`): nền nút chính trong lớp iOS chung.
- **Xanh liên kết** (`link`): nút chữ, tài khoản và thao tác cửa sổ.

### Neutral

- **Nền nhóm** (`bg`), **trắng bề mặt** (`surface`): nền ứng dụng và nhóm nội dung.
- **Xám tab** (`surface-muted`), **xanh bề mặt tương tác** (`surface-hover`): lớp phụ.
- **Chữ nội dung** (`text`), **mực tiêu đề** (`ink`), **chữ phụ** (`muted`): phân cấp chữ.
- **Viền phân nhóm** (`line`): chia hàng và khung.
- **Vùng chọn chữ** (`selection`): nền chọn văn bản với chữ mực tối.

**The Hành động xanh Rule.** Hành động chính dùng màu `primary`; màu biểu
tượng chỉ giúp nhận diện ứng dụng. Không lấy nút đen ở stylesheet cũ làm chuẩn.

Tính tương phản từ token ngày 17/11/2026 theo độ chói sRGB: trắng trên xanh
hành động (`5.28:1`), chữ phụ trên nền nhóm (`5.40:1`), xanh liên kết trên
trắng (`6.38:1`). Đây là kiểm tra cặp màu, không phải chứng nhận truy cập
toàn giao diện. Không dùng màu viền nhạt làm chữ hoặc dấu hiệu trạng thái
duy nhất. Các dải màu ở sidecar được tổng hợp để xem trước, không phải token
đã triển khai trong CSS.

## Typography

**Display Font:** chuỗi hệ thống của token `display`.
**Body Font:** cùng chuỗi hệ thống; không cần tải font Apple riêng.

Tiêu đề lớn dùng độ đậm cao và tracking chặt; nội dung vận hành giữ giãn dòng
thoáng. Chữ hệ thống là lựa chọn rõ của phong cách iOS đã được duyệt; Lora
trong stylesheet cũ không còn là vai trò tiêu đề.

- **Display:** tiêu đề Home theo token `display`; xuống cỡ (`32px`) trên điện thoại.
- **Headline:** tiêu đề Switcher và Tùy chỉnh theo token `headline`; xuống (`28px`) ở điện thoại.
- **Body:** lời dẫn Home theo token `body`; trình duyệt đặt nền chữ (`15px`), đoạn văn giãn dòng (`1.6`).
- **Label:** token `label` cho tab và nút; nhãn app thường đậm (`500`), xuống cỡ (`13px`) ở điện thoại.

Tùy chọn chữ lớn tăng các vai trò được khai báo trong shell và trình duyệt;
không coi đây là phép phóng to toàn bộ giao diện hoặc thay cho zoom thiết bị.

## Layout

Các kích thước dưới đây trích mã ngày 17/11/2026. Home, Switcher và Tùy chỉnh
căn giữa, tối đa (`1100px`); Tùy chỉnh thu về (`820px`). Home có lưới sáu cột,
tại (`900px`) xuống bốn cột; thẻ cửa sổ từ ba xuống hai cột rồi một cột tại
(`600px`). Danh mục nền tảng từ hai xuống một cột tại (`900px`).

Vỏ ứng dụng giữ chiều cao viewport; vùng xem cuộn riêng, cao
(`calc(100dvh - 184px)`) trên máy tính và (`calc(100dvh - 168px)`) tại
(`600px`). Khoảng dành riêng bên dưới tách nội dung khỏi Dock cố định;
Dock dùng safe area.

Toast của shell đặt phía trên Dock ở `112px` cộng safe area; thông báo không
che icon điều hướng. Các trang ứng dụng mở độc lập giữ vị trí thông báo riêng.

Tại (`600px`), Home có lề (`20px 20px 30px`), biểu tượng nhỏ hơn, Dock thu
gọn. Tiêu đề và nút tùy chỉnh đứng cùng hàng; lời chào và ngày phụ ẩn để
giữ vùng đầu gọn. Đồng hồ thanh trạng thái cũng ẩn ở kích thước này. Cửa sổ
ứng dụng trở thành toàn chiều ngang, bỏ bo góc và bóng; thanh cửa sổ giữ
nút điều khiển. Nội dung iframe có vùng cuộn riêng. Khi chiều cao màn hình
không quá (`600px`), cửa sổ bỏ chiều cao tối thiểu và dùng
(`calc(100dvh - 168px)`).

Trình duyệt có nội dung tối đa (`1000px`), đệm (`60px 40px 48px`); điện thoại
đổi thành (`30px 20px`), địa chỉ chiếm hàng riêng, tab cuộn ngang và nút tìm
ở Home trình duyệt chiếm cả hàng. Không ép trang nghiệp vụ thành lưới icon.

## Elevation & Depth

Nền Home là gradient nhạt, các nhóm nội dung trắng. Dock kết hợp nền trắng
bán trong suốt, blur (`20px`) và bóng để tách khỏi nội dung; nền trắng vẫn
hiện khi trình duyệt không hỗ trợ blur. Không phụ thuộc blur để đọc chữ.

Bóng trích mã ngày 17/11/2026:

- **Biểu tượng:** (`0 5px 12px #12325b14`).
- **Dock:** (`0 10px 32px #182f5420`).
- **Cửa sổ:** (`0 12px 36px #182f541a`), bỏ ở điện thoại.
- **Thông báo:** (`0 7px 18px #182f541c`).

**The Lớp nổi có vai trò Rule.** Dùng chiều sâu cho Dock, cửa sổ và thông
báo; nhóm danh sách thường chỉ cần nền và đường phân cách.

## Shapes

Điều khiển và panel dùng nhóm `rounded` theo vai trò. Icon Home vuông bo góc,
giảm từ (`68px`) còn (`58px`) trên điện thoại; icon trong Dock nhỏ hơn. Nút
đóng cửa sổ trong Switcher là hình tròn. SVG nét mảnh lấy từ hệ BDSG, không
thay bằng emoji hoặc tài sản Apple.

## Components

### Buttons

Nút chính xanh, chữ trắng theo `button-primary`; nút chữ dùng `button-text`.
Điều khiển shell thường có chiều cao tối thiểu (`44px`). Nút trình duyệt
chính bo (`10px`), đệm (`10px 17px`), hover xanh (`#0055b8`); đây là biến thể
đang có, không đổi token hover của shell.

Focus shell dùng outline xanh (`3px`), cách (`4px`); trình duyệt cách (`3px`).
Các điều khiển kế thừa lớp chung có outline (`2px`), cách (`3px`) và màu
focus được iOS ghi đè xanh. Disabled shell giảm opacity (`0.45`), trình
duyệt (`0.4`); không dùng như trạng thái tải hoặc bằng chứng thiếu quyền.

### Chips

Gợi ý tìm kiếm trong trình duyệt là nút nền xám (`#e4e4eb`), chữ tối
(`#3c3c43`), tối thiểu (`44px`), bo (`10px`); hover (`#d8d8e2`). Đây là gợi
ý thao tác, không phải chip bộ lọc đang chọn.

### Cards / Containers

Thẻ Switcher trắng theo `session-card`, có nút mở và nút đóng riêng. Nhóm
cài đặt, danh mục dùng panel trắng và đường chia hàng; không thêm bóng mỗi
hàng. Cửa sổ app có thanh điều khiển riêng trên iframe.

### Inputs / Fields

Tìm kiếm Home nền trắng, bo panel; chữ nhập (`16px`). Focus đặt lên toàn
khung bằng outline (`3px`), cách (`2px`), không chồng thêm outline input.
Địa chỉ trình duyệt nền nhóm, bo control; focus đổi viền xanh. Nhãn ẩn vẫn
cung cấp tên cho người dùng công nghệ hỗ trợ; placeholder không thay nhãn.

### Navigation

Home có tab thư viện: mục chọn dùng chữ xanh và gạch dưới; trạng thái chọn
phải tiếp tục được biểu đạt bằng thuộc tính trợ năng. Dock giữ đường về Home
và ứng dụng; danh sách cửa sổ mở là nơi tiếp tục hoặc đóng phiên. Nhãn icon
Home đọc được; icon Dock có tên trợ năng dù không hiện nhãn.

### Chuyển ứng dụng và trình duyệt

Chuyển ứng dụng giữ DOM trong bộ nhớ, chỉ cửa sổ hiện tại tương tác; tải lại
chỉ phục hồi metadata có giới hạn. Không trình bày như đình chỉ tiến trình
native. Tìm BDSG dựa trên danh mục; website mở tab thiết bị với giải thích rõ.
Tab và dấu trang trình duyệt là trạng thái phiên, không hứa đồng bộ tài khoản.

Icon Home dịch lên (`2px`) khi trỏ với transition (`180ms`). Chế độ giảm
chuyển động loại animation/transition và cuộn mượt qua lớp tùy chỉnh; media
query giảm chuyển động cũng áp dụng trong shell và trình duyệt. Không dùng
chuyển động làm dấu hiệu duy nhất cho trạng thái.

## Do's and Don'ts

### Do:

- **Do** giữ nhận diện BDSG, tiếng Việt và lựa chọn phong cách iOS mới nhất.
- **Do** dùng hành động xanh, chữ tối và nhóm bề mặt sáng theo token.
- **Do** giữ focus, tên trợ năng, phản hồi lỗi và hỗ trợ giảm chuyển động.
- **Do** kiểm cả điện thoại, máy tính, chữ lớn và trạng thái rỗng trước nghiệm thu.

### Don't:

- **Don't** khôi phục nút đen và tiêu đề Lora từ stylesheet đã bị ghi đè.
- **Don't** dùng tài sản Apple hoặc bịa pin, thời tiết, tín hiệu hay trạng thái kết nối.
- **Don't** mô tả liên kết web như SSO, đồng bộ hoặc ứng dụng native đã cài.
- **Don't** coi việc ghi tài liệu từ mã là bằng chứng giao diện đã qua kiểm thử hình ảnh.
