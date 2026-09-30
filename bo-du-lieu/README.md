# Bộ dữ liệu mở — Open BDSG

Thẻ dữ liệu (datasheet) của phần ngữ liệu mở trong dự án **Open BDSG**.

- **Ngày đo mọi con số trong tệp này:** 25/09/2026.
- **Giấy phép bộ dữ liệu:** CC-BY-4.0 (xem mục *Giấy phép và cách trích dẫn*).
- **Xuất xứ chi tiết từng nguồn:** [GIAY-PHEP-NGUON.md](GIAY-PHEP-NGUON.md).
- **Lược đồ JSONL:** [luoc-do.md](luoc-do.md).
- **Script xuất:** [xuat.py](xuat.py).

> Nguyên tắc của thẻ này: **không có số nào được viết ra mà chưa đo.** Chỗ nào chưa đo
> thì ghi thẳng là *chưa đo*. Một bản phát hành nghiêm túc được đánh giá bằng chỗ nó
> nói KHÔNG, không phải bằng chỗ nó khoe có.

---

## 1. Trước hết: bộ này KHÔNG phải cái gì

Ba hiểu nhầm dễ xảy ra nhất, nói ngay từ đầu để người đọc không phải dò tìm:

**1.1. BDSG chưa huấn luyện trọng số nào.** Tính đến 25/09/2026, BDSG chưa huấn luyện
bất kỳ trọng số mô hình nào. API tại `llm.bdsg.vn` tự khai `bdsg_la_trong_so_bdsg=false`
cho MỌI mô hình. Thứ đang chạy ở đó là **truy hồi** (`pg_trgm` + `tsvector`, **không phải
vector** — cổng LiteLLM hiện không có mô hình nhúng nào) đặt trước một mô hình của bên
thứ ba. Bộ dữ liệu này là **nguyên liệu để huấn luyện**, chưa phải sản phẩm của huấn luyện.

**1.2. Bộ này không phải là cơ sở dữ liệu khách hàng của BDSG.** 1.079.991 bản ghi trong
`map5d.khach_dn` là dữ liệu CRM và **không có bản ghi nào trong đó lọt vào đây**. Xem mục 5.

**1.3. Bộ này không có tầng hội thoại (SFT).** Toàn bộ vật liệu hỏi–đáp sẵn có của BDSG
đều là máy sinh qua cổng LiteLLM, và đã bị loại (mục 5.6). Vì vậy bộ phát hành lần này
**chỉ có tầng văn bản thô (pretrain)**. Ai cần SFT phải tự dựng, hoặc chờ BDSG dựng bằng
vật liệu do người viết.

---

## 2. Bộ này gồm gì

Ba lớp, đóng gói thành ba tệp JSONL. Mọi bản ghi ở cả ba lớp đều mang bốn trường xuất xứ
bắt buộc (`nguon`, `giay_phep`, `ngay_do`, `muc_tin_cay`) — chi tiết ở [luoc-do.md](luoc-do.md).

| Tệp | Lớp | Số bản ghi | Ký tự | Dung lượng |
|---|---|---|---|---|
| `tri-thuc-van-ban.jsonl` | Văn bản thô | **11.733** | **7.509.969** | **7,16 MB** |
| `ho-so-cong-ty.jsonl` | Hồ sơ DN có cấu trúc | **5.424** | chưa đo (xem 2.2) | chưa đo |
| `nang-luc.jsonl` | Tên năng lực / ngành nghề | **11.927** | **346.704** | chưa đo |
| **Cộng** | | **29.084** *(cộng tay)* | | |

> **Cảnh báo về cột "Dung lượng".** Con số 7,16 MB bằng đúng `7.509.969 / 1.048.576`,
> tức là nó được quy đổi từ **số ký tự**, coi 1 ký tự = 1 byte. Tiếng Việt có dấu mã hoá
> UTF-8 tốn 2–3 byte cho ký tự có dấu, nên **tệp thật trên đĩa sẽ nặng hơn con số này**.
> Dung lượng byte thật của tệp JSONL sau khi xuất **chưa đo** — `xuat.py` sẽ in ra khi chạy.

### 2.1. Lớp 1 — `tri-thuc-van-ban.jsonl`

Nguồn: CSDL `bdsg_chat`, bảng `doan_tri_thuc`. Đây là các đoạn văn bản đã được cắt đoạn
sẵn cho hệ truy hồi, nay dùng lại làm ngữ liệu tiền huấn luyện.

Bảng gốc có **17.788 đoạn**. Sau khi loại 2 nguồn máy sinh (mục 5.6) còn **11.733 đoạn**:

| `nguon` | Số đoạn | Dung lượng (quy đổi từ ký tự) |
|---|---|---|
| `ho-so-niem-yet` | 5.192 | 4,20 MB |
| `ho-so-dn` | 6.434 | 2,83 MB |
| `wiki-crm` | 107 | 0,13 MB |
| **Cộng** | **11.733** | **7,16 MB** |

> **Bẫy tên gọi, đọc kỹ:** nguồn tên `ho-so-dn` ở BẢNG NÀY (6.434 đoạn văn bản trong
> `bdsg_chat`) **không phải** là lớp 2 dưới đây (5.424 hồ sơ có cấu trúc trong
> `business.company_profiles`). Hai thứ khác CSDL, khác lược đồ, khác số lượng. Đặt tên
> tệp lớp 2 là `ho-so-cong-ty.jsonl` chính là để tránh nhầm chỗ này.

### 2.2. Lớp 2 — `ho-so-cong-ty.jsonl`

Nguồn: CSDL `postgres`, bảng `business.company_profiles` (+ `business.company_sector_links`).

Số đo trên bảng gốc:

| Chỉ số | Giá trị |
|---|---|
| Tổng số hồ sơ | 6.672 |
| `is_published` | 5.645 |
| Có `products` | 6.439 |
| Có `province_id` | 5.952 |
| Có `summary` | 6.608 |
| Có ngành (`company_sector_links`) | 6.666 |
| **ĐỦ CẢ BA: `is_published` ∧ có ngành ∧ có sản phẩm** | **5.424** |

**5.424 là con số duy nhất được phép dùng** khi nói "doanh nghiệp theo ngành nghề, tỉnh,
sản phẩm dịch vụ". Bốn con số kia (6.672 / 5.645 / 6.439 / 6.666) là số đo từng điều kiện
riêng lẻ và **không được cộng, trừ hay trích dẫn thay cho 5.424**.

> **CHƯA LÀM, và nó chặn lần chạy đầu tiên.** Bảng `company_sector_links` chỉ giữ **số
> hiệu ngành** (khoá ngoại), không giữ tên ngành. Bảng danh mục chứa **tên** thì chưa đối
> chiếu được lược đồ, nên `xuat.py` chưa nối sang bảng ấy — và vì thế nó **dừng hẳn** thay
> vì ghi ra một tệp trông hợp lệ nhưng ghi *"Ngành: 12; 47"*. Phải khai tên bảng/tên cột
> danh mục ngành trước khi xuất được lớp 2. Xem [luoc-do.md](luoc-do.md) mục 4.2.

Số ký tự đã đo trên bảng gốc: `summary` **1.941.353** + `products` **322.477** = 2.263.830
ký tự — nhưng phép đo ấy chạy **trên 5.645 dòng `is_published`**, không phải trên 5.424
dòng thực xuất. Vì 5.424 ⊂ 5.645 nên số ký tự của tệp xuất sẽ **nhỏ hơn hoặc bằng**
2.263.830; **giá trị chính xác chưa đo.** `xuat.py` in ra khi chạy.

### 2.3. Lớp 3 — `nang-luc.jsonl`

Nguồn: CSDL `postgres`, bảng `business.capabilities`. **11.927 dòng**, **346.704 ký tự**
ở hai cột tên (`name` + `name_en`).

Cột `description` của bảng này **bị loại** — lý do ở mục 6.2.

> **346.704 là số ký tự của `name` và `name_en` CỘNG LẠI.** Phần tiếng Anh chiếm bao nhiêu
> trong đó **chưa đo**. Đừng trích con số này như thể nó là khối lượng tiếng Việt, cũng
> đừng trích như thể nó là khối lượng tiếng Anh.

---

## 3. Ngôn ngữ: tiếng Việt là chính, tiếng Anh là phụ

Phạm vi ngôn ngữ của dự án, chốt ngày 26/09/2026, là **đúng hai**: tiếng Việt là chính,
tiếng Anh là phụ. Không có ngôn ngữ thứ ba, không trong ngữ liệu và không trong lược đồ.

Điều đó áp vào bộ dữ liệu này như sau, và có chỗ phải nói thẳng là *chưa đo*:

| Ngôn ngữ | Thứ tự | Có trong bộ dữ liệu này không |
|---|---|---|
| Tiếng Việt | 1 | **Có** — là toàn bộ lớp 1, phần lớn lớp 2 và cột `name` của lớp 3. |
| Tiếng Anh | 2 | **Có, nhưng ít và chưa đo riêng** — chỉ nằm ở cột `name_en` (lớp 3). Khối lượng riêng phần tiếng Anh: **chưa đo**. |

Dấu vết đo được của thứ tự ấy: mỗi bản ghi JSONL mang trường `ngon_ngu`
(`vi` | `en` | `vi+en`), để sau này ai cũng **đếm được** tỉ lệ hai thứ tiếng thay vì đoán.

Tỉ lệ trộn hai ngôn ngữ khi tiền huấn luyện: **chưa quyết, chưa đo.**

> **Vì sao thu phạm vi lại.** Bản trước của thẻ này liệt kê ba ngôn ngữ, trong đó ngôn ngữ
> thứ ba có đúng một ô ghi *"chưa chọn nguồn, chưa đo"* — tức là một lời hứa không kèm số
> đo nào. Theo đúng nguyên tắc ở đầu thẻ (*không có số nào được viết ra mà chưa đo*), cách
> xử đúng không phải là để ô trống chờ mãi, mà là **bỏ hẳn khỏi phạm vi**. Một phạm vi hẹp
> mà đo được thì kiểm chứng được; một phạm vi rộng mà mọi ô đều ghi "chưa đo" thì không.

---

## 4. Xuất xứ và vì sao từng lớp được phép phát hành

| Lớp | Xuất xứ | Vì sao phát hành được |
|---|---|---|
| Lớp 1 · `ho-so-niem-yet` | Hồ sơ doanh nghiệp niêm yết do BDSG tổng hợp từ công bố thông tin bắt buộc của DN niêm yết | Công bố thông tin của DN niêm yết là **thông tin bắt buộc công khai** theo luật chứng khoán Việt Nam. Phần biên tập, cắt đoạn, chuẩn hoá là công sức của BDSG. |
| Lớp 1 · `ho-so-dn` | Hồ sơ doanh nghiệp do BDSG biên soạn trong hệ thống của mình | BDSG là tác giả. Không có ràng buộc bên thứ ba. |
| Lớp 1 · `wiki-crm` | Tài liệu nội bộ về quy trình nghiệp vụ, do người của BDSG viết trong wiki CRM | BDSG là tác giả. 107 đoạn đã rà để chắc không chứa cấu hình hệ thống hay bí mật vận hành. |
| Lớp 2 · `ho-so-cong-ty` | `business.company_profiles` — hồ sơ năng lực DN, phần `is_published` là phần DN/BDSG đã chủ động cho hiển thị công khai trên `bdsg.vn/business` | Chỉ xuất bản ghi `is_published = true`. Cờ ấy chính là hành vi đồng ý công khai. Bản ghi chưa xuất bản **không ra khỏi hệ thống**. |
| Lớp 3 · `nang-luc` | `business.capabilities` — danh mục ngành nghề/năng lực do BDSG chuẩn hoá | Danh mục phân loại do BDSG tự dựng. Chỉ lấy **tên**, không lấy `description` (mục 6.2). |

---

## 5. NHỮNG GÌ CỐ Ý KHÔNG CÓ

Mục này quan trọng hơn mục 2. Đây là danh sách những nguồn BDSG **có trong tay, đo được,
và quyết định không phát hành** — kèm lý do để người đọc kiểm lại lập luận.

### 5.1. Dữ liệu khách hàng CRM — 1.079.991 bản ghi — LOẠI

`map5d.khach_dn`, **1.079.991 bản ghi**. **100%** số đó mang `nguon = 'crm_geocode_dot2'`,
tức là **dữ liệu khách hàng trong CRM của BDSG**. Phát hành công khai dữ liệu khách hàng
là điều không bàn.

Một lưu ý kỹ thuật để dập luôn ý định "lọc bớt rồi phát hành": bảng này chỉ có các cột
`id`, `ten`, `do_chinh_xac`, `ma_xa`, `ma_tinh`, `geom`, `nguon`, `ngay_cap_nhat`.
**Không có cột ngành nghề. Không có cột sản phẩm.** Nghĩa là ngay cả khi bỏ qua vấn đề
quyền riêng tư, bảng này **cũng không trả lời được** câu hỏi "doanh nghiệp theo ngành nghề,
sản phẩm dịch vụ". Con số 1,08 triệu **không được phép** xuất hiện trong bất kỳ mô tả nào
về quy mô bộ dữ liệu mở này.

### 5.2. Kho tri thức nội bộ — 118 tệp — LOẠI

Thư mục `kho-tri-thuc`, **118 tệp**. Đã kiểm **118/118**: mỗi tệp đều mang dòng cấp phép
bên thứ ba *"Licensed to RAI Holdings"*. Đây là tài liệu cấp phép cho một pháp nhân khác;
BDSG không có quyền phát hành lại. Tỉ lệ dính là **118/118 = 100%**, nên không có cách nào
lọc ra phần sạch.

### 5.3. OCOP — 1.727 sản phẩm — LOẠI

**1.727 sản phẩm** OCOP. Nội dung là **văn quảng cáo do người bán viết**, và trường `url`
trỏ về `buudien.vn`. Hai vấn đề: (a) quyền tác giả thuộc người bán / sàn, không thuộc BDSG;
(b) văn quảng cáo là ngữ liệu xấu cho tiền huấn luyện — nó dạy mô hình giọng chào hàng
chứ không dạy sự thật.

### 5.4. Tin tức — LOẠI

Nguồn `tin-tuc`: bản quyền thuộc các toà soạn. Số lượng đoạn **chưa đo** vì đã loại từ
vòng lọc nguồn, trước khi đếm.

### 5.5. Bài đăng người dùng — LOẠI

Nguồn `bai-dang`: nội dung do người dùng đăng trên nền tảng BDSG. Người dùng đăng bài lên
một nền tảng **không có nghĩa là họ đồng ý cho bài của mình đi huấn luyện mô hình rồi phát
hành công khai**. Số lượng đoạn **chưa đo**, lý do như trên.

### 5.6. Hai nguồn máy sinh qua LiteLLM — 6.055 đoạn — LOẠI

| Nguồn | Số đoạn |
|---|---|
| `nao-agent` | 116 |
| `bai-dang-bds` | 5.939 |
| **Cộng** | **6.055** |

Kiểm được: 17.788 (toàn bảng) − 6.055 = **11.733** (phần phát hành). Hai lý do:

1. **Điều khoản nhà cung cấp.** Cả hai nguồn là đầu ra của mô hình bên thứ ba qua cổng
   LiteLLM. Điều khoản của các nhà cung cấp mô hình thường **cấm dùng đầu ra để huấn luyện
   mô hình cạnh tranh**. Một bộ dữ liệu mở đem đi huấn luyện mô hình mở rơi thẳng vào chỗ cấm ấy.
2. **Bí mật thương mại của chính BDSG.** 3.601 "não agent" là **cấu hình thương mại** của
   BDSG. Phát hành chúng là tự đem sản phẩm của mình ra cho không.

Ngoài ra, ngữ liệu máy sinh còn làm hỏng phép đánh giá: huấn luyện trên đầu ra của mô hình
khác rồi đo xem mô hình mình "biết" gì thì thứ đo được là trí nhớ về mô hình kia.

### 5.7. Cột `capabilities.description` — LOẠI

Xem mục 6.2.

---

## 6. Giới hạn đã biết

### 6.1. Rác cào web: 2,3%

**110 đoạn** trong lớp 1 còn dính rác cào web (mảnh menu trang web, CSS, JS, URL ngoài).
Khối lượng: **0,17 MB trên 7,16 MB = 2,3%**.

> Lấy hai con số đã làm tròn ở trên chia cho nhau thì ra 2,4%, không phải 2,3%. Chênh lệch
> ấy là do **0,17 MB tự nó đã được làm tròn**; 2,3% mới là tỉ lệ đo trên số ký tự chưa làm
> tròn. Ghi cả hai ra đây để người đọc không phải ngồi ngờ vực một trong hai con số — đúng
> nguyên tắc của thẻ này: số nào đã đo thì giữ nguyên, chỗ nào nhìn có vẻ vênh thì giải thích.

Rác tập trung ở một nguồn: **110/5.192 = 2,1%** số đoạn của `ho-so-niem-yet`. Hai nguồn
kia không có đoạn nào dính trong phép đo này.

Kết luận của phép đo: **lọc được, không phải bỏ nguồn.** 2,1% là tỉ lệ đủ thấp để làm sạch
bằng luật, chứ chưa tới mức phải nghi ngờ cả nguồn. `xuat.py` gắn cờ `co_rac_web` cho từng
bản ghi để người dùng hạ nguồn tự quyết giữ hay bỏ, thay vì BDSG quyết thay.

**Chưa làm:** bộ lọc rác tự động chưa được viết và chưa được đo độ chính xác. 110 đoạn kia
đang được **đánh dấu**, chưa được **làm sạch**.

### 6.2. `capabilities.description`: 696.890 ký tự nhưng chỉ 58 giá trị khác nhau

Cột `description` của `business.capabilities` có **696.890 ký tự** trên **11.927 dòng** —
nhìn qua thì đây là khối văn bản lớn thứ hai của cả bộ. Nhưng đếm giá trị phân biệt thì chỉ
có **58 giá trị khác nhau trên 11.927 dòng**.

Nghĩa là nó **không phải mô tả**, mà là **chuỗi xuất xứ do ETL lặp lại** — cùng một câu
được dán vào hàng nghìn dòng. Đưa vào tiền huấn luyện thì 696.890 ký tự ấy dạy mô hình
đúng 58 câu, lặp trung bình ~206 lần mỗi câu, và làm lệch phân bố token.

**Loại.** Chỉ lấy `name` + `name_en` (346.704 ký tự).

Bài học đo lường đáng ghi lại: **đếm ký tự không phải là đếm thông tin.** Nếu chỉ nhìn cột
"dung lượng" thì nguồn này trông béo gấp đôi phần được giữ.

### 6.3. Chia tập huấn luyện/kiểm tra/thẩm định: KHÔNG kèm theo bộ này

Phép chia đã đo là: huấn luyện **16.151** / kiểm tra **835** / thẩm định **802**
(cộng = 17.788). Nhưng **17.788 là toàn bộ bảng gốc, tức CÓ CHỨA 6.055 đoạn máy sinh đã bị loại.**

Vì vậy ba con số ấy **không áp dụng được** cho bộ phát hành 11.733 đoạn, và **không được
trích dẫn như thể chúng là phép chia của bộ này**. Phép chia lại trên 11.733 đoạn **chưa làm.**
Bộ phát hành lần này **không kèm chia tập**; người dùng hạ nguồn tự chia.

### 6.4. Những giới hạn khác, nói thẳng

- **Thiên lệch nguồn.** 5.192/11.733 đoạn (~44%) đến từ một nguồn duy nhất là DN niêm yết.
  Mô hình học từ đây sẽ nghiêng về ngôn ngữ báo cáo tài chính và công bố thông tin.
- **Thiên lệch địa lý.** `province_id` chỉ có ở 5.952/6.672 hồ sơ. Phân bố theo tỉnh của
  5.424 bản ghi thực xuất: **chưa đo.**
- **Thiên lệch thời gian.** Mọi số đo là ảnh chụp ngày 25/09/2026. Nguồn thay đổi theo thời
  gian; bộ này **không** có cơ chế cập nhật tự động.
- **Chưa có đối chứng chất lượng của con người.** Chưa có ai đọc mẫu ngẫu nhiên rồi chấm
  điểm. Tỉ lệ đoạn sai sự thật, đoạn trùng, đoạn cụt: **chưa đo.**
- **Chưa khử trùng lặp.** Số cặp đoạn trùng hoặc gần trùng trong 11.733 đoạn: **chưa đo.**

---

## 7. Kết quả quét dữ liệu cá nhân

Quét chạy trên lớp 1 (11.733 đoạn phát hành được), ngày **25/09/2026**. Quét được chạy lại
từ đầu, **không tin lời khai của bước xử lý trước đó**.

| Loại | Số khớp | Kết luận |
|---|---|---|
| Địa chỉ email | **0** | Sạch |
| Số điện thoại | **0** | Sạch |
| URL nội bộ | **0** | Sạch |
| "Mã số thuế" | **29** | Phần lớn là thông tin đăng ký công khai + vài dương tính giả — xem 7.2 |
| "Địa chỉ IP" | **5** | **Toàn bộ là dương tính giả** — xem 7.3 |

### 7.1. Bước gỡ dữ liệu cá nhân ĐÃ chạy thật — có bằng chứng

Trong văn bản còn nguyên các nhãn `[EMAIL]` và `[SĐT]`. Đây là bằng chứng **dương** rằng
bước thay thế đã chạy: nếu bước ấy chưa từng chạy thì không thể có nhãn, và nếu nó chạy
nửa vời thì sẽ còn sót email thật bên cạnh nhãn. Kết quả 0 email + có nhãn = bước gỡ đã
chạy trọn.

Đây là cách kiểm đúng: **không hỏi "có email không" rồi yên tâm khi được trả lời không có,
mà hỏi "dấu vết của việc gỡ có còn không".** Một phép quét trả về 0 trên một tệp rỗng cũng
trả về 0.

### 7.2. 29 khớp "mã số thuế"

Phần lớn là **mã số thuế và số đăng ký kinh doanh của doanh nghiệp**. Ở Việt Nam đây là
**thông tin đăng ký công khai** — tra được trên cổng thông tin quốc gia về đăng ký doanh
nghiệp. Chúng là định danh **của pháp nhân**, không phải dữ liệu cá nhân của thể nhân.
Giữ lại, và ghi rõ ở đây để người đọc tự quyết.

Phần còn lại là **dương tính giả**, gồm hai kiểu:

- **Tên lớp CSS** — rác cào web (mục 6.1) để lại các chuỗi kiểu `col-12-3849` mà bộ dò
  chuỗi số dài nhận nhầm.
- **Trường `rev` trong JSON** — các mẩu chuỗi hex/UUID kiểu `3-a1f09c7e…`. Bộ dò chỉ tìm
  "dãy số dài" sẽ cắn phải phần số trong đó.

Rút ra cho thiết kế bộ dò: một bộ dò mã số thuế **bắt buộc** phải kiểm định dạng (đúng 10
hoặc 13 chữ số, 13 thì có dấu gạch nối) chứ không được bắt "dãy chữ số dài".

### 7.3. 5 khớp "địa chỉ IP" — toàn bộ là dương tính giả

**Cả 5 khớp đều là số tiền viết kiểu Việt Nam**, ví dụ `120.086.720.000 đồng`.

Người Việt dùng **dấu chấm làm dấu phân cách hàng nghìn**, nên một số tiền lớn nhìn y hệt
một địa chỉ IPv4 với bốn nhóm số ngăn bằng dấu chấm. Đây là **cái bẫy riêng của tiếng Việt**
mà một bộ dò viết cho tiếng Anh sẽ không lường trước.

Cách phân biệt, và `xuat.py` cài đúng cách này:

- IPv4 hợp lệ có **mỗi nhóm ≤ 255**. `120.086.720.000` có nhóm `720` → không phải IP.
- IPv4 **không viết số 0 ở đầu nhóm**. `086` và `000` có số 0 đứng đầu → không phải IP.
  (`000` bằng 0 nên **không** vi phạm luật ≤ 255; nó bị luật số 0 đứng đầu loại. Ghi rõ vì
  xếp nhầm một ca sang luật khác sẽ dẫn tới sửa nhầm luật khi bộ dò cần chỉnh.)
- Số tiền Việt Nam thường đi kèm `đồng` / `VNĐ` / `₫` ngay sau.

Ba luật ấy loại sạch 5/5 khớp mà không cần bỏ qua lớp kiểm tra IP thật.

### 7.4. Hai lớp còn lại chưa có số quét riêng

Số quét ở bảng trên là **của lớp 1**. Kết quả quét riêng cho lớp 2 (`ho-so-cong-ty`) và
lớp 3 (`nang-luc`): **chưa đo**. Vì vậy `xuat.py` **chạy quét trên cả ba lớp ngay trước khi
ghi**, và **từ chối ghi** nếu có khớp thật vượt ngưỡng (mục 8).

---

## 8. Cách bộ dữ liệu được tạo lại

```bash
export BDSG_DSN_CHAT='postgresql://.../bdsg_chat'      # KHÔNG có giá trị mặc định
export BDSG_DSN_BUSINESS='postgresql://.../postgres'   # KHÔNG có giá trị mặc định
export BDSG_THU_MUC_XUAT='./xuat'

python3 bo-du-lieu/xuat.py
```

`xuat.py` được viết theo nguyên tắc **hỏng-thì-đóng** (fail-closed), vì họ lỗi nguy hiểm
nhất trong pipeline dữ liệu là *hỏng mà không báo*:

1. **Không có giá trị mặc định nào chứa thông tin máy chủ.** Thiếu biến môi trường thì
   chương trình dừng, chứ không lặng lẽ nối vào một CSDL đoán được.
2. **Danh sách trắng nguồn.** Chỉ 3 giá trị `nguon` được phép ở lớp 1. Gặp `nguon` lạ →
   **dừng toàn bộ**, không bỏ qua im lặng. Lý do: nguồn mới xuất hiện trong bảng là sự kiện
   cần người xem xét, không phải trường hợp cần xử lý tự động.
3. **Quét dữ liệu cá nhân chạy trước khi ghi**, trên bản ghi đã dựng xong. Vượt ngưỡng →
   **không ghi tệp nào cả**, kể cả các lớp đã sạch.
4. **In báo cáo số đo cuối cùng**: số bản ghi, số ký tự, số byte thật của từng tệp, để
   người chạy đối chiếu với thẻ dữ liệu này.

---

## 9. Dùng bộ này để làm gì, và không nên dùng để làm gì

**Hợp lý:**

- Tiền huấn luyện mô hình ngôn ngữ nhỏ về ngữ cảnh doanh nghiệp Việt Nam.
- Huấn luyện bộ từ vựng (BPE mức byte) có chỗ cho tiếng Việt có dấu.
- Đo đạc, đối chứng, phản biện phương pháp của BDSG.

**Không nên:**

- **Tra cứu sự thật về một doanh nghiệp cụ thể.** Ảnh chụp 25/09/2026, không cập nhật.
- **Suy ra danh sách khách hàng của BDSG.** Không có dữ liệu khách hàng ở đây (mục 5.1).
- **Dùng thay cho nguồn chính thống** về đăng ký doanh nghiệp hoặc công bố thông tin.
- **Kết luận về chất lượng mô hình BDSG.** Bộ này là nguyên liệu, không phải mô hình.

---

## 10. Trạng thái mô hình và đường cơ sở đánh giá

Nhắc lại từ mục 1.1: **chưa có trọng số BDSG nào.** Đường cơ sở dưới đây là số đo của
**hệ truy hồi + mô hình bên thứ ba**, không phải của mô hình huấn luyện từ bộ dữ liệu này.
Ghi ở đây để sau này có mốc so sánh.

Đợt đánh giá **M3, ngày 22/09/2026**, bộ **227 câu**:

| Nhóm câu | Số câu | Điểm |
|---|---|---|
| Nghiệp vụ **trong** kho | 111 | **0,636** |
| Nghiệp vụ **ngoài** kho | 31 | **0,539** |
| Câu bẫy chống bịa | 60 | **0,953** |
| Tiếng Việt tổng quát | 25 | **0,908** |
| **Cộng** | **227** | |

Lợi ích của truy hồi: **+0,097**.

Chênh lệch trong-kho/ngoài-kho = 0,636 − 0,539 = 0,097, đúng bằng phần lợi ích truy hồi
đo được. Đây là số đo của hệ hiện tại, **không phải lời hứa** về mô hình sắp huấn luyện.

Hạ tầng liên quan, đo ngày 25/09/2026: `llm.bdsg.vn` đã sống (`/` → 200, `/v1/models` → 200,
`/api/suc-khoe` → 200), chứng chỉ Let's Encrypt cấp lúc 21:27. `ai.bdsg.vn` đã NXDOMAIN
(bản ghi DNS gỡ cùng ngày). API tương thích OpenAI; mã mô hình công khai: `openbiz-vn-chat` và
`openbiz-vn-reasoner` (đổi tên 25/09/2026; hai tên cũ `bdsg-ai-v1`,
`bdsg-ai-v1-suy-luan` vẫn là bí danh vĩnh viễn).

---

## 11. Giấy phép và cách trích dẫn

Bộ dữ liệu này phát hành theo **Creative Commons Attribution 4.0 International (CC-BY-4.0)**
— https://creativecommons.org/licenses/by/4.0/

Bạn được **dùng, sửa, phân phối lại, dùng cho mục đích thương mại**, với một điều kiện duy
nhất: **ghi công**.

Giấy phép này áp cho **phần dữ liệu do BDSG tạo ra và biên tập** (ba lớp ở mục 2). Nó
**không** cấp quyền nào đối với các nguồn đã bị loại ở mục 5 — những nguồn ấy không nằm
trong bộ, nên cũng không nằm trong giấy phép. Xuất xứ và ràng buộc của từng nguồn, kể cả
nguồn bị loại, xem [GIAY-PHEP-NGUON.md](GIAY-PHEP-NGUON.md).

### Cách trích dẫn

```
BDSG (2026). Bo du lieu mo Open BDSG.
Phien ban 2026-09-25. Giay phep CC-BY-4.0.
https://github.com/BDSG-VN/open-bdsg
```

BibTeX:

```bibtex
@misc{openbdsgos_bodulieu_2026,
  title        = {Bo du lieu mo Open BDSG},
  author       = {{BDSG}},
  year         = {2026},
  version      = {2026-09-25},
  license      = {CC-BY-4.0},
  howpublished = {\url{https://github.com/BDSG-VN/open-bdsg}}
}
```

> Đường dẫn kho mã ở trên là **dự kiến theo quyết định của chủ dự án** (repo GitHub công
> khai tên "Open BDSG"). Kho đã tồn tại công khai tại địa chỉ đó hay chưa:
> **chưa kiểm tại thời điểm viết tệp này.** Sửa lại đường dẫn khi kho lên thật.

---

## 12. Liên hệ và trách nhiệm

Bộ dữ liệu do **BDSG** phát hành. Người chịu trách nhiệm chuyên môn: **Kiến trúc sư
trưởng tư vấn, BDSG** — liên hệ qua kho mã công khai.

> Thẻ dữ liệu nghiêm túc thường nêu tên người chịu trách nhiệm, và ở đây cố ý nêu
> VAI TRÒ thay vì tên riêng: đây là kho công khai, và một cái tên đăng lên thì máy
> thu thập giữ lại vĩnh viễn. Chủ dự án muốn đứng tên thật thì thay dòng trên —
> đó là quyết định của người có tên, không phải mặc định của kho.

Nếu bạn phát hiện trong bộ này có **dữ liệu cá nhân còn sót**, **nội dung vi phạm bản quyền
bên thứ ba**, hoặc **thông tin sai về doanh nghiệp của bạn**: xin báo để gỡ. Hai phép quét ở
mục 7 là phép quét bằng luật, và luật thì có chỗ không phủ tới — mục 7.2 và 7.3 đã cho thấy
bộ dò tự nó nhầm cả hai chiều.
