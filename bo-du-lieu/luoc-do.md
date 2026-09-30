# Lược đồ JSONL

Lược đồ của ba tệp trong bộ dữ liệu mở **Open BDSG**.
Xem [README.md](README.md) cho số đo và [GIAY-PHEP-NGUON.md](GIAY-PHEP-NGUON.md) cho xuất xứ.

Định dạng: **JSON Lines** — mỗi dòng là một đối tượng JSON hoàn chỉnh, mã hoá **UTF-8**,
**không** có BOM, xuống dòng `\n`. Ghi bằng `json.dumps(..., ensure_ascii=False)` để tiếng
Việt giữ nguyên chữ có dấu thay vì bị thoát thành `\uXXXX`. Mỗi chữ có dấu khi bị thoát
chiếm **6 byte** (`ế`) thay cho **2–3 byte** UTF-8, tức nặng thêm khoảng 2–3 lần
**ở riêng những ký tự ấy** — phần tăng trên cả tệp thì tuỳ tỉ lệ chữ có dấu và **chưa đo**.
Ngoài chuyện dung lượng, tệp thoát còn không đọc được bằng mắt khi soi lỗi.

| Tệp | Số bản ghi | Dùng cho |
|---|---|---|
| `tri-thuc-van-ban.jsonl` | 11.733 | Tiền huấn luyện |
| `ho-so-cong-ty.jsonl` | 5.424 | Tiền huấn luyện + tra cứu có cấu trúc |
| `nang-luc.jsonl` | 11.927 | Bộ từ vựng + thuật ngữ vi↔en (**không** dùng tiền huấn luyện, xem 4.3.0) |

---

## 1. Trường chung — bắt buộc ở CẢ BA lớp

Bảy trường dưới đây có mặt trong **mọi** bản ghi của **mọi** tệp. Bốn trường xuất xứ
(`nguon`, `giay_phep`, `ngay_do`, `muc_tin_cay`) là **bắt buộc theo thiết kế**: một bản ghi
không nói được nó từ đâu ra thì không được phép nằm trong bộ phát hành.

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `ma` | string | **Có** | Duy nhất trong toàn bộ bản phát hành. Dạng `<tiền tố lớp>-<6 chữ số>`. **Chỉ ổn định TRONG một bản phát hành**: số thứ tự sinh theo thứ tự dòng lúc xuất, nên bản sau có thể gán `tvb-000005` cho một đoạn khác. Muốn truy ngược bền thì dùng `ma_nguon_goc`. |
| `lop` | string | **Có** | `tri-thuc-van-ban` \| `ho-so-cong-ty` \| `nang-luc` |
| `nguon` | string | **Có** | Mã nguồn, **phải nằm trong danh sách trắng** ở mục 2. |
| `giay_phep` | string | **Có** | Giấy phép phát hành của bản ghi. Bản phát hành này: luôn `CC-BY-4.0`. |
| `ngay_do` | string | **Có** | Ngày đo/trích nguồn, `YYYY-MM-DD`. Bản phát hành này: luôn `2026-09-25`. |
| `muc_tin_cay` | string | **Có** | `cao` \| `trung-binh` \| `thap` — quy tắc gán ở mục 3. |
| `ngon_ngu` | string | **Có** | `vi` \| `en` \| `vi+en` — xem mục 5. |

### Vì sao `giay_phep` và `ngay_do` nằm trong TỪNG BẢN GHI, không chỉ trong README

Vì bộ dữ liệu sẽ bị cắt, trộn, lọc, nối với bộ khác. Khi một dòng JSONL bị copy sang tệp
khác, README ở lại đằng sau. Chỉ trường nằm trong chính dòng ấy mới đi theo nó. Đây là kiểu
lỗi im lặng điển hình: dữ liệu vẫn chạy, chỉ là không ai còn truy được nó từ đâu.

### Quy tắc kiểu dữ liệu: một trường — một kiểu, trên toàn tệp

Trường có thể **vắng giá trị** nhưng **không được vắng khoá**: ghi `null`, không bỏ khoá đi.
Và một trường **không được lúc là số lúc là chuỗi**.

Lý do thực dụng: cách nạp JSONL phổ biến nhất — `load_dataset('json', ...)` của thư viện
`datasets` — **suy lược đồ từ dữ liệu**. Một trường lúc `123` lúc `"123"` sẽ làm bước suy
lược đồ hỏng giữa chừng, và hỏng ở bước nạp dữ liệu thì thông báo lỗi chẳng liên quan gì
tới cái sai thật. Giữ kiểu cố định là cách rẻ nhất để không phải đi tìm.

---

## 2. Danh sách trắng `nguon`

`xuat.py` **dừng toàn bộ** khi gặp giá trị `nguon` ngoài bảng này (fail-closed).

| `nguon` | Lớp | Số bản ghi | Từ đâu |
|---|---|---|---|
| `ho-so-niem-yet` | 1 | 5.192 | `bdsg_chat.doan_tri_thuc` |
| `ho-so-dn` | 1 | 6.434 | `bdsg_chat.doan_tri_thuc` |
| `wiki-crm` | 1 | 107 | `bdsg_chat.doan_tri_thuc` |
| `business-company-profiles` | 2 | 5.424 | `postgres.business.company_profiles` |
| `business-capabilities` | 3 | 11.927 | `postgres.business.capabilities` |

> **Bẫy tên gọi.** `nguon = "ho-so-dn"` là **6.434 đoạn văn bản** ở lớp 1, **không phải**
> 5.424 hồ sơ có cấu trúc ở lớp 2 (`nguon = "business-company-profiles"`). Trùng nghĩa
> tiếng Việt, khác hoàn toàn về CSDL, lược đồ và số lượng.

Mọi `nguon` khác — kể cả `nao-agent`, `bai-dang-bds`, `tin-tuc`, `bai-dang` — **không được
xuất hiện**. Nếu chúng xuất hiện thì hoặc truy vấn lọc sai, hoặc dữ liệu nguồn đã đổi;
cả hai trường hợp đều cần người xem, không phải máy bỏ qua.

---

## 3. `muc_tin_cay` — gán bằng luật, không bằng cảm tính

Ba mức, gán **cơ học** theo nguồn và theo cờ rác, để hai lần chạy khác nhau cho cùng kết quả.

| Mức | Nghĩa | Gán cho |
|---|---|---|
| `cao` | BDSG là tác giả, **hoặc** nội dung bắt nguồn từ công bố thông tin bắt buộc theo luật; bản ghi không bị gắn cờ rác | `wiki-crm`; `ho-so-dn`; `ho-so-niem-yet` khi `co_rac_web = false`; `business-company-profiles`; `business-capabilities` |
| `trung-binh` | Nội dung dùng được nhưng có dấu hiệu nhiễu đã biết | `ho-so-niem-yet` khi `co_rac_web = true` (110 bản ghi, mục 6.1 của README) |
| `thap` | Nội dung nghi ngờ về xuất xứ hoặc chất lượng | **0 bản ghi trong bản phát hành này.** Mọi thứ đáng xếp `thap` đều đã bị loại khỏi bộ, chứ không bị hạ mức rồi vẫn phát hành. |

Mức `thap` được **định nghĩa mà không được dùng** là có chủ ý: nó để chỗ cho các bản phát
hành sau, và để người đọc thấy rằng ở bản này không có hạng "cứ phát hành rồi dán nhãn xấu".

`muc_tin_cay` **không phải** điểm chất lượng nội dung. Chưa có ai đọc và chấm điểm mẫu ngẫu
nhiên — xem mục 6.4 của README. Nó chỉ là bản ghi của **xuất xứ và cờ rác**.

---

## 4. Lược đồ từng lớp

### 4.1. `tri-thuc-van-ban.jsonl` — lớp 1

Prefix `ma`: **`tvb-`**. 11.733 bản ghi.

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| *(7 trường chung ở mục 1)* | | **Có** | |
| `text` | string | **Có** | Nội dung đoạn. Không rỗng, không chỉ toàn khoảng trắng. |
| `so_ky_tu` | int | **Có** | `len(text)` tính bằng **ký tự Unicode**, không phải byte. |
| `co_rac_web` | bool | **Có** | `true` cho bản ghi dính rác cào web (menu/CSS/JS/URL ngoài). Phép đo 25/09/2026 đếm được **110** đoạn; nhưng cờ này do **bộ dò của `xuat.py`** gắn, mà đó **không phải bộ dò đã tạo ra con số 110**. Hai bộ dò khác nhau có thể ra hai con số khác nhau, nên số bản ghi `true` thực tế **chưa đo** — `xuat.py` in cả hai để đối chiếu. |
| `ma_nguon_goc` | string \| null | Không | Khoá của đoạn trong `bdsg_chat.doan_tri_thuc`, để truy ngược. |

**Vì sao tên trường là `text`:** `text` là khoá quy ước mà hầu hết bộ nạp dữ liệu tiền
huấn luyện đọc mặc định. Đặt tên khác thì mọi công cụ hạ nguồn đều phải sửa để dùng được
bộ này — cái giá ấy đổ lên người dùng, chỉ để đổi lấy một cái tên đẹp hơn trong lược đồ.

**Vì sao `so_ky_tu` đếm ký tự chứ không đếm byte:** để đối chiếu được với các số đo trong
README, vốn đo bằng ký tự. Muốn biết dung lượng byte thật thì đo tệp, và `xuat.py` in ra
(README mục 2 giải thích vì sao hai con số ấy khác nhau ở tiếng Việt).

**Vì sao `co_rac_web` là cờ chứ không phải bộ lọc:** 110/11.733 bản ghi có rác, nhưng bộ lọc
làm sạch tự động **chưa được viết và chưa được đo độ chính xác**. Gắn cờ là nói thật những gì
đã đo; xoá đi là quyết thay cho người dùng hạ nguồn bằng một công cụ chưa ai kiểm.

### 4.2. `ho-so-cong-ty.jsonl` — lớp 2

Prefix `ma`: **`hsc-`**. 5.424 bản ghi — chỉ những hồ sơ **`is_published` ∧ có ngành ∧ có sản phẩm**.

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| *(7 trường chung ở mục 1)* | | **Có** | |
| `text` | string | **Có** | Bản dựng văn xuôi từ `ten_cong_ty` + `nganh` + `tom_tat` + `san_pham`, để lớp này dùng được cho tiền huấn luyện mà không phải viết thêm mã. |
| `ten_cong_ty` | string | **Có** | |
| `nganh` | array[string] | **Có** | **Tên ngành**, luôn có ít nhất 1 phần tử — đó là một trong ba điều kiện lọc. Xem cảnh báo ngay dưới bảng. |
| `san_pham` | string | **Có** | Luôn khác rỗng — điều kiện lọc thứ hai. |
| `tom_tat` | string \| null | Không | **Có thể null.** Bảng gốc có 6.608/6.672 hồ sơ có `summary`, và `summary` **không** nằm trong ba điều kiện lọc. Số hồ sơ thiếu `tom_tat` trong 5.424 bản ghi thực xuất: **chưa đo.** |
| `ma_tinh` | string \| null | Không | **Có thể null.** Bảng gốc có 5.952/6.672 hồ sơ có `province_id`. Số bản ghi thiếu tỉnh trong 5.424: **chưa đo.** Luôn ghi dạng **chuỗi**, kể cả khi giá trị gốc là số — xem quy tắc kiểu ở mục 1. |
| `da_xuat_ban` | bool | **Có** | Luôn `true`. Giữ trường này để bản ghi tự chứng minh điều kiện lọc, thay vì bắt người đọc tin README. |
| `so_ky_tu` | int | **Có** | `len(text)`, ký tự Unicode. |

> **CHƯA LÀM — `nganh` chưa lấy được tên ngành.** Bảng `business.company_sector_links`
> chỉ có **số hiệu ngành** (`sector_id`, khoá ngoại). Bảng danh mục giữ **tên** ngành
> thì **chưa đối chiếu được lược đồ** tính đến 25/09/2026, nên truy vấn trong `xuat.py`
> **chưa JOIN** sang bảng ấy. Nếu cứ chạy, trường `nganh` sẽ ra `["12","47"]` và `text`
> sẽ thành *"Công ty X. Ngành: 12; 47."* — tệp vẫn hợp lệ, số bản ghi vẫn đúng 5.424, chỉ
> có nội dung là vô nghĩa. Đúng họ lỗi im lặng. Vì vậy `lay_lop2()` **dừng hẳn** khi thấy
> `nganh` toàn chữ số. Phải khai bảng danh mục ngành trong hằng số `COT` rồi mới chạy
> được lần đầu.

> **Đừng suy ra "5.424 doanh nghiệp có đủ ngành + tỉnh + sản phẩm".** Ba điều kiện lọc là
> *đã xuất bản* ∧ *có ngành* ∧ *có sản phẩm*. **Tỉnh không nằm trong bộ lọc**, nên một phần
> trong 5.424 bản ghi có `ma_tinh = null`. Phần ấy bao nhiêu: chưa đo.

### 4.3. `nang-luc.jsonl` — lớp 3

Prefix `ma`: **`nlc-`**. 11.927 bản ghi.

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| *(7 trường chung ở mục 1)* | | **Có** | |
| `ten` | string | **Có** | Cột `name`. |
| `ten_en` | string \| null | Không | Cột `name_en`. Số dòng có `name_en` khác rỗng: **chưa đo** (346.704 ký tự là tổng của cả hai cột). |
| `so_ky_tu` | int | **Có** | `len(ten) + len(ten_en or "")`. |

**4.3.0. Lớp này KHÔNG có trường `text`, và đó là quyết định có lý do.**

Một danh mục 11.927 cái tên không phải văn xuôi. Đổ nó vào tiền huấn luyện là dạy mô hình
**lặp danh sách** — đúng kiểu hỏng làm điểm đánh giá đẹp lên mà năng lực thật đi xuống.
Không có `text` nghĩa là bộ nạp tiền huấn luyện **không nạp nhầm** tệp này: nó sẽ lỗi ngay
vì thiếu khoá bắt buộc, thay vì âm thầm học sai. Thiếu một khoá là một lỗi ồn ào, và lỗi
ồn ào thì rẻ hơn lỗi im lặng.

Lớp 3 dùng cho hai việc: **huấn luyện bộ từ vựng** (BPE mức byte cần thấy thuật ngữ chuyên
ngành để không cắt vụn chúng) và **tra thuật ngữ vi↔en**.

**Cột `description` bị loại.** 696.890 ký tự nhưng chỉ **58 giá trị khác nhau trên 11.927 dòng**
⇒ là chuỗi xuất xứ do ETL lặp, không phải mô tả. Xem README mục 6.2.

---

## 5. `ngon_ngu` — dấu vết đo được của "Việt chính, Anh phụ"

Phạm vi ngôn ngữ của dự án là **đúng hai**: tiếng Việt (1) là chính, tiếng Anh (2) là phụ.
Trường `ngon_ngu` tồn tại để tỉ lệ ấy **đếm được**, thay vì chỉ được tuyên bố trong tài liệu.

| Giá trị | Nghĩa | Xuất hiện ở đâu trong bản phát hành này |
|---|---|---|
| `vi` | Tiếng Việt | Lớp 1, lớp 2; lớp 3 khi `ten_en` là null |
| `vi+en` | Song ngữ trong cùng bản ghi | Lớp 3 khi `ten_en` khác rỗng |
| `en` | Chỉ tiếng Anh | Hợp lệ trong lược đồ, **0 bản ghi** trong bản này |

Ba giá trị, hết. Lược đồ **không** định nghĩa sẵn giá trị nào cho một ngôn ngữ thứ ba.

Đó là một thay đổi có chủ ý ngày 26/09/2026, và lý do đáng ghi lại vì nó đi ngược trực
giác quen thuộc *"cứ định nghĩa sẵn cho khỏi phải đổi lược đồ sau"*: một giá trị enum được
định nghĩa mà **0 bản ghi** dùng không phải là chỗ trống vô hại. Nó là một lời hứa nằm
trong lược đồ — bộ kiểm hợp lệ chấp nhận nó, tài liệu phải giải thích nó, và người đọc suy
ra rằng dự án có kế hoạch cho nó. Khi kế hoạch ấy không còn, giữ lại giá trị là giữ lại
lời hứa đã hết hiệu lực.

Giá trị `en` thì khác, và khác ở chỗ kiểm được: nó có **0 bản ghi độc lập** nhưng tiếng
Anh **có thật** trong bộ này qua `vi+en` (cột `name_en` của lớp 3). Nó là chỗ chừa cho một
thứ đã có mặt, không phải cho một thứ chưa từng có.

Tỉ lệ trộn hai ngôn ngữ khi tiền huấn luyện: **chưa quyết, chưa đo.**

---

## 6. Ba bản ghi ví dụ

> **Dữ liệu trong ba ví dụ dưới đây là BỊA HOÀN TOÀN.** Tên doanh nghiệp, số liệu, mã tỉnh
> đều do người viết tài liệu nghĩ ra để minh hoạ **hình thức** bản ghi. **Không có tên doanh
> nghiệp thật nào trong tài liệu này.** Trường `nguon` trong ví dụ vẫn ghi giá trị thật vì
> đó là phần lược đồ cần minh hoạ.

### 6.1. Lớp 1

```json
{"ma":"tvb-000001","lop":"tri-thuc-van-ban","nguon":"ho-so-niem-yet","giay_phep":"CC-BY-4.0","ngay_do":"2026-09-25","muc_tin_cay":"cao","ngon_ngu":"vi","text":"Công ty Cổ phần Ví Dụ Một công bố kết quả kinh doanh quý II năm 2026 với doanh thu thuần 120.086.720.000 đồng, tăng 11% so với cùng kỳ. Ban lãnh đạo cho biết phần tăng đến từ mảng xây lắp hạ tầng. Mọi số liệu trong đoạn này là số liệu minh hoạ, không phải số liệu của một doanh nghiệp có thật.","so_ky_tu":293,"co_rac_web":false,"ma_nguon_goc":"dtt-000001"}
```

Ví dụ này cố ý chứa `120.086.720.000 đồng` — **đúng cái bẫy** đã làm bộ dò sinh 5 khớp
"địa chỉ IP" dương tính giả (README mục 7.3). Dùng chính dòng này để thử bộ dò: nếu nó báo
đây là địa chỉ IP thì bộ dò sai, không phải dữ liệu sai.

### 6.2. Lớp 2

```json
{"ma":"hsc-000001","lop":"ho-so-cong-ty","nguon":"business-company-profiles","giay_phep":"CC-BY-4.0","ngay_do":"2026-09-25","muc_tin_cay":"cao","ngon_ngu":"vi","text":"Công ty TNHH Minh Hoạ Hai. Ngành: Xây dựng dân dụng; Vật liệu xây dựng. Tóm tắt: Doanh nghiệp minh hoạ chuyên thi công nhà ở và cung cấp vật liệu, thành lập năm 2010. Sản phẩm, dịch vụ: thi công phần thô; cung cấp gạch không nung; tư vấn giám sát.","ten_cong_ty":"Công ty TNHH Minh Hoạ Hai","nganh":["Xây dựng dân dụng","Vật liệu xây dựng"],"san_pham":"thi công phần thô; cung cấp gạch không nung; tư vấn giám sát","tom_tat":"Doanh nghiệp minh hoạ chuyên thi công nhà ở và cung cấp vật liệu, thành lập năm 2010.","ma_tinh":"00","da_xuat_ban":true,"so_ky_tu":247}
```

`ma_tinh` để `"00"` — mã bịa, **không** trùng mã tỉnh thật nào, và là **chuỗi** chứ không
phải số (quy tắc một-trường-một-kiểu ở mục 1). Một bản ghi thật thiếu tỉnh sẽ ghi
`"ma_tinh": null`, **không** bỏ khoá đi.

### 6.3. Lớp 3

```json
{"ma":"nlc-000001","lop":"nang-luc","nguon":"business-capabilities","giay_phep":"CC-BY-4.0","ngay_do":"2026-09-25","muc_tin_cay":"cao","ngon_ngu":"vi+en","ten":"Tư vấn giám sát thi công","ten_en":"Construction supervision consultancy","so_ky_tu":60}
```

Không có `text` — xem 4.3.0. Không có `description` — xem README mục 6.2. `ngon_ngu` là
`vi+en` vì `ten_en` khác rỗng; dòng nào `ten_en` null thì ghi `vi`.

---

## 7. Kiểm bộ dữ liệu đã tải về

Bốn phép kiểm rẻ, chạy được ngay, không cần thư viện:

```bash
# 1. Đếm dòng — phải khớp đúng 11.733 / 5.424 / 11.927
wc -l tri-thuc-van-ban.jsonl ho-so-cong-ty.jsonl nang-luc.jsonl

# 2. Mọi dòng phải là JSON hợp lệ và có đủ 7 trường chung
python3 - <<'PY'
import json, sys
CHUNG = {"ma","lop","nguon","giay_phep","ngay_do","muc_tin_cay","ngon_ngu"}
for ten in ("tri-thuc-van-ban.jsonl","ho-so-cong-ty.jsonl","nang-luc.jsonl"):
    thieu = 0
    with open(ten, encoding="utf-8") as f:
        for i, dong in enumerate(f, 1):
            b = json.loads(dong)
            if not CHUNG.issubset(b):
                thieu += 1
                if thieu == 1:
                    print(f"{ten}:{i} thieu truong: {sorted(CHUNG - set(b))}")
    print(f"{ten}: {thieu} dong thieu truong chung")
PY

# 3. Danh sách trắng nguồn — không được có giá trị nào ngoài 5 giá trị đã công bố
python3 -c "import json,sys,collections;
print(collections.Counter(json.loads(d)['nguon'] for d in open(sys.argv[1],encoding='utf-8')))" \
  tri-thuc-van-ban.jsonl

# 4. Tệp phải là UTF-8 thật, không BOM, không byte NUL
#    (một byte NUL làm grep lặng lẽ bỏ qua cả tệp — lỗi im lặng kinh điển)
file tri-thuc-van-ban.jsonl
LC_ALL=C grep -c $'\x00' tri-thuc-van-ban.jsonl || echo "khong co byte NUL"
```

Phép kiểm 1 quan trọng hơn vẻ ngoài của nó: nếu số dòng **không** khớp con số đã công bố
thì hoặc bản tải về hỏng, hoặc ai đó đã lọc thêm mà không cập nhật thẻ dữ liệu. Cả hai
đều là lý do dừng lại, không phải lý do chạy tiếp.
