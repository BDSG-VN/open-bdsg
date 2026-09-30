# Kiến trúc: Open BDSG là một hệ điều hành cho doanh nghiệp

Viết ngày **26/09/2026**. Đây là tài liệu **đọc trước khi sửa bất cứ thứ gì** trong
phần hệ điều hành của kho.

Mục tiêu do chủ dự án đặt ra, ba tính chất:

1. **Đấu nối MCP** vào các nền tảng trong hệ sinh thái BDSG.
2. Có **mô hình riêng** và **dữ liệu riêng** của doanh nghiệp.
3. **Không phụ thuộc bên thứ ba.**

Tài liệu này mô tả kiến trúc để đạt ba tính chất ấy, và **nói thẳng cái nào hôm nay
là sự kiện, cái nào còn là mục tiêu**. Ranh giới đó nằm ở mục
[§6 Điều này chưa làm được và vì sao](#6-dieu-nay-chua-lam-duoc-va-vi-sao). Ai chỉ
đọc được một mục thì đọc mục ấy.

---

## Mục lục

- [0 · Trạng thái đo được hôm nay](#0-trang-thai-do-duoc-hom-nay)
- [1 · Phép so sánh với hệ điều hành — và chỗ nó hỏng](#1-phep-so-sanh-voi-he-dieu-hanh--va-cho-no-hong)
- [2 · Sơ đồ một lời gọi](#2-so-do-mot-loi-goi)
- [3 · Vì sao máy chủ MCP đang chạy KHÔNG phải là nhân](#3-vi-sao-may-chu-mcp-dang-chay-khong-phai-la-nhan)
- [4 · Bốn quyết định kiến trúc, kèm phản biện](#4-bon-quyet-dinh-kien-truc-kem-phan-bien)
- [5 · Bảng 18 nền tảng và thứ tự làm](#5-bang-18-nen-tang-va-thu-tu-lam)
- [6 · Điều này chưa làm được và vì sao](#6-dieu-nay-chua-lam-duoc-va-vi-sao)
- [7 · Lộ trình ba chặng, mỗi chặng một điều kiện nghiệm thu đo được](#7-lo-trinh-ba-chang-moi-chang-mot-dieu-kien-nghiem-thu-do-duoc)
- [8 · Bố cục thư mục](#8-bo-cuc-thu-muc)

---

<a id="0-trang-thai-do-duoc-hom-nay"></a>

## 0 · Trạng thái đo được hôm nay

Bảng này đứng đầu tài liệu **có chủ ý**. Phần còn lại mô tả một kiến trúc; bảng này
nói kiến trúc ấy hiện đứng ở đâu. Đọc ngược thứ tự thì rất dễ tưởng mọi thứ đã chạy.

| Hạng mục | Trạng thái | Số đo | Đo ngày |
|---|---|---|---|
| Nền tảng đang sống (đo bằng HTTP thật) | **ĐÃ ĐO** | 18 nền tảng trả lời; 15 mã 200, 3 mã 302 | 26/09/2026 |
| Máy chủ MCP đang chạy thật | **ĐÃ CÓ** | 1 máy chủ · 221 dòng · 7 công cụ · JSON-RPC qua stdio | 26/09/2026 |
| Lớp danh tính / quyền / hạn mức / nhật ký (nhân) | **CHƯA CÓ** | chưa viết dòng mã nào | 26/09/2026 |
| Trình điều khiển tách rời theo nền tảng | **CHƯA CÓ** | 7 công cụ hiện nằm trong **một tệp phẳng** | 26/09/2026 |
| Kiến trúc mô hình do BDSG viết | **ĐÃ CÓ** | `mo-hinh/thu_kien_truc.py` → **13/13 ĐẠT** (chạy lại 26/09/2026) | 26/09/2026 |
| Trọng số đầu tiên do BDSG huấn luyện | **ĐÃ CÓ** | 26.878.464 tham số · loss học 8,88 → 2,99 · loss kiểm 4,63 (ppl 102,5) | 26/09/2026 |
| Trọng số ấy gọi được công cụ | **CHƯA ĐO, và gần như chắc chắn KHÔNG** | xem [§6.1](#61-mo-hinh-2688-trieu-tham-so-khong-goi-cong-cu-dang-tin-duoc) | — |
| Mô hình đang phục vụ ở cổng mô hình là của BDSG | **KHÔNG** | API tự khai `bdsg_la_trong_so_bdsg = false` cho **mọi** mã | 26/09/2026 |
| Truy hồi bằng vector (nhúng) | **CHƯA CÓ** | đang là khớp chữ: `pg_trgm` + `tsvector` | 26/09/2026 |
| Vỏ trò chuyện đã mở mã | **ĐÃ CÓ** | `chat/` — 1.272 dòng (97 HTML + 792 JS + 383 CSS), đếm lại 26/09/2026 | 26/09/2026 |

Ngữ liệu: lần gom toàn bộ ngày 26/09/2026 đo **45.416 đoạn · 14,72 MB · 4.367.287
token**. Lần huấn luyện đầu tiên **không** chạy trên toàn bộ số đó mà trên một lát
nhỏ hơn đã kết xuất trước: 11.699 đoạn · 2.068.295 token (xem
[LAN-HUAN-LUYEN-DAU-TIEN.md](LAN-HUAN-LUYEN-DAU-TIEN.md)). Hai con số khác nhau vì
đo ở hai thời điểm khác nhau, không phải vì một trong hai sai — ghi cả hai để không
ai cộng nhầm.

---

<a id="1-phep-so-sanh-voi-he-dieu-hanh--va-cho-no-hong"></a>

## 1 · Phép so sánh với hệ điều hành — và chỗ nó hỏng

Gọi thứ này là "hệ điều hành" chỉ có ích nếu phép so sánh **ràng buộc được thiết kế**.
Một phép so sánh chỉ để nghe cho kêu thì tệ hơn không có: nó khiến người đọc suy ra
những tính chất mà hệ thật không có.

Nên bảng dưới đây có cột thứ tư, và **cột thứ tư mới là cột quan trọng**. Một dòng
không nói được phép so sánh của nó hỏng ở đâu là một dòng đang đánh lừa người đọc.

| Khái niệm HĐH | Trong Open BDSG | Phép so sánh ĐÚNG tới đâu | Nó HỎNG ở đâu |
|---|---|---|---|
| **Lời gọi hệ thống** | Một công cụ MCP | Đúng ở chỗ cốt lõi: đây là ranh giới **duy nhất** mà tiến trình vượt qua để chạm vào thế giới ngoài. Có chữ ký tường minh, có kiểm tham số, có mã lỗi, và **chặn được tại ranh giới**. | Lời gọi hệ thống thật có **ABI ổn định** và chi phí tính bằng micro-giây. Một công cụ MCP là lời gọi mạng: hàng chục tới hàng nghìn mili-giây, hỏng giữa chừng, và chữ ký có thể đổi khi nền tảng đằng sau nâng cấp. **Không được thiết kế như thể nó rẻ và ổn định.** |
| **Trình điều khiển** | Một máy chủ MCP cho một nền tảng | Đúng ở chỗ: nó biết **một** thiết bị, phơi ra giao diện chung, và thay được mà không sửa nhân. Thêm nền tảng = thêm trình điều khiển. | Trình điều khiển thật chạy **trong không gian nhân**, tin cậy cao, và hỏng thì sập máy. Ở đây nó là một tiến trình riêng nói chuyện qua ống dẫn hoặc mạng: **nhân phải coi trình điều khiển là bên không đáng tin**, có thời hạn chờ, và sống sót khi nó chết. Đây không phải chi tiết nhỏ — nó đảo ngược quan hệ tin cậy so với HĐH thật. |
| **Thiết bị** | 18 nền tảng đang chạy | Đúng ở chỗ: mỗi cái có khả năng riêng, trạng thái riêng, và **không** đồng nhất. | Thiết bị phần cứng có lớp chuẩn hoá (một ổ đĩa là một ổ đĩa). 18 nền tảng này thì **không có mẫu số chung**: một cái là CRM, một cái là bản đồ, một cái là không gian 3D. Mọi cố gắng ép chúng vào một giao diện "đọc/ghi" duy nhất sẽ hoặc mất hết ngữ nghĩa, hoặc đẻ ra một giao diện rỗng. **Chấp nhận công cụ khác nhau cho từng nền tảng.** |
| **Tiến trình** | Một phiên agent | Đúng ở chỗ: có danh tính, có thời gian sống, có hạn mức, có thể bị dừng, và **nhật ký quy về nó**. | Tiến trình thật bị nhân cô lập **cưỡng chế** bằng phần cứng (MMU). Một phiên agent thì không: nó "cô lập" chỉ nhờ nhân nhớ kiểm quyền. **Một dòng quên kiểm là hết cô lập** — và không có phần cứng nào bắt lỗi giùm. Đây là chỗ hỏng nghiêm trọng nhất của cả phép so sánh. |
| **Vỏ (shell)** | `chat/` — giao diện trò chuyện | Đúng ở chỗ: vỏ là **một** client trong nhiều client, không đặc quyền, và thay được. Bất kỳ client MCP nào cũng là một vỏ hợp lệ. | Vỏ dòng lệnh nhận lệnh **xác định**: gõ gì chạy nấy. Vỏ ở đây nhận **ngôn ngữ tự nhiên do một mô hình diễn giải**, nên cùng một câu có thể ra hai hành động khác nhau. Hệ quả thiết kế: **mọi hành động có hậu quả phải xác nhận lại bằng dữ liệu cụ thể**, không được tin rằng vỏ đã hiểu đúng. |
| **Nhân** | Định tuyến + danh tính + quyền + hạn mức + nhật ký | Đúng ở chỗ quan trọng nhất: nó là **điểm cưỡng chế duy nhất**, và mọi thứ khác không được phép tự làm phần việc ấy. | Nhân thật có **vòng bảo vệ của CPU**: mã người dùng *không thể* gọi thẳng phần cứng dù có muốn. Nhân ở đây chỉ là quy ước — một trình điều khiển hoàn toàn *có thể* mở cổng riêng và bỏ qua nhân. Cái giữ cho nó không xảy ra là **kỷ luật dự án và phép kiểm**, không phải kiến trúc máy. Phải nói thẳng, vì đây là chỗ hệ này yếu hơn hẳn thứ nó lấy tên. |
| **Bộ nhớ** | Ngữ liệu + lớp truy hồi | Đúng ở chỗ: đây là nơi tri thức **tồn tại lâu dài**, tách khỏi mô hình, thay được mà không huấn luyện lại — đúng như đổi RAM không cần đổi CPU. | Bộ nhớ máy tính **địa chỉ hoá được và chính xác**: đọc ô 42 luôn ra đúng thứ đã ghi. Truy hồi thì **xấp xỉ**: nó trả về thứ *giống* câu hỏi. Tệ hơn, hôm nay nó là **khớp chữ** (`pg_trgm` + `tsvector`), chưa có lớp nhúng — nên hỏi bằng từ khác là không tìm ra, dù ý giống hệt. Gọi nó là "bộ nhớ" mà quên điều này thì sẽ thiết kế ra những tính năng giả định một thứ chính xác mà nó không hề chính xác. |
| **CPU** | Mô hình ngôn ngữ | Đúng ở chỗ: nó là bộ phận **thực thi**, thay được (đổi mã mô hình), và là chỗ nghẽn về tốc độ lẫn chi phí. | CPU **tất định**: cùng đầu vào ra cùng đầu ra, và nó *không bao giờ bịa* ra một chỉ thị. Mô hình thì ngẫu nhiên và **bịa** — đã đo ngay ở lần huấn luyện đầu tiên. Nên nhân **không được tin đầu ra của "CPU" này như tin một lệnh máy**: mọi lời gọi công cụ phải được kiểm theo lược đồ trước khi thi hành. |

**Một hệ quả rút ra từ cả bảng:** bốn dòng cuối (tiến trình, nhân, bộ nhớ, CPU) đều
hỏng theo **cùng một kiểu** — thứ tương ứng trong máy tính thật thì *cưỡng chế* hoặc
*tất định*, còn ở đây là *quy ước* hoặc *xấp xỉ*. Vì vậy thiết kế phải bù lại bằng
kiểm tra tường minh ở mọi ranh giới, thay vì bằng niềm tin vào lớp dưới.

---

<a id="2-so-do-mot-loi-goi"></a>

## 2 · Sơ đồ một lời gọi

Đường đi của một câu hỏi từ người dùng tới một nền tảng và quay về. Các chốt có dấu
`[CHẶN n]` là chỗ **nhân dừng được lời gọi**; mỗi chốt kèm lý do tồn tại.

```
  NGƯỜI DÙNG
      │  "cho tôi xem các bảng dữ liệu về sản phẩm"
      ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ VỎ · chat/                                                       │
 │  - gửi câu hỏi + danh sách công cụ cho mô hình                   │
 │  - KHÔNG tự quyết quyền, KHÔNG tự gọi nền tảng                   │
 └──────────────────────────────┬───────────────────────────────────┘
                                │ lời gọi công cụ do mô hình đề xuất
                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ NHÂN · một tiến trình, một điểm cưỡng chế                        │
 │                                                                  │
 │  [CHẶN 1] DANH TÍNH — phiên này là ai?                           │
 │           không xác định được ⇒ TỪ CHỐI. Không có "khách ẩn      │
 │           danh mặc định": ẩn danh thì nhật ký vô nghĩa.          │
 │                                                                  │
 │  [CHẶN 2] LƯỢC ĐỒ — tham số có đúng chữ ký công cụ không?        │
 │           Sai ⇒ TỪ CHỐI tại đây. Vì "CPU" bịa được (§1), không   │
 │           được để tham số bịa đi tiếp tới nền tảng.              │
 │                                                                  │
 │  [CHẶN 3] QUYỀN — danh tính này được gọi công cụ này không?      │
 │           Mặc định KHÔNG. Danh sách trắng, không phải đen.       │
 │                                                                  │
 │  [CHẶN 4] CỔNG GHI — công cụ có khai `ghi = true` không?         │
 │           Nếu có: phải có quyền ghi RIÊNG, và phải qua xác nhận. │
 │           Công cụ không khai gì ⇒ coi là CHỈ ĐỌC, và nếu nó lỡ   │
 │           ghi thì đó là lỗi của trình điều khiển, không phải     │
 │           một "tính năng" được phép.                             │
 │                                                                  │
 │  [CHẶN 5] HẠN MỨC — số lời gọi / thời gian / khối lượng trả về.  │
 │           Vượt ⇒ TỪ CHỐI. Một vòng lặp của agent không được      │
 │           phép biến thành một trận tự đánh mình.                 │
 │                                                                  │
 │  ── GHI NHẬT KÝ ── ghi ở CẢ HAI nhánh: cho phép và từ chối.      │
 │     Chỉ ghi lúc cho phép thì không trả lời được câu "ai đã THỬ   │
 │     làm gì" — mà đó thường mới là câu cần trả lời.               │
 └──────────────────────────────┬───────────────────────────────────┘
                                │ lời gọi đã hợp lệ hoá
                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ TRÌNH ĐIỀU KHIỂN · một nền tảng, một trình                       │
 │  - đổi lời gọi công cụ  →  lời gọi API của nền tảng              │
 │  - đổi kết quả API      →  kết quả công cụ                       │
 │  - KHÔNG xác thực người dùng, KHÔNG quyết quyền, KHÔNG ghi       │
 │    nhật ký kiểm toán (nhân làm cả ba)                            │
 └──────────────────────────────┬───────────────────────────────────┘
                                │ HTTP tới API của nền tảng
                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ NỀN TẢNG · 1 trong 18                                            │
 └──────────────────────────────┬───────────────────────────────────┘
                                │ dữ liệu trả về
                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ NHÂN (đường về)                                                  │
 │  [CHẶN 6] KHỐI LƯỢNG — cắt kết quả quá lớn, và NÓI RÕ là đã cắt. │
 │           Cắt im lặng làm mô hình kết luận trên dữ liệu thiếu mà │
 │           không ai biết. Đã gặp đúng họ lỗi này ở dự án khác.    │
 │  ── GHI NHẬT KÝ: mã kết quả, thời gian chạy, số bản ghi ──       │
 └──────────────────────────────┬───────────────────────────────────┘
                                ▼
                        VỎ  →  NGƯỜI DÙNG
```

**Đọc sơ đồ này theo đúng một câu:** mọi mũi tên đi ra thế giới đều xuyên qua hộp
NHÂN, và hộp NHÂN là hộp duy nhất biết *ai* đang gọi. Nếu ngày nào đó có một mũi tên
đi tắt từ VỎ hoặc từ TRÌNH ĐIỀU KHIỂN thẳng ra NỀN TẢNG, thì kiến trúc này đã hỏng,
dù mọi thứ vẫn chạy.

---

<a id="3-vi-sao-may-chu-mcp-dang-chay-khong-phai-la-nhan"></a>

## 3 · Vì sao máy chủ MCP đang chạy KHÔNG phải là nhân

Dự án **đã có** một máy chủ MCP chạy thật: 221 dòng, 7 công cụ, nói JSON-RPC qua
stdio, phục vụ CDP và danh mục dữ liệu (đang quản trị 3 nguồn: một MariaDB, một
PostgreSQL, một MySQL). Nó hữu ích và nó chạy. Nhưng nó là **bằng chứng khái niệm**,
không phải nền của hệ điều hành, và ba giới hạn dưới đây **chính là lý do phải có nhân**.

**(a) Vận chuyển là SSH vào máy chủ sản phẩm.** Mỗi công cụ cuối cùng chạy
`subprocess.run(SSH + [cmd])` với một khoá riêng ghi cứng trong mã. Nghĩa là mỗi công
cụ là **một lệnh tuỳ ý trên máy sản phẩm**. Đó không phải trình điều khiển; đó là một
cửa hậu có giao diện đẹp. Phải nói thẳng vì lựa chọn ấy ban đầu có lý do chính đáng —
điểm cuối quản trị của CDP **cố ý** không mở ra Internet, nên SSH là đường duy nhất
còn lại. Lý do đúng vẫn không làm cho kết quả an toàn: cái cần thay không phải động cơ
mà là **hình dạng của ranh giới**.

**(b) 7 công cụ, một lĩnh vực, một tệp phẳng.** Thêm một nền tảng là **sửa tệp ấy**.
Với 18 nền tảng thì tệp ấy hoặc phình ra không đọc nổi, hoặc bị tách vội theo cách
không ai thống nhất. Đây đúng là lý do hệ điều hành thật phát minh ra khái niệm trình
điều khiển.

**(c) Không có lớp quyền, không có nhật ký.** Đo ngày 26/09/2026: tìm trong toàn tệp
các từ khoá `quyen|auth|nhat_ky` trả về **đúng 1 khớp**, và khớp ấy là dòng 56 — một
tiêu đề `Authorization` **gửi đi** để máy chủ MCP tự xác thực với dịch vụ đích. Tức là
xác thực của *máy chủ với dịch vụ*, **không phải** của *người gọi với máy chủ*. Hai
thứ ấy khác nhau hoàn toàn: cái đang có chứng minh máy chủ có quyền; **không có** cái
nào hỏi xem người gọi là ai. Hệ quả đo được: hệ hiện tại **không trả lời được câu
"ai đã làm gì"**.

> Ghi lại phép đo cho đúng: nói "grep trả về rỗng" là sai, nó trả về 1 dòng. Điều
> đúng là dòng ấy không phải lớp quyền. Một tài liệu kiến trúc mà làm tròn số đo cho
> gọn thì nó dạy người đọc thói quen tin số chưa kiểm.

---

<a id="4-bon-quyet-dinh-kien-truc-kem-phan-bien"></a>

## 4 · Bốn quyết định kiến trúc, kèm phản biện

Bốn quyết định này **đã chốt**. Mỗi mục nêu cả **cái giá của lựa chọn ngược lại** —
một quyết định không nêu được điều đó thì chưa phải quyết định, mới chỉ là sở thích.

### 4.1 · MCP là ranh giới lời gọi hệ thống

Không phải REST. Không phải một API riêng do dự án tự đặt ra.

**Vì sao.** MCP là thứ mô hình **đã nói sẵn**. Lấy nó làm ranh giới thì mọi client
biết MCP đều là một **vỏ hợp lệ**: giao diện trò chuyện của BDSG, một trợ lý khác,
hay một script chạy trong đêm. Và một công cụ MCP đóng đúng vai một lời gọi hệ thống —
có chữ ký, có quyền, ghi nhật ký được.

**Nếu làm ngược lại — tự định nghĩa một API riêng.** Cái giá không phải là "phải viết
thêm tài liệu". Cái giá là **mỗi client mới phải viết một bộ chuyển đổi**, và mô hình
thì không biết API ấy nên phải dạy nó bằng lời nhắc — tức là bằng thứ không kiểm được
và trôi theo từng bản mô hình. Rốt cuộc lại phải viết một lớp dịch sang MCP, chỉ là
viết muộn hơn và trong hoàn cảnh xấu hơn. Chọn REST thuần thì mất luôn thứ MCP cho
không: **mô tả công cụ do máy đọc được**, thứ khiến mô hình biết công cụ nào tồn tại
mà không cần ai nhắc.

### 4.2 · Nhân sở hữu danh tính, quyền, hạn mức, nhật ký. Trình điều khiển thì không.

Đây là **luật quan trọng nhất** trong tài liệu này.

**Vì sao.** Trình điều khiển chỉ biết **một** việc: đổi một lời gọi công cụ thành một
lời gọi API của nền tảng nó phụ trách, rồi trả kết quả về. Không hơn.

**Nếu làm ngược lại — mỗi trình điều khiển tự xác thực.** 18 nền tảng sẽ cho ra
**18 mô hình quyền khác nhau**, vì chúng vốn khác nhau: một cái có vai trò nhân viên,
một cái có nhóm người dùng, một cái chỉ có khoá API dùng chung. Hệ quả cụ thể, không
phải trừu tượng:

- Không ai trả lời được **"ai đã làm gì"**, vì nhật ký nằm ở 18 chỗ với 18 định dạng
  và 18 khái niệm "người dùng" không khớp nhau.
- Thu hồi quyền của một người phải làm ở 18 nơi, và **chỉ cần sót một nơi là chưa thu hồi**.
- Một lỗi quyền chỉ vá được ở một trình điều khiển, 17 cái kia vẫn mang lỗi ấy.

Điều đánh đổi phải nói ra: nhân trở thành **điểm hỏng duy nhất** và là chỗ nghẽn.
Chấp nhận, vì một điểm hỏng **nhìn thấy được** thì tốt hơn 18 điểm hỏng phân tán mà
không ai kiểm được — và vì một điểm cưỡng chế là thứ duy nhất khiến câu hỏi
"ai đã làm gì" có câu trả lời.

### 4.3 · Mặc định chỉ đọc. Công cụ có GHI phải khai tường minh và đi qua một cổng riêng.

**Vì sao.** Một hệ điều hành mà mọi tiến trình ghi vào mọi thiết bị theo mặc định thì
không phải hệ điều hành, đó là một trách nhiệm pháp lý. Cụ thể hơn trong bối cảnh này:
"CPU" của hệ **bịa** (đã đo, §6.1). Cho một bộ phận biết bịa quyền ghi mặc định vào
18 nền tảng sản phẩm là kết hợp tệ nhất có thể.

Cách làm: mỗi công cụ khai một trường `ghi` trong siêu dữ liệu. **Không khai = chỉ đọc**
(mặc định an toàn, fail-closed). Nhân từ chối thi hành công cụ có `ghi = true` nếu
danh tính không có quyền ghi **riêng** cho nền tảng ấy.

**Nếu làm ngược lại — cho ghi theo mặc định, chặn cái nguy hiểm.** Đó là danh sách đen,
và danh sách đen luôn thiếu đúng một mục: mục vừa được thêm vào tuần trước. Với danh
sách trắng, một công cụ mới bị quên khai quyền thì **nó không chạy** — phiền, và ai
đó sẽ phàn nàn. Với danh sách đen, một công cụ mới bị quên chặn thì **nó xoá dữ liệu**,
và không ai phàn nàn cho tới khi đã muộn. Chọn kiểu hỏng ồn ào thay vì kiểu hỏng im lặng.

### 4.4 · Mô hình cục bộ là mặc định. Bên thứ ba phải khai tường minh, và KHÔNG CÓ đường lui im lặng.

**Vì sao.** Một chuỗi dự phòng kiểu "cục bộ trước, đám mây sau" nghe rất chu đáo, và
nó phá đúng thứ hệ này hứa: người dùng **tưởng** mình chạy cục bộ, còn câu hỏi thì âm
thầm đi ra ngoài mỗi khi máy cục bộ chậm hoặc chưa kịp khởi động. Thà hỏng ra mặt còn
hơn gửi dữ liệu đi mà không ai biết. Quyết định này đã được ghi sẵn trong
`tich-hop/bdsg-cuc-bo.json5` và tài liệu này chỉ nâng nó lên thành luật của cả hệ.

**Nếu làm ngược lại — bật dự phòng tự động.** Cái giá là **mất khả năng trả lời câu
"dữ liệu này đã đi đâu"**, và mất nó theo cách không phát hiện được từ bên trong: hệ
vẫn trả lời đúng, vẫn nhanh, chỉ là một phần câu hỏi đã rời khỏi doanh nghiệp. Với
một hệ mà điểm bán chính là "dữ liệu riêng, không phụ thuộc bên thứ ba", đây không
phải một lỗi tính năng — nó là lời hứa bị phá ở đúng chỗ người ta không kiểm được.

Hệ quả bắt buộc, viết ra để không ai "sửa" nhầm về sau:

- Hồ sơ đi ra ngoài phải là một **lựa chọn có tên**, do người dùng chọn.
- Khi mô hình cục bộ hỏng, hệ **báo hỏng**. Không âm thầm chuyển hướng.
- Nhật ký phải ghi **mô hình nào đã trả lời**, cho từng lượt. Không ghi thì câu hỏi
  "lượt này chạy cục bộ hay không" không có câu trả lời — và một lời hứa không kiểm
  được thì không phải lời hứa.

---

<a id="5-bang-18-nen-tang-va-thu-tu-lam"></a>

## 5 · Bảng 18 nền tảng và thứ tự làm

**Cột "Mã HTTP" là số đo thật ngày 26/09/2026.** Cột "Là gì" và cột "Công cụ nên phơi"
là **mô tả và đề xuất**, chưa phải phép đo — người viết trình điều khiển phải kiểm lại
API thật của nền tảng trước khi tin cột ấy.

Hai nền tảng quản trị nội bộ trong danh sách **không viết tên miền ra đây**: kho này
công khai và cổng `cong/khong-ha-tang.py` chặn tên miền quản trị nội bộ. Chúng được
gọi theo vai trò. Đây là hạn chế có chủ ý, không phải sót.

| # | Nền tảng | Mã HTTP | Là gì | Công cụ trình điều khiển nên phơi (đọc trước) | Ưu tiên |
|---:|---|:---:|---|---|:---:|
| 1 | **Cổng mô hình** (`llm.bdsg.vn`) | 200 | API tương thích OpenAI; mã `openbiz-vn-chat`, `openbiz-vn-reasoner` | liệt kê mô hình · sinh văn bản · đọc trạng thái | **P0** |
| 2 | **Danh mục dữ liệu** (vai trò: quản trị siêu dữ liệu) | 200 | Đang quản trị 3 nguồn dữ liệu | tìm bảng · xem cột · liệt kê nguồn — **3 công cụ này đã chạy thật** | **P0** |
| 3 | **CRM** (vai trò: quản trị khách hàng) | 302 | Hệ CRM nội bộ — nơi dữ liệu nghiệp vụ dày nhất | tìm khách hàng · xem hồ sơ · liệt kê việc/dự án · *(ghi: tạo việc — chặng 2)* | **P0** |
| 4 | **bdsg.vn** | 200 | Cổng nội dung và danh bạ chính | tìm nội dung · đọc trang · tra danh bạ doanh nghiệp | P1 |
| 5 | **app.bdsg.vn** | 302 | Siêu ứng dụng; **nguồn danh tính SSO của hệ sinh thái** | tra người dùng · kiểm phiên · đọc hồ sơ | P1 |
| 6 | **bdsgland.bdsg.vn** | 200 | Dữ liệu dự án bất động sản | tìm dự án · xem chi tiết · lọc theo địa bàn | P1 |
| 7 | **map.bdsg.vn** | 200 | Nền bản đồ và dữ liệu địa lý | định vị đơn vị hành chính · tìm quanh điểm · đọc lớp dữ liệu | P1 |
| 8 | **bdsgacademy.bdsg.vn** | 200 | Hệ quản lý đào tạo | tìm khoá học · xem tiến độ học viên | P1 |
| 9 | **bdsgpos.bdsg.vn** | 200 | Bán hàng tại điểm, kho | tra tồn kho · đọc đơn hàng · báo cáo doanh thu | P1 |
| 10 | **chat.bdsg.vn** | 200 | Hỏi đáp có truy hồi kèm trích dẫn | hỏi kèm trích dẫn · tra nguồn của một câu trả lời | P1 |
| 11 | **twin.bdsg.vn** | 200 | Không gian 3D thương mại hoá | liệt kê không gian · đọc trạng thái đơn | P2 |
| 12 | **iot.bdsg.vn** | 200 | Nền tảng thiết bị | liệt kê thiết bị · đọc chuỗi số đo gần nhất | P2 |
| 13 | **news.bdsg.vn** | 200 | Tin tức | tìm bài · đọc bài | P2 |
| 14 | **video.bdsg.vn** | 200 | Video | tìm video · đọc mô tả | P2 |
| 15 | **groupchat.bdsg.vn** | 200 | Nhắn tin nhóm | liệt kê phòng · đọc tin gần nhất | P2 |
| 16 | **ask.bdsg.vn** | 200 | Hỏi đáp cộng đồng | tìm câu hỏi · đọc câu trả lời | P2 |
| 17 | **connect.bdsg.vn** | 200 | Kết nối người dùng | tìm hồ sơ · đọc kết nối | P2 |
| 18 | **cloud.bdsg.vn** | 302 | Cấp phát hạ tầng cho khách | liệt kê tài nguyên đã cấp · đọc trạng thái | P2 |

### Vì sao chia ưu tiên như thế — và vì sao KHÔNG hứa làm hết

Hứa làm cả 18 trình điều khiển là cách chắc chắn nhất để không cái nào xong tử tế.
Ba mức được chia theo **một câu hỏi duy nhất**: cái nào cần thiết để chứng minh kiến
trúc chạy?

- **P0 (3 nền tảng)** là tập **nhỏ nhất** đủ để chạy hết một vòng thật: một chỗ có sẵn
  công cụ đọc đã chạy được (danh mục dữ liệu), một chỗ có dữ liệu nghiệp vụ thật đáng
  hỏi (CRM), và "CPU" (cổng mô hình). Ba cái này đủ để nghiệm thu chặng 1 và chặng 2.
  Thêm cái thứ tư vào P0 chỉ làm chậm phép chứng minh mà không chứng minh thêm điều gì.
- **P1 (6 nền tảng)** là nơi có **dữ liệu doanh nghiệp thật** và **nguồn danh tính**.
  Làm sau khi nhân đã được chứng minh, vì trước đó mọi trình điều khiển đều có nguy
  cơ phải viết lại theo giao diện nhân.
- **P2 (9 nền tảng)** chủ yếu là nội dung và cộng đồng. Giá trị cho một trợ lý doanh
  nghiệp thấp hơn hẳn, và nhiều cái trong nhóm này là bản tự bảo trì nên API có thể
  đổi — **chi phí bảo trì cao, lợi ích thấp**. Làm khi có nhu cầu cụ thể, không làm
  vì cho đủ bộ.

---

<a id="6-dieu-nay-chua-lam-duoc-va-vi-sao"></a>

## 6 · Điều này chưa làm được và vì sao

Mục này tồn tại để không ai đọc tài liệu trên rồi tưởng nó mô tả một thứ đang chạy.
**Tính đến 26/09/2026, chưa có dòng mã nào của nhân được viết.** Phần trên là thiết kế.

<a id="61-mo-hinh-2688-trieu-tham-so-khong-goi-cong-cu-dang-tin-duoc"></a>

### 6.1 · Mô hình 26,88 triệu tham số của BDSG KHÔNG gọi công cụ đáng tin được

BDSG **đã có** trọng số đầu tiên do chính mình huấn luyện (26/09/2026): 26.878.464
tham số, loss học 8,88 → 2,99, loss kiểm 4,63 (ppl 102,5), sinh được tiếng Việt
nghiệp vụ mạch lạc — **và bịa nhiều**.

Một mô hình cỡ ấy **không giữ nổi định dạng**. Gọi công cụ đòi hỏi bám đúng lược đồ,
đúng tên tham số, đúng kiểu, nhiều lượt liên tiếp. Đây là **ràng buộc cứng**, không
phải một mục "sẽ cải thiện dần".

Nên hôm nay hệ này chạy bằng mô hình đang phục vụ ở cổng mô hình, mà trọng số đó
**KHÔNG phải của BDSG** — API tự khai `bdsg_la_trong_so_bdsg = false` cho mọi mã.

> **Mục tiêu "không cần bên thứ ba" là MỤC TIÊU, chưa phải sự kiện.**
> Viết khác đi chính là kiểu "mở giả" mà kho này lập ra để chống.

### 6.2 · Chưa đo tính năng nào thật sự chạy với mô hình nhỏ

Chưa có phép đo nào cho câu "mô hình 26,88 triệu tham số gọi đúng công cụ bao nhiêu
phần trăm số lượt". **Chưa đo nghĩa là chưa biết**, không phải là "chắc thấp" — dù
lý do ở §6.1 khiến ai cũng đoán là thấp. Đoán không thay được đo, và bộ thử phải được
đóng băng **trước** khi đo, nếu không con số đầu tiên đã là con số đã bị chỉnh.

### 6.3 · Chưa có lớp nhúng; truy hồi vẫn là khớp chữ

Lớp truy hồi dùng `pg_trgm` + `tsvector` — **khớp chữ, không khớp vector** — vì cổng
mô hình nội bộ không có mô hình nhúng nào. Hệ quả cụ thể: hỏi bằng từ khác với từ
trong dữ liệu thì **không tìm ra**, dù ý hệt nhau. Gọi truy hồi là "bộ nhớ" của hệ
điều hành (§1) mà quên điều này thì sẽ thiết kế ra những tính năng giả định một thứ
chính xác hơn thực tế.

### 6.4 · Máy chủ MCP hiện tại chưa thay thế được

Ba giới hạn ở §3 vẫn nguyên: đi qua SSH vào máy sản phẩm, một tệp phẳng, không có lớp
quyền và nhật ký. Nó vẫn chạy và vẫn dùng được cho việc tra cứu, nhưng **không được
lấy làm nền** cho phần còn lại.

### 6.5 · Những thứ tài liệu này cố ý chưa quyết

Ghi ra để không ai tưởng đã có câu trả lời ở đâu đó:

- **Vận chuyển giữa nhân và trình điều khiển** — stdio hay HTTP nội bộ. Chưa chọn,
  chưa đo độ trễ của cả hai.
- **Nơi lưu nhật ký** và thời hạn giữ. Nhật ký kiểm toán có ràng buộc pháp lý riêng.
- **Mô hình vai trò**: vai trò theo nền tảng, hay một tập vai trò chung của hệ. Chọn
  sai hướng này thì phải viết lại nhân, nên phải quyết **trước** chặng 2.
- **Danh tính** lấy từ SSO sẵn có hay tách riêng cho hệ điều hành.

---

<a id="7-lo-trinh-ba-chang-moi-chang-mot-dieu-kien-nghiem-thu-do-duoc"></a>

## 7 · Lộ trình ba chặng, mỗi chặng một điều kiện nghiệm thu đo được

Mỗi chặng có **đúng một** điều kiện nghiệm thu, và điều kiện ấy phải **đo được** —
tức là chạy được, ra một kết quả đúng/sai, và người khác lặp lại được. Một lời hứa
kiểu "nhân hoạt động ổn định" không phải điều kiện nghiệm thu.

### Chặng 1 — Nhân tối thiểu + một trình điều khiển chỉ đọc

Làm: nhân với 5 chốt chặn của §2, một trình điều khiển cho **danh mục dữ liệu** (nền
tảng đã có 3 công cụ đọc chạy thật, nên chặng này đo **nhân**, không đo việc nối API).

> **Điều kiện nghiệm thu.** Một công cụ **đọc** được gọi từ vỏ `chat/`, trả **đúng**
> dữ liệu, và sinh ra **một** dòng nhật ký nói **ai** đã gọi. Cụ thể, cả bốn phép sau
> cùng đúng trong một lượt chạy:
> 1. Gọi công cụ tìm bảng từ vỏ → trả về ≥ 1 bảng có định danh đầy đủ **kiểm chứng
>    lại được** ở nền tảng nguồn.
> 2. Tệp nhật ký tăng **đúng 1 dòng**; dòng ấy có: danh tính, tên công cụ, tham số
>    (đã che giá trị nhạy cảm), thời điểm, mã kết quả.
> 3. Gọi lại lần hai → nhật ký có **2** dòng. (Bắt đúng lỗi "ghi một lần rồi thôi".)
> 4. Gỡ quyền của danh tính ấy rồi gọi lại → lời gọi **bị từ chối**, **và** nhật ký
>    vẫn tăng thêm 1 dòng ghi "từ chối". (Đây mới là phép đo quan trọng nhất: nó
>    chứng minh nhân **chặn được**, chứ không chỉ **ghi được**.)

### Chặng 2 — Ba trình điều khiển + cổng ghi

Làm: đủ 3 nền tảng P0, và cổng ghi của §4.3 với **đúng một** công cụ ghi đầu tiên.

> **Điều kiện nghiệm thu.** Hai phép, cùng phải đúng:
> 1. **Cổng ghi cưỡng chế được.** Một công cụ khai `ghi = true` chạy thật trên dữ
>    liệu thử: số bản ghi ở nền tảng đích thay đổi **đúng bằng 1**; cùng lời gọi ấy
>    với một danh tính **chỉ đọc** thì **bị từ chối**; nhật ký có **cả hai** dòng
>    (một cho phép, một từ chối).
> 2. **Trình điều khiển thật sự tháo lắp được.** Thêm trình điều khiển thứ ba **không
>    sửa một dòng nào trong nhân** — đo bằng khác biệt mã: chỉ chạm thư mục của trình
>    điều khiển mới, cộng **một** dòng đăng ký. Nếu phải sửa nhân thì §4.2 mới chỉ là
>    lời nói, và chặng 2 **chưa đạt**.

### Chặng 3 — Mô hình riêng chạy được vỏ

Làm: huấn luyện tới mức mô hình của BDSG **gọi công cụ** được, rồi trỏ vỏ vào chính nó.

> **Điều kiện nghiệm thu.** Trên một **bộ thử gọi công cụ 100 lượt được đóng băng
> TRƯỚC khi đo**, công bố **tỉ lệ gọi đúng lược đồ** đo được, kèm ngày và kèm số đo
> của mô hình bên thứ ba trên **cùng** bộ thử để so. Và trường
> `bdsg_la_trong_so_bdsg` trả **true** trên chính điểm cuối đang phục vụ vỏ.
>
> **Ngưỡng đạt chưa đặt, và cố ý chưa đặt.** Chưa có đường cơ sở nào cho phép gọi
> công cụ của mô hình này (§6.2). Đặt một con số bây giờ là **bịa một con số**, rồi
> sau đó hoặc phải hạ nó xuống cho vừa kết quả, hoặc phải giả vờ là đã đạt. Ngưỡng
> do chủ dự án chốt **sau** lần đo đầu tiên, và được ghi vào chính tài liệu này kèm ngày.

**Một ghi chú về thứ tự.** Chặng 3 đứng sau cùng không phải vì nó ít quan trọng nhất —
nó chính là mục tiêu số 2 và số 3 của cả dự án. Nó đứng sau vì hai chặng đầu **không
phụ thuộc** vào nó: nhân, quyền, nhật ký và trình điều khiển chạy được với bất kỳ mô
hình nào. Làm ngược lại — chờ có mô hình riêng rồi mới xây nhân — thì hệ sinh thái
không có gì trong nhiều tháng, mà mô hình vẫn chưa chắc tới.

---

<a id="8-bo-cuc-thu-muc"></a>

## 8 · Bố cục thư mục

**Một phần đã tồn tại, một phần còn là đề xuất — bảng dưới ghi rõ cái nào là cái nào.**
Đo bằng cách liệt kê cây thư mục lúc **11:13 ngày 26/09/2026**. Các tệp này đang được
viết trong cùng phiên làm việc, nên **hãy liệt kê lại trước khi tin bảng này**; trạng
thái thư mục đổi theo giờ, tài liệu thì không.

```
nhan/                    ← danh tính · quyền · hạn mức · nhật ký · định tuyến
  danh_tinh.py             ĐÃ CÓ   ai đang gọi
  quyen.py                 ĐÃ CÓ   danh sách TRẮNG, mặc định từ chối
  han_muc.py               ĐÃ CÓ   số lời gọi · thời gian · khối lượng trả về
  nhat_ky.py               CHƯA    ghi CẢ hai nhánh: cho phép và từ chối
  dinh_tuyen.py            CHƯA    tên công cụ  →  trình điều khiển
trinh-dieu-khien/        ← mỗi nền tảng một thư mục
  hop_dong.py              ĐÃ CÓ   lược đồ công cụ; trường `ghi` thiếu ⇒ chỉ đọc
  danh-muc-du-lieu/        CHƯA
  crm/                     CHƯA
  cong-mo-hinh/            CHƯA
cong/
  khong-cua-hau.py         ĐÃ CÓ   cổng chặn khuôn "cửa hậu có giao diện đẹp" (§3)
```

Hai quy tắc đi kèm bố cục này, và chúng **đáng thành phép kiểm tự động**:

1. Thư mục `trinh-dieu-khien/` **không được** chứa mã xác thực người dùng, mã quyết
   quyền, hay mã ghi nhật ký kiểm toán. Có là vi phạm §4.2.
2. Công cụ không khai trường `ghi` thì nhân coi là **chỉ đọc**. Trình điều khiển nào
   ghi trong một công cụ chỉ-đọc là **lỗi**, không phải "tính năng tiện".

**Một ranh giới còn phải chốt, ghi ra chứ không lờ đi.** `hop_dong.py` hiện nằm trong
`trinh-dieu-khien/`. Nó là **lược đồ công cụ dùng chung**, nên đặt ở đó thì hợp lý theo
nghĩa "trình điều khiển khai công cụ của mình". Nhưng chính nhân là bên **cưỡng chế**
trường `ghi` của lược đồ ấy (chốt 4 ở §2), nên nếu về sau có mã *quyết định* nằm trong
tệp này thì quy tắc 1 ở trên bị vi phạm ngay tại chỗ dễ bỏ sót nhất. Quy ước đề xuất:
`hop_dong.py` chỉ **mô tả và kiểm hình dạng**; mọi câu "được hay không được" nằm trong
`nhan/`. Ai sửa tệp ấy, hãy giữ ranh giới này hoặc chuyển nó sang `nhan/`.

---

## Cách kiểm chứng tài liệu này

Mọi con số trong tài liệu này **chạy lại được**:

| Khẳng định | Chạy gì để kiểm |
|---|---|
| Kiến trúc mô hình 13/13 đạt | `.venv/bin/python mo-hinh/thu_kien_truc.py` |
| Vỏ trò chuyện 1.272 dòng | `wc -l chat/index.html chat/chat.js chat/giao-dien.css` |
| Kho không lộ bí mật / hạ tầng | `cong/chay-tat-ca.sh` |
| Cổng mô hình khai `bdsg_la_trong_so_bdsg` | gọi `/v1/models` ở cổng mô hình và đọc trường ấy |
| Máy chủ MCP 221 dòng · 7 công cụ · 1 khớp `auth` | đếm dòng và tìm từ khoá trên chính tệp ấy (tệp nằm **ngoài** kho công khai này) |

Số nào trong tài liệu này không có dòng tương ứng ở bảng trên thì nó là **đề xuất**,
không phải phép đo. Khi một đề xuất được đo, hãy thêm nó vào bảng này kèm ngày.
