# Hợp đồng lĩnh vực — một mô-đun cắm vào Open BDSG như thế nào

Một **lĩnh vực** (module) là một mảng nghiệp vụ mà doanh nghiệp bật lên thì có. Tệp này
định nghĩa hợp đồng: thứ gì phải khai, thứ gì máy tự đo, và thứ gì tuyệt đối không được khai.

## Vì sao có hợp đồng trước khi có mô-đun

Ngày 01/10/2026, BDSG chốt sẽ **viết lại từng mảng mã** thay vì tái phân phối phần mềm
thương mại đang dùng ở production. Viết lại là việc nhiều năm và nhiều người. Nếu mỗi bản
viết lại tự nghĩ ra cách cắm riêng thì đến bản thứ ba là không ai ghép được nữa.

Nên **khe cắm phải chốt trước bản viết lại đầu tiên**, không phải sau.

## Một tệp `linh-vuc.json` gồm gì

| trường | bắt buộc | ai điền | ghi chú |
|---|---|---|---|
| `ma` | có | người viết | `^[a-z][a-z0-9_]{0,31}$` — dùng làm **tiền tố công cụ** ở `nhan/quyen.py` |
| `ten` | có | người viết | tên hiển thị, tiếng Việt |
| `tom_tat` | có | người viết | một câu, nói **doanh nghiệp làm được gì**, không nói công nghệ |
| `bieu_tuong` | có | người viết | `{chu, mau}` — một chữ cái và một mã màu |
| `duong_dan` | có | người viết | nơi gắn, ví dụ `/map5d`. **Bắt đầu bằng `/`, không kết thúc bằng `/`** |
| `loai` | có | người viết | `tep-tinh` · `spa-tinh` · `proxy` |
| `cong_cu` | có | người viết | tên công cụ MCP, **phải** khớp `ma` làm tiền tố |
| `quyen_can` | có | người viết | `doc` và/hoặc `ghi` — đúng hằng ở `nhan/quyen.py` |
| `trang_thai` | **không** | **máy đo** | xem dưới |
| `bang_chung` | **không** | **máy đo** | xem dưới |

## Hai trường máy đo, người KHÔNG được khai

`trang_thai` và `bang_chung` **không nằm trong tệp khai báo**. Chúng do
`linh-vuc/do_trang_thai.py` đo và ghi ra `cong/trang-thai-linh-vuc.json`.

Lý do là một bài học đã trả giá trong chính dự án này: một mô-đun tự khai "chạy được" thì
lời khai ấy đúng vào ngày viết và sai dần sau đó, mà **không ai được báo**. Bảng điều khiển
đọc số đo, không đọc lời khai. Lĩnh vực nào chưa đo được thì hiện **"chưa đo"** — không hiện
"chạy được", và cũng không hiện "hỏng".

## Ba loại, và vì sao phân biệt

- **`tep-tinh`** — vài tệp tĩnh, đặt vào là chạy. Gộp dưới một đường dẫn gần như miễn phí.
- **`spa-tinh`** — một ứng dụng một trang đã đóng gói. ⚠ **Phải dựng với `base` bằng đúng
  `duong_dan`.** Một SPA dựng với `base: "/"` mà phục vụ ở `/map5d/` sẽ xin `/assets/x.js`
  thay vì `/map5d/assets/x.js` → tải 404 → **trang trắng, mã HTTP vẫn 200**. Đây là lỗi
  im lặng, và `do_trang_thai.py` kiểm đúng điều này.
- **`proxy`** — có tiến trình riêng phía sau. Đường dẫn chỉ là cửa; tiến trình vẫn triển
  khai độc lập.

## Vì sao gắn theo ĐƯỜNG DẪN chứ không theo TÊN MIỀN PHỤ

Đo ngày 01/10/2026 trên chính hệ của BDSG: 8 sản phẩm nhóm "hệ điều hành" đang ở 8 tên miền
phụ. Mỗi tên miền phụ kéo theo một bản ghi DNS, một chứng chỉ, một khối cấu hình máy chủ,
một phạm vi cookie riêng — và vì cookie không dùng chung nên phải dựng thêm cả một cơ chế
đăng nhập xuyên tên miền phụ. Đó là chi phí thật, trả bằng sự cố thật.

Còn phía khách: **một doanh nghiệp cài Open BDSG không nên phải tạo 8 bản ghi DNS.** Họ có
một tên miền. Mọi lĩnh vực phải nằm dưới nó.

Riêng một phép đo cho thấy việc này rẻ hơn tưởng: `map.bdsg.vn` và `twin.bdsg.vn` đang phục
vụ **cùng một bộ gói, trùng từng mã băm** (`index-DzAweHNA.js`, `vendor-react-CwpOsKwA.js`),
chỉ định tuyến theo hostname. Chúng vốn đã là một ứng dụng.
