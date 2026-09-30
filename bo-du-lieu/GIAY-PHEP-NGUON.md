# Xuất xứ và giấy phép của từng nguồn dữ liệu

Bảng xuất xứ của dự án **Open BDSG**. Ngày đo: **25/09/2026**.

Tệp này liệt kê **cả nguồn được phát hành lẫn nguồn bị loại**. Nguồn bị loại có mặt ở đây
là có chủ ý: người đọc cần **kiểm lại được lập luận loại trừ**, chứ không phải chỉ được
thông báo kết quả. Một danh sách chỉ liệt kê thứ đã lấy thì không ai kiểm được là còn thứ
gì lẽ ra phải lấy mà không lấy, hoặc lẽ ra phải bỏ mà vẫn lấy.

- Thẻ dữ liệu: [README.md](README.md)
- Lược đồ JSONL: [luoc-do.md](luoc-do.md)
- Script xuất: [xuat.py](xuat.py)

---

## 1. Bảng tổng — một dòng một nguồn

| # | Nguồn | Nơi lưu | Khối lượng đã đo | Bản quyền thuộc về | Ràng buộc | Quyết định |
|---|---|---|---|---|---|---|
| 1 | `ho-so-niem-yet` | `bdsg_chat.doan_tri_thuc` | 5.192 đoạn · 4,20 MB | BDSG (phần biên tập) trên nền công bố thông tin bắt buộc | Không | **PHÁT HÀNH** · CC-BY-4.0 |
| 2 | `ho-so-dn` | `bdsg_chat.doan_tri_thuc` | 6.434 đoạn · 2,83 MB | BDSG | Không | **PHÁT HÀNH** · CC-BY-4.0 |
| 3 | `wiki-crm` | `bdsg_chat.doan_tri_thuc` | 107 đoạn · 0,13 MB | BDSG | Không | **PHÁT HÀNH** · CC-BY-4.0 |
| 4 | `company_profiles` | `postgres.business` | 5.424 hồ sơ đủ ba điều kiện | BDSG + DN đã đồng ý công khai | Chỉ bản ghi `is_published` | **PHÁT HÀNH** · CC-BY-4.0 |
| 5 | `capabilities` (cột tên) | `postgres.business` | 11.927 dòng · 346.704 ký tự | BDSG | Chỉ `name` + `name_en` | **PHÁT HÀNH** · CC-BY-4.0 |
| 6 | `capabilities.description` | `postgres.business` | 696.890 ký tự · **58 giá trị khác nhau** | — | — | **LOẠI** · chuỗi ETL lặp |
| 7 | `map5d.khach_dn` | Supabase `map5d` | **1.079.991 bản ghi** | BDSG (dữ liệu khách hàng) | Dữ liệu CRM | **LOẠI** · quyền riêng tư |
| 8 | `kho-tri-thuc` | Tệp trên máy chủ | **118 tệp** (118/118 dính) | **RAI Holdings** | *"Licensed to RAI Holdings"* | **LOẠI** · giấy phép bên thứ ba |
| 9 | `ocop` | Supabase `ocop` | **1.727 sản phẩm** | Người bán / sàn `buudien.vn` | Bản quyền bên thứ ba | **LOẠI** · bản quyền + chất lượng |
| 10 | `tin-tuc` | Hệ tin tức BDSG | Số đoạn **chưa đo** | Các toà soạn | Bản quyền báo chí | **LOẠI** · bản quyền |
| 11 | `bai-dang` | Nền tảng BDSG | Số đoạn **chưa đo** | Người dùng đăng bài | Chưa có đồng ý cho huấn luyện | **LOẠI** · chưa có đồng ý |
| 12 | `nao-agent` | `bdsg_chat.doan_tri_thuc` | **116 đoạn** | Máy sinh qua LiteLLM | Điều khoản nhà cung cấp + bí mật thương mại | **LOẠI** · máy sinh |
| 13 | `bai-dang-bds` | `bdsg_chat.doan_tri_thuc` | **5.939 đoạn** | Máy sinh qua LiteLLM | Điều khoản nhà cung cấp | **LOẠI** · máy sinh |

> **Bảng này chỉ có 13 dòng, và đó là toàn bộ nguồn DỮ LIỆU của dự án.** Bản trước có thêm
> hai dòng cho mã nguồn và bộ dữ liệu của một dự án ngoài. Cả hai dòng đã bị gỡ ngày
> 26/09/2026 vì hai lý do khác nhau, nói rõ cả hai:
>
> - **Dòng mã nguồn** không còn đúng: kiến trúc và bộ huấn luyện của kho này do BDSG viết
>   độc lập, dựng từ kỹ thuật đã công bố trong bài báo (xem mục 4). Không có mã nào được
>   dẫn xuất, nên không có giấy phép thượng nguồn nào để ghi.
> - **Dòng bộ dữ liệu** không thuộc bảng này ngay từ đầu: nó chưa bao giờ được trộn vào bộ
>   này, nên nó không phải một nguồn đã dùng mà là một nguồn đã không dùng — và bảng này
>   liệt kê nguồn BDSG **có trong tay** và đã quyết định giữ hay loại, không liệt kê mọi bộ
>   dữ liệu tồn tại trên đời.

Kiểm được bằng phép cộng: **5.192 + 6.434 + 107 = 11.733** (phát hành) và
**11.733 + 116 + 5.939 = 17.788** (toàn bảng `doan_tri_thuc`). Không còn chỗ cho nguồn nào
khác trong bảng ấy — nên `tin-tuc` và `bai-dang` nằm ở nguồn khác, và `xuat.py` không bao
giờ truy vấn tới chúng.

---

## 2. Nguồn ĐƯỢC phát hành — lập luận từng nguồn

### 2.1. `ho-so-niem-yet` — 5.192 đoạn · 4,20 MB

**Xuất xứ.** Hồ sơ doanh nghiệp niêm yết, BDSG tổng hợp từ công bố thông tin của các doanh
nghiệp niêm yết trên thị trường chứng khoán Việt Nam, rồi biên tập và cắt đoạn.

**Vì sao được phát hành.** Công bố thông tin của doanh nghiệp niêm yết là **thông tin bắt
buộc công khai** theo pháp luật chứng khoán Việt Nam — đó là nghĩa vụ của DN với công
chúng đầu tư, không phải tài sản giữ kín. Phần BDSG bỏ công vào (tổng hợp, chuẩn hoá, cắt
đoạn, gắn nguồn) là **sản phẩm biên tập của BDSG**, và chính phần ấy được cấp CC-BY-4.0.

**Điều cần nói thẳng.** Nguồn này chiếm **5.192/11.733 ≈ 44%** lớp 1, nên nó **kéo lệch
giọng văn** của toàn bộ ngữ liệu về phía ngôn ngữ báo cáo tài chính. Đây cũng là nguồn duy
nhất có rác cào web: **110/5.192 = 2,1%** số đoạn. Xem README mục 6.1 và 6.4.

### 2.2. `ho-so-dn` — 6.434 đoạn · 2,83 MB

**Xuất xứ.** Hồ sơ doanh nghiệp do BDSG biên soạn trong hệ thống của mình.

**Vì sao được phát hành.** BDSG là tác giả. Không có bên thứ ba nào giữ quyền.

**Bẫy tên gọi.** Nguồn này là **6.434 đoạn văn bản** trong `bdsg_chat.doan_tri_thuc`.
Nó **không phải** 5.424 hồ sơ có cấu trúc ở dòng 4 (`business.company_profiles`). Hai thứ
trùng nghĩa tiếng Việt nhưng khác CSDL, khác lược đồ, khác số lượng. Trong bộ xuất ra,
chúng ở hai tệp khác nhau (`tri-thuc-van-ban.jsonl` và `ho-so-cong-ty.jsonl`).

### 2.3. `wiki-crm` — 107 đoạn · 0,13 MB

**Xuất xứ.** Tài liệu quy trình nghiệp vụ do người của BDSG viết trong wiki của hệ CRM nội bộ.

**Vì sao được phát hành.** BDSG là tác giả. 107 đoạn là lượng nhỏ, đã rà để chắc không lẫn
cấu hình hệ thống, thông tin máy chủ hay bí mật vận hành.

**Điều cần nói thẳng.** "Đã rà" ở đây nghĩa là đã quét bằng luật (README mục 7), **không**
có nghĩa là đã có người đọc hết 107 đoạn và ký xác nhận. Việc đọc tay ấy: **chưa làm.**

### 2.4. `business.company_profiles` — 5.424 hồ sơ

**Xuất xứ.** Hồ sơ năng lực doanh nghiệp trong hệ `business` của BDSG, phần hiển thị công
khai trên danh bạ `bdsg.vn/business`.

**Vì sao được phát hành.** Chỉ xuất bản ghi có **`is_published = true`**. Cờ ấy chính là
hành vi cho phép hiển thị công khai đã có sẵn trong hệ thống — bộ dữ liệu này không tạo ra
một mức công khai mới, nó chỉ đóng gói lại thứ đã công khai. Bản ghi **chưa xuất bản không
ra khỏi hệ thống** (6.672 − 5.645 = 1.027 hồ sơ chưa xuất bản, không có mặt trong bộ).

**Bộ lọc chính xác là ba điều kiện:** `is_published` ∧ có ngành ∧ có sản phẩm = **5.424**.
Đây là con số duy nhất được phép dùng khi nói "doanh nghiệp theo ngành nghề, tỉnh, sản phẩm
dịch vụ". **Tỉnh không nằm trong bộ lọc** — một phần trong 5.424 bản ghi có `ma_tinh = null`,
phần ấy bao nhiêu thì **chưa đo**.

### 2.5. `business.capabilities`, chỉ hai cột tên — 11.927 dòng · 346.704 ký tự

**Xuất xứ.** Danh mục ngành nghề/năng lực do BDSG tự chuẩn hoá.

**Vì sao được phát hành.** Danh mục phân loại là công sức biên soạn của BDSG. Chỉ lấy
`name` và `name_en`; cột `description` bị loại (mục 3.1).

**Vai trò riêng của nguồn này.** Đây là **vật liệu song ngữ duy nhất** trong cả bộ, nên nó
là chỗ duy nhất trong bộ dữ liệu thể hiện được thứ tự **tiếng Việt (1) → tiếng Anh (2)**.
Khối lượng riêng phần tiếng Anh trong 346.704 ký tự: **chưa đo**.

---

## 3. Nguồn BỊ LOẠI — lập luận từng nguồn

### 3.1. `capabilities.description` — 696.890 ký tự — LOẠI

**Số đo.** 696.890 ký tự trên 11.927 dòng, nhưng chỉ **58 giá trị khác nhau**.

**Lập luận.** Trung bình mỗi giá trị lặp ~206 lần. Đây không phải mô tả mà là **chuỗi xuất
xứ do ETL dán vào**. Đưa vào tiền huấn luyện thì 696.890 ký tự ấy dạy mô hình đúng 58 câu
và làm lệch phân bố token.

**Cách người đọc tự kiểm lại lập luận này:**

```sql
SELECT COUNT(*) AS so_dong,
       COUNT(DISTINCT description) AS so_gia_tri_khac_nhau,
       SUM(length(description)) AS tong_ky_tu
FROM business.capabilities;
-- Do ngay 25/09/2026: 11927 | 58 | 696890
```

**Bài học đo lường.** Đếm ký tự không phải đếm thông tin. Nhìn cột "dung lượng" thì nguồn
này trông béo gấp đôi phần được giữ lại.

### 3.2. `map5d.khach_dn` — 1.079.991 bản ghi — LOẠI

**Số đo.** 1.079.991 bản ghi. **100%** mang `nguon = 'crm_geocode_dot2'`.

**Lập luận chính.** `crm_geocode_dot2` nghĩa là dữ liệu đến từ **CRM khách hàng của BDSG**.
Phát hành công khai dữ liệu khách hàng là điều không bàn — không có ngưỡng ẩn danh nào,
không có phương án "lọc bớt rồi phát hành".

**Lập luận phụ, để dập luôn ý định lọc bớt.** Bảng chỉ có các cột `id`, `ten`,
`do_chinh_xac`, `ma_xa`, `ma_tinh`, `geom`, `nguon`, `ngay_cap_nhat`. **Không có cột ngành
nghề. Không có cột sản phẩm.** Nên ngay cả khi bỏ qua quyền riêng tư, bảng này **cũng không
trả lời được** câu hỏi "doanh nghiệp theo ngành nghề, sản phẩm dịch vụ" — tức là nó không
đem lại thứ người ta tưởng nó đem lại.

**Hệ quả với cách nói.** Con số **1,08 triệu không được phép** xuất hiện trong bất kỳ mô tả
nào về quy mô bộ dữ liệu mở này. Quy mô thật của bộ là **29.084 bản ghi** trên ba lớp.

### 3.3. `kho-tri-thuc` — 118 tệp — LOẠI

**Số đo.** 118 tệp, kiểm **118/118**: mỗi tệp mang dòng cấp phép *"Licensed to RAI Holdings"*.

**Lập luận.** Đây là tài liệu được cấp phép cho **một pháp nhân khác**. BDSG là bên **nhận**
cấp phép sử dụng, không phải bên **giữ** quyền, nên không có quyền cấp phép lại cho công
chúng theo CC-BY-4.0.

**Tỉ lệ dính là 118/118 = 100%**, nên không tồn tại phương án "lọc ra phần sạch". Đây là
trường hợp hiếm mà phép đo cho ra kết luận dứt khoát: không phải cân nhắc, chỉ là loại.

### 3.4. `ocop` — 1.727 sản phẩm — LOẠI

**Số đo.** 1.727 sản phẩm. Trường `url` trỏ về `buudien.vn`.

**Hai lý do độc lập, mỗi lý do đủ để loại:**

1. **Bản quyền.** Nội dung là văn quảng cáo do **người bán** viết, đăng trên sàn của bên
   thứ ba. Quyền không thuộc BDSG.
2. **Chất lượng ngữ liệu.** Văn quảng cáo dạy mô hình **giọng chào hàng**, không dạy sự
   thật. Với một mô hình có mục tiêu trả lời đúng về doanh nghiệp, đây là ngữ liệu làm hại
   chứ không phải ngữ liệu thiếu.

Lý do 2 đáng ghi lại riêng: kể cả khi giấy phép sạch, vẫn có ngữ liệu không nên đưa vào.

### 3.5. `tin-tuc` — LOẠI

**Lập luận.** Bản quyền thuộc các toà soạn. BDSG thu thập để phục vụ truy hồi nội bộ, việc
ấy khác hẳn việc phát hành lại công khai kèm giấy phép cho phép dùng thương mại.

**Số lượng đoạn: chưa đo.** Nguồn này bị loại ngay ở vòng lọc nguồn, **trước khi đếm**.
Nói thẳng là chưa đo, thay vì đưa ra một con số ước lượng nghe cho đủ bảng.

### 3.6. `bai-dang` — LOẠI

**Lập luận.** Nội dung do người dùng đăng trên nền tảng của BDSG. Người dùng đăng bài lên
một nền tảng **không có nghĩa là họ đồng ý** cho bài của mình đi huấn luyện mô hình rồi
được phát hành lại công khai theo giấy phép cho dùng thương mại. Điều khoản sử dụng của
nền tảng hiện **chưa có** điều khoản đồng ý ấy.

**Số lượng đoạn: chưa đo**, cùng lý do như 3.5.

**Nếu sau này muốn dùng:** phải xin đồng ý rõ ràng, không phải sửa điều khoản rồi áp ngược
cho nội dung đã đăng trước đó.

### 3.7. `nao-agent` (116 đoạn) và `bai-dang-bds` (5.939 đoạn) — LOẠI

**Số đo.** 116 + 5.939 = **6.055 đoạn**. Kiểm: 17.788 − 6.055 = 11.733.

**Lý do 1 — điều khoản nhà cung cấp mô hình.** Cả hai nguồn là **đầu ra của mô hình bên thứ
ba** sinh qua cổng LiteLLM. Điều khoản của các nhà cung cấp mô hình thường **cấm dùng đầu
ra để huấn luyện mô hình cạnh tranh**. Một bộ dữ liệu mở đem đi huấn luyện một mô hình mở
rơi thẳng vào chỗ cấm ấy — và rủi ro không dừng ở BDSG, nó lan sang mọi người tải bộ về.

**Lý do 2 — bí mật thương mại của chính BDSG.** 3.601 "não agent" là **cấu hình thương
mại** của BDSG. Phát hành chúng là tự đem sản phẩm của mình cho không.

**Lý do 3 — hỏng phép đánh giá.** Huấn luyện trên đầu ra của mô hình khác rồi đo xem mô
hình mình "biết" gì thì thứ đo được là **trí nhớ về mô hình kia**, không phải tri thức về
doanh nghiệp Việt Nam. Điểm sẽ đẹp lên trong khi năng lực thật không đổi — đúng kiểu hỏng
mà không báo.

**Cách người đọc tự kiểm:**

```sql
SELECT nguon, COUNT(*) FROM doan_tri_thuc GROUP BY nguon ORDER BY nguon;
-- Do ngay 25/09/2026:
--   bai-dang-bds     5939   (LOAI - may sinh)
--   ho-so-dn         6434   (phat hanh)
--   ho-so-niem-yet   5192   (phat hanh)
--   nao-agent         116   (LOAI - may sinh)
--   wiki-crm          107   (phat hanh)
--   -------------------------------
--   Tong            17788
```

`xuat.py` chạy đúng truy vấn này trước khi lấy dữ liệu, và **dừng toàn bộ** nếu xuất hiện
một `nguon` nào khác 5 giá trị trên.

---

## 4. Mã nguồn của kho này — viết độc lập, không có nguồn dữ liệu nào đi kèm

Mục này tách riêng vì đây là chỗ dễ nhầm nhất khi đọc bảng ở mục 1: bảng ấy liệt kê nguồn
**DỮ LIỆU**, còn mã nguồn thì theo một giấy phép khác và có một câu chuyện xuất xứ khác.

### 4.1. Kiến trúc và bộ huấn luyện do BDSG viết

Kiến trúc mô hình (`mo-hinh/`) và bộ huấn luyện (`huan-luyen/`) do BDSG viết. Từng khối
được viết lại từ **mô tả toán học trong bài báo gốc**:

| Khối | Bài báo | Mã arXiv |
|---|---|---|
| Transformer | Vaswani và cộng sự, 2017 | arXiv:1706.03762 |
| Xếp chuẩn trước khối (pre-norm) | Xiong và cộng sự, 2020 | arXiv:2002.04745 |
| RMSNorm | Zhang và Sennrich, 2019 | arXiv:1910.07467 |
| RoPE | Su và cộng sự, 2021 | arXiv:2104.09864 |
| GQA | Ainslie và cộng sự, 2023 | arXiv:2305.13245 |
| SwiGLU | Shazeer, 2020 | arXiv:2002.05202 |
| Buộc trọng số vào/ra (`tie_word_embeddings`) | Press và Wolf, 2017 | arXiv:1608.05859 |
| BPE (thuật toán từ vựng) | Sennrich và cộng sự, 2016 | arXiv:1508.07909 |

Dòng **buộc trọng số vào/ra** được thêm ngày 26/09/2026 sau một lượt soát lại bảng này.
Nó từng bị sót, và chỗ sót ấy đáng ghi lại: `tie_word_embeddings` trông như một *tên trường
cấu hình* nên dễ bị xếp nhầm vào nhóm "quy ước đặt tên của hệ sinh thái" — trong khi nó là
một **kỹ thuật lấy từ bài báo**, và là kỹ thuật đổi hẳn số tham số của mô hình (lớp nhúng
đầu vào và lớp chiếu đầu ra dùng chung một ma trận, nên chỉ đếm một lần). Tên trường thì
không cần ghi công; kỹ thuật thì cần. Bảng này liệt kê **kỹ thuật**, không liệt kê tên
trường — đọc nhầm ranh giới ấy là cách một khoản ghi công biến mất mà không ai thấy.

**Vì sao điều này thuộc về một tệp về GIẤY PHÉP NGUỒN.** Vì nó là một khai báo xuất xứ, và
khai sai xuất xứ mã cũng nghiêm trọng đúng như khai sai xuất xứ dữ liệu — chỉ là ít người
soi hơn. Hai cách làm sai, cả hai đều phải tránh:

1. **Dẫn xuất mà không ghi công.** Nếu BDSG lấy mã của người khác, sửa vài chỗ rồi xoá tên
   họ đi, thì vi phạm chính giấy phép cho phép mình dùng — Apache-2.0 điều 4 buộc giữ thông
   báo bản quyền và **nêu rõ chỗ đã sửa**. Đó là vi phạm pháp lý.
2. **Khai là của mình thứ mình không viết.** Nặng hơn vế trên, vì nó là lời khai sai về
   nguồn gốc mô hình — đúng thứ mà cả kho này tồn tại để chống. Bảng trạng thái trong README
   ghi thẳng `bdsg_la_trong_so_bdsg = false`; một kho khai thật ở chỗ khó như thế thì không
   được khai dối ở chỗ dễ.

Cách tránh cả hai không phải là viết cẩn thận hơn, mà là **viết thật từ đầu từ bài báo**,
rồi khoá lại bằng cổng `cong/khong-tham-chieu-ngoai.py` để một cái tên không lặng lẽ quay
về qua một lần sao chép tài liệu.

**Ranh giới của cổng ấy, nói trước:** nó chứng minh được *tài liệu không còn khai sai
nguồn*, nó **không** chứng minh được *mã là viết độc lập*. Việc thứ hai chỉ có người đọc mã
mới làm được. Đừng đọc một dòng "cổng ĐẠT" thành nhiều hơn thế.

### 4.2. Không có bộ dữ liệu bên ngoài nào được trộn vào bộ này

Bộ dữ liệu phát hành ở đây gồm **đúng 5 nguồn** ở dòng 1–5 của bảng mục 1, tất cả đều là
dữ liệu của BDSG. Không có ngữ liệu bên ngoài nào được trộn vào.

Ranh giới ấy được giữ để mỗi bộ có **một giấy phép rõ ràng**, thay vì một mớ pha trộn
không ai truy được nguồn. Nếu sau này BDSG có trộn thêm ngữ liệu mở của bên khác ở bước
huấn luyện, thì việc ấy thuộc `huan-luyen/`, phải khai xuất xứ tại đó, và **vẫn không**
được đóng gói vào bộ dữ liệu phát hành này.

Hệ quả phải nói thẳng: **7,16 MB là nhỏ**, nhỏ hơn ngữ liệu tiền huấn luyện thông thường
vài bậc độ lớn. Đó là cái giá của việc chỉ phát hành thứ mình chứng minh được nguồn.

### 4.3. Vì sao BDSG phải tự huấn luyện bộ từ vựng

Lập luận đứng một mình, không cần so với ai:

Một bộ **BPE mức byte** (arXiv:1508.07909) không được luyện trên tiếng Việt sẽ đẩy chữ có
dấu xuống tận từng byte UTF-8 thô. Chữ tiếng Việt có dấu chiếm 2–3 byte trong UTF-8, nên
mỗi chữ như thế tốn nhiều token hơn mức cần. Hệ quả kép, cả hai đều đắt: phí **độ dài ngữ
cảnh** và phí **thời gian GPU** (chi phí huấn luyện tính theo token, không theo chữ).

Phép đo ngày 25/09/2026 (chi tiết ở `huan-luyen/tu-vung/ket-qua/`): so cùng cỡ từ vựng
**6.400**, bản học tiếng Việt dùng **289.266** token cho phần giữ lại, bản không học tiếng
Việt dùng **852.285** — **giảm 66,1%**. Đổi lại, tiếng Anh **tệ đi 22,0%**. Con số thứ hai
phải công bố cùng, và nó là lý do bản phát hành phải trộn hai thứ tiếng theo trọng số chứ
không đổi hẳn sang tiếng Việt.

**Hệ quả phải chấp nhận:** trọng số luôn gắn chặt với đúng bộ từ vựng đã huấn luyện cùng
nó. Mô hình của kho này không dùng lẫn được với mô hình dựng trên từ vựng khác, theo cả hai
chiều.

### 4.4. Hạn chế dự báo trước của mô hình nhỏ — và vì sao nó CHƯA phải số đo

**Mô hình ngôn ngữ nhỏ bịa kiến thức.** Đây là giới hạn của cỡ mô hình, không phải lỗi cấu
hình. Rủi ro thứ hai: **độ ổn định sự thật thường giảm sau các giai đoạn tinh chỉnh theo sở
thích (RLHF/DPO)** — mô hình học cách trả lời dễ nghe hơn, và dễ nghe đôi khi trái với đúng.

Ghi hai điều này ở đây vì chúng ảnh hưởng trực tiếp tới cách bộ dữ liệu được dùng: nhóm câu
bẫy chống bịa trong `danh-gia/` phải được đo lại sau **mỗi** giai đoạn tinh chỉnh, không
phải đo một lần ở cuối.

**Cả hai là dự báo dựa trên hiểu biết chung về mô hình nhỏ, KHÔNG phải số đo của BDSG.**
BDSG chưa có trọng số nào để đo (26/09/2026).

---

## 5. Giấy phép bộ dữ liệu phát hành

**CC-BY-4.0** — https://creativecommons.org/licenses/by/4.0/

Áp cho **dòng 1–5** ở bảng mục 1, tức ba tệp JSONL trong bộ. **Không** cấp quyền nào đối
với các nguồn ở dòng 6–13: những nguồn ấy không nằm trong bộ, nên cũng không nằm trong giấy
phép.

**MÃ NGUỒN theo giấy phép khác: Apache-2.0** (xem `LICENSE-CODE` ở gốc kho, kèm ghi chú vì
sao BDSG chọn giấy phép ấy). Hai phạm vi độc lập nhau — CC-BY-4.0 cho dữ liệu, Apache-2.0
cho mã — và đó là chủ ý: trộn chung một giấy phép cho hai loại tài sản khác nhau là cách
nhanh nhất để người dùng hạ nguồn không biết mình được phép làm gì.

Cách trích dẫn: xem README mục 11.

---

## 6. Điều tệp này CHƯA làm được

Nói thẳng, để người đọc biết ranh giới của bảng trên:

- **Chưa có luật sư đọc.** Bảng này là lập luận kỹ thuật và nghiệp vụ của người làm dữ
  liệu, **chưa qua rà soát pháp lý**.
- **Số lượng của `tin-tuc` và `bai-dang` chưa đo.** Chúng bị loại ở vòng lọc nguồn, trước
  khi đếm.
- **Chưa rà điều khoản từng nhà cung cấp mô hình trong cổng LiteLLM.** Lập luận ở mục 3.7
  dựa trên *quy tắc chung* của ngành ("thường cấm"), **không** dựa trên việc đã đọc từng
  bản điều khoản cụ thể và đối chiếu ngày hiệu lực. Kết luận loại trừ không đổi — nhưng
  căn cứ thì đúng ra phải chắc hơn thế.
- **Chưa có ai đọc lại toàn bộ mã trong `mo-hinh/` và `huan-luyen/` để xác nhận tính độc
  lập bằng mắt người.** Cổng `cong/khong-tham-chieu-ngoai.py` chỉ chứng minh tài liệu không
  còn khai sai nguồn; nó không chứng minh được mã là viết độc lập. Khẳng định ở mục 4.1
  dựa trên lời khai của người viết và trên các trích dẫn bài báo có trong mã, **chưa** dựa
  trên một lượt soát đối kháng độc lập.
- **Chưa có ai đọc mẫu ngẫu nhiên** trong 11.733 đoạn để xác nhận không lẫn nguồn lạ. Mọi
  khẳng định về xuất xứ trong tệp này dựa trên **trường `nguon` trong CSDL**, tức là tin
  vào bước gán nguồn lúc nạp dữ liệu.

Điểm cuối đáng nhấn: cả bảng này đứng trên giả định rằng **trường `nguon` được gán đúng
lúc nạp**. Nếu giả định ấy sai ở đâu đó thì mọi lập luận phía trên sai theo ở chính chỗ ấy,
mà không có dấu hiệu nào lộ ra. Đó là rủi ro còn mở, và cách duy nhất đóng lại là đọc mẫu
bằng mắt người.
