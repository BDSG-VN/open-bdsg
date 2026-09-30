# Gộp 8 tên miền phụ vào một bảng điều khiển — khuyến nghị kèm số đo

Viết ngày **01/10/2026**. Trả lời câu hỏi: *BDSG có nên bỏ các tên miền phụ
`openos` · `map` · `twin` · `iot` · `llm` · `agent` · `chat` · `web3` và gộp mã vào
một bảng điều khiển không?*

## Khuyến nghị: CÓ, gộp URL — nhưng KHÔNG gộp tiến trình

Hai việc này hay bị lẫn làm một, và lẫn là chỗ hỏng:

- **Gộp URL** — một tên miền, nhiều đường dẫn. `/map5d`, `/twin`, `/iot`… Việc này
  **nên làm**, và rẻ hơn tưởng.
- **Gộp tiến trình** — nhét mọi thứ vào một tiến trình. Việc này **không nên làm**:
  `llm` cần hạn mức riêng, `twin` phục vụ tệp 3D nặng, `map5d` phục vụ tile cần
  HTTP Range. Chúng vẫn nên là tiến trình riêng, chỉ đứng sau cùng một cửa.

Một tên miền phụ không cho bạn khả năng triển khai độc lập — **một tiến trình riêng
mới cho**. Tên miền phụ chỉ thêm một bản ghi DNS, một chứng chỉ, một khối cấu hình,
và một phạm vi cookie nữa.

## Vì sao nên gộp — bốn lý do đo được

**1. Chi phí thật đã trả bằng sự cố thật.** Mỗi tên miền phụ kéo theo DNS + chứng chỉ
+ vhost + phạm vi cookie riêng. Vì cookie không dùng chung nên đã phải dựng thêm cả
một cơ chế đăng nhập xuyên tên miền phụ, cộng các sửa đổi `frame-ancestors` trong CSP.
Toàn bộ khối việc ấy **biến mất** khi chỉ còn một gốc.

**2. Hai trong tám vốn đã là một ứng dụng.** Đo 01/10/2026: `map.bdsg.vn` và
`twin.bdsg.vn` phục vụ **cùng một bộ gói, trùng từng mã băm** —
`index-DzAweHNA.js`, `vendor-react-CwpOsKwA.js`, `vendor-util-DERVbgHk.js`,
`vendor-i18n-B6yirjum.js`. Chúng định tuyến theo hostname lúc chạy. Gộp hai cái này
không phải di trú; là **gỡ một lớp nguỵ trang**.

**3. Ba trong tám gộp được với chi phí bằng không.** Đo: `openos`, `agent`, `web3`
tham chiếu **0 tài nguyên ngoài** — CSS và JS nội dòng, một tệp HTML tự chứa. Chuyển
thẳng, không sửa gì.

**4. Và lý do quyết định — sản phẩm mã nguồn mở.** Một doanh nghiệp cài Open BDSG
**không nên phải tạo 8 bản ghi DNS**. Họ có một tên miền. Nếu kho này bắt họ dựng 8
tên miền phụ thì nó không phải một hệ điều hành cài được; nó là một tập tám dự án.

## Chi phí gộp, đo từng sản phẩm

| sản phẩm | tài nguyên trong HTML | chi phí |
|---|---|---|
| `openos` · `agent` · `web3` | **0 tệp ngoài** | **0** — chuyển thẳng |
| `llm` · `chat` | 2 tệp phẳng mỗi cái | gần 0 — thêm tiền tố đường dẫn |
| `map5d` · `twin` | **chung một bộ gói** | đổi định tuyến hostname → đường dẫn, dựng lại 1 lần |
| `iot` | Vite riêng | đặt `base` rồi dựng lại |

## Cái bẫy phải chặn bằng máy, không bằng trí nhớ

Một ứng dụng một trang dựng với `base: "/"` mà phục vụ ở `/map5d/` sẽ xin
`/assets/index.js` thay vì `/map5d/assets/index.js`. Tài nguyên 404, JavaScript không
chạy, **trang trắng — mà mã HTTP của trang vẫn là 200.**

Đo 01/10/2026: **5 trong 8** sản phẩm đang tham chiếu tài nguyên bằng đường dẫn tuyệt
đối. Gộp mà không dựng lại thì cả 5 trắng trang và mọi phép kiểm nhìn mã HTTP đều báo
lành.

Vì vậy `linh-vuc/do_trang_thai.py` **tải thật từng tệp `.js`/`.css`** mà HTML khai, giải
đường dẫn đúng như trình duyệt, và gắn nhãn `trang-trang` cho đúng trường hợp này. Đã
thử ngược trên một máy chủ dựng sẵn cả ca lành lẫn ca hỏng: bắt đúng 3/3 ca hỏng, và
không báo nhầm ca nào lành.

## Cái gộp KHÔNG giải quyết, nói cho rõ

- **Cookie dùng chung là con dao hai lưỡi.** Một gốc nghĩa là một phạm vi cookie: đăng
  nhập đơn giản hẳn, nhưng một lỗ hổng ở một đường dẫn cũng chạm tới phần còn lại. Bù
  lại bằng nhân: `nhan/quyen.py` kiểm quyền theo **từng công cụ**, không theo đường dẫn.
- **Tile vẫn cần HTTP Range.** Gộp không sửa việc CDN bỏ Range cho tệp `.pmtiles`
  (đo được: máy gốc trả 206 đúng chuẩn, qua CDN thành 200 và mất `Accept-Ranges`).
  Đó là việc riêng ở cài đặt CDN.
- **Chuyển tên miền là việc có hậu quả SEO.** Mọi tên miền phụ đang có phải 301 về
  đường dẫn mới, **một chặng**, không bắc cầu.

## Thứ tự nên làm

1. **Chốt hợp đồng khe cắm** — `linh-vuc/luoc-do.md` + `so_ghi.py` + bài thử ngược.
   ✅ **xong 01/10/2026**, 20/20 phép thử ngược đạt.
2. **Dựng bảng điều khiển đọc sổ ghi + trạng thái đo được.** ✅ **xong**, dựng đủ 8 ô.
3. Dựng lại 5 sản phẩm dùng đường dẫn tuyệt đối, mỗi cái với `base` bằng đường dẫn gắn.
   Cổng nghiệm thu: `do_trang_thai.py` phải báo `chay-duoc`, không `trang-trang`.
4. Gộp `map5d` + `twin` thành một mô-đun (chúng vốn là một bộ gói).
5. Dựng 301 một chặng từ mỗi tên miền phụ về đường dẫn mới, rồi mới gỡ DNS.

Bước 3 trở đi **chưa làm**. Bước 5 đụng DNS và chứng chỉ của hệ đang chạy thật, nên
phải làm sau khi bước 3 và 4 đã có số đo, không làm trước.
