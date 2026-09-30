# Thẻ mô hình — Open BDSG OS

Viết theo khuôn thẻ mô hình (model card) của Hugging Face.

> ## Cảnh báo đặt ở đầu, không giấu xuống cuối
>
> ## Đổi hướng ngày 01/10/2026 — đọc trước mọi mục khác
>
> BDSG **bỏ** vai trò "phục vụ và tinh chỉnh Gemma 4 31B làm mô hình chính", và **bỏ cách
> nói "30 tỷ tham số"**. Hướng thay thế: **mô hình quyết định có kiểu** — trả một trong N
> nhãn kèm xác suất, không sinh văn. Lý do là số đo, không phải sở thích: mục tiêu sinh văn
> đòi ~20 token mỗi tham số, tức **537.569.280 token** cho 26.878.464 tham số, mà ngữ liệu
> đã huấn luyện thật là **2.068.295 token** — **thiếu 260 lần**. Đầy đủ ở
> [`tai-lieu/QUYET-DINH-CO-KIEU.md`](tai-lieu/QUYET-DINH-CO-KIEU.md).
>
> Thẻ này **chưa được viết lại** theo hướng mới. Mọi mục dưới đây vẫn nói về mô hình sinh
> văn, và chúng vẫn đúng như tài liệu về **bản trọng số 26/09/2026**. Mục nào nói về Gemma 4
> 31B thì đọc như tài liệu lịch sử, không như đường đi hiện tại.
>
> ### Số tham số — bảng do máy ghi
>
> Bảng này **không được gõ bằng tay**. Nó sinh từ
> [`cong/con-so-thuc.json`](cong/con-so-thuc.json) bằng
> `python3 mo-hinh/con_so_thuc.py --cap-nhat-tai-lieu`, mà tệp ấy đếm từ `parameters()` của
> chính mô hình. Sửa bằng tay sẽ bị ghi đè ở lần chạy sau.

<!-- BAT-DAU-CON-SO-THUC — sinh boi mo-hinh/con_so_thuc.py, DUNG SUA BANG TAY -->

| mô hình | mục tiêu | tham số (đếm thật) | fp32 | dùng được? |
|---|---|---:|---:|---|
| `bdsg-quyet-dinh-nho` | quyet-dinh-co-kieu | **4.592.140** | 17,52 MiB | chưa huấn luyện — đây là số của kiến trúc |
| `bdsg-quyet-dinh-vua` | quyet-dinh-co-kieu | **12.198.156** | 46,53 MiB | chưa huấn luyện — đây là số của kiến trúc |
| `bdsg-quyet-dinh-lon` | quyet-dinh-co-kieu | **26.883.084** | 102,55 MiB | chưa huấn luyện — đây là số của kiến trúc |
| `bdsg-da-huan-luyen-20260926` | sinh-van | **26.878.464** | 102,53 MiB | **chưa đạt** cổng nghiệm thu |
| `bdsg-nho` | sinh-van | **36.184.576** | 138,03 MiB | chưa huấn luyện — đây là số của kiến trúc |
| `bdsg-vua` | sinh-van | **119.563.008** | 456,10 MiB | chưa huấn luyện — đây là số của kiến trúc |
| `bdsg-lon` | sinh-van | **295.748.608** | 1 128,19 MiB | chưa huấn luyện — đây là số của kiến trúc |

<sub>Bảng này do máy ghi từ [`cong/con-so-thuc.json`](cong/con-so-thuc.json) bằng `python3 mo-hinh/con_so_thuc.py --cap-nhat-tai-lieu`. Ngày đo ở trường `do_luc` trong tệp ấy. Sửa bảng bằng tay sẽ bị ghi đè ở lần chạy sau.</sub>

<!-- KET-THUC-CON-SO-THUC -->

> **Thẻ này nói về MÔ HÌNH CỦA BDSG. Nó KHÔNG phải thẻ của Gemma 4 31B.**
> Kho này còn có một backend phục vụ trọng số của Google; ranh giới ở
> [§0](#0-hai-thu-khac-nhau-dung-lan).
>
> **Tại 26/09/2026, BDSG có đúng MỘT bản trọng số do chính mình huấn luyện, và nó là bản
> nghiên cứu chưa dùng được** (26.878.464 tham số; perplexity phần kiểm 102,5 so với phần
> học 19,9 — quá khớp 5,2 lần). Không có tệp trọng số nào trong kho, không có liên kết tải
> nào trong tài liệu này.
>
> Thứ đang chạy tại `llm.bdsg.vn` là **lớp truy hồi của BDSG đặt trước một mô hình của bên
> thứ ba**. API tự khai trường `bdsg_la_trong_so_bdsg = false` cho **mọi** mã mô hình.
>
> Mọi mục dưới đây cần một bản trọng số **dùng được** đều ghi **"chưa huấn luyện — mục này
> trống cho tới M7"**. Không mục nào được điền bằng số ước lượng, số của mô hình khác, hay
> số của thượng nguồn.

---

<a id="0-hai-thu-khac-nhau-dung-lan"></a>

## 0. Hai thứ khác nhau, đừng lẫn

| | **(a) Mô hình BDSG — thẻ này** | **(b) Backend Gemma 4 31B** |
|---|---|---|
| Trọng số của ai | **BDSG** | **Google DeepMind** |
| Cỡ | 26.878.464 tham số (đo 26/09/2026) | 31.273.088.876 tham số |
| Từ vựng | 6.400 token, BDSG tự luyện | 262.144 token, của Google |
| `bdsg_la_trong_so_bdsg` | `true` cho đúng bản ấy | **`false`** — BDSG chỉ phục vụ |
| Thẻ/tài liệu | **tệp này** | [`tai-lieu/GEMMA4-31B.md`](tai-lieu/GEMMA4-31B.md) |
| Giấy phép | Apache-2.0 (mã) · CC BY 4.0 (dữ liệu) | Apache-2.0 (trọng số của Google) |

**Ghi công Google:** trọng số Gemma 4 31B là của **Google DeepMind**, giấy phép
**Apache-2.0** (tra 26/09/2026, `gated = false`).
Nguồn: `https://huggingface.co/google/gemma-4-31B-it` ·
`https://huggingface.co/google/gemma-4-31B` ·
`https://github.com/google-deepmind/gemma` · bài báo arXiv:2607.02770.
**BDSG PHỤC VỤ trọng số ấy; BDSG KHÔNG huấn luyện chúng.**

Hai điều cấm về kỹ thuật, cả hai đều hỏng **lặng lẽ**, không có thông báo lỗi:

- **Không nạp trọng số Gemma 4 vào kiến trúc ở §1.2 của thẻ này.**
- **Không thay tokenizer/chat template gốc của Gemma bằng bộ từ vựng 6.400 ở §1.3.**

---

## 1. Chi tiết mô hình

### 1.1 Mô tả

| Trường | Giá trị |
|---|---|
| Tên | Open BDSG OS |
| Đơn vị phát triển | BDSG |
| Loại mô hình | mô hình ngôn ngữ nhân quả (decoder-only), pre-norm, kiến trúc do BDSG viết |
| Ngôn ngữ | **1. Tiếng Việt (chính) · 2. Tiếng Anh (phụ)** |
| Giấy phép mã | Apache License 2.0 — xem [LICENSE-CODE](LICENSE-CODE) |
| Giấy phép dữ liệu | CC BY 4.0, chỉ cho `bo-du-lieu/` — xem [LICENSE-DATA](LICENSE-DATA) |
| Mô hình gốc được tinh chỉnh từ | **không có** — huấn luyện từ đầu, không nạp trọng số của ai |
| Trọng số **đã huấn luyện** | bản **nghiên cứu**: 26.878.464 tham số · 107,5 MB · 74 tensor (26/09/2026) — [chi tiết](tai-lieu/LAN-HUAN-LUYEN-DAU-TIEN.md) |
| Trọng số **phát hành** | **chưa có** — bản nghiên cứu quá khớp 5,2 lần, chưa dùng được cho việc gì |
| Kho mã | thư mục này |
| Điểm cuối API đang sống | `https://llm.bdsg.vn` — **không phục vụ trọng số của BDSG** |
| Backend phục vụ trọng số **của bên ngoài** | `trien-khai/` — Gemma 4 31B **của Google DeepMind**, Apache-2.0; **không phải mô hình của thẻ này** |

### 1.2 Kiến trúc

**Kiến trúc do BDSG viết.** Không dẫn xuất từ mã của dự án nào khác. Từng khối được viết
lại từ **mô tả toán học trong bài báo gốc**; trích dẫn dưới đây là trích **bài báo**:

| Khối | Bài báo gốc | Mã arXiv |
|---|---|---|
| Transformer | Vaswani và cộng sự, 2017 | arXiv:1706.03762 |
| Xếp chuẩn trước khối (pre-norm) | Xiong và cộng sự, 2020 | arXiv:2002.04745 |
| RMSNorm | Zhang và Sennrich, 2019 | arXiv:1910.07467 |
| RoPE | Su và cộng sự, 2021 | arXiv:2104.09864 |
| GQA | Ainslie và cộng sự, 2023 | arXiv:2305.13245 |
| SwiGLU | Shazeer, 2020 | arXiv:2002.05202 |
| Buộc trọng số vào/ra (`tie_word_embeddings`) | Press và Wolf, 2017 | arXiv:1608.05859 |

**Tên trường cấu hình theo chuẩn `transformers`** — `hidden_size`, `num_hidden_layers`,
`num_attention_heads`, `num_key_value_heads`, `intermediate_size`, `vocab_size`,
`rms_norm_eps`, `rope_theta`, `tie_word_embeddings`. Đó là quy ước chung của cả hệ sinh
thái mô hình mở (Llama, Mistral, Qwen, Gemma đều dùng), không phải tên riêng của ai. Giữ
nguyên bộ tên ấy là điều kiện để trọng số của BDSG nạp được ở công cụ khác; đổi tên là tự
cắt đường ra của chính mình. Trường nào là phát minh riêng của BDSG thì mang tiền tố
`bdsg_`.

**Giá trị cụ thể không ghi ở thẻ này.** Mã kiến trúc ở `mo-hinh/`; các cấu hình (số lớp,
bề rộng, số đầu, cỡ từ vựng, số tham số, ước tính bộ nhớ) ở `huan-luyen/cau-hinh/`, mỗi
giá trị kèm lý do chọn. Chép số vào thẻ này chỉ tạo một bản sao sẽ lệch — đọc tại chỗ.

**Cỡ mà BDSG sẽ huấn luyện: đã chốt ngày 01/10/2026, và chốt theo hướng khác câu hỏi ban
đầu.** Câu hỏi cũ là "bao nhiêu tham số cho mô hình sinh văn" — câu hỏi ấy không có đáp án
tốt, vì ngữ liệu thiếu 260 lần ở mọi cỡ đáng làm. Đáp án là đổi mục tiêu: ba cấu hình
`huan-luyen/cau-hinh/quyet-dinh-{nho,vua,lon}.json`, mục tiêu `quyet-dinh-co-kieu`. Số tham
số của cả ba **không ghi ở đây** — đọc bảng do máy ghi ở đầu thẻ, hoặc chạy
`python3 mo-hinh/con_so_thuc.py`.

`quyet-dinh-lon` cố ý **trùng khít thân** bản trọng số đã huấn luyện 26/09/2026 (512 chiều ·
8 lớp · 8 đầu truy vấn / 4 đầu khoá-giá trị · từ vựng 6.400), nên 74/74 tensor thân nạp lại
được sang mô hình quyết định — kiểm bằng `nap_than_tu_ngon_ngu()`, chỉ bỏ `lm_head.weight`.

**Số tham số trong các tệp cấu hình là số TÍNH RA từ công thức, không phải số ĐẾM.** Hai
con số ấy phải khớp **tuyệt đối**; lệch thì một bên hiểu sai kiến trúc.

Phép đối chiếu ấy **không chờ trọng số**. Đếm tham số chỉ cần dựng mô hình với khởi tạo
ngẫu nhiên rồi cộng `p.numel()` trên `model.parameters()` — không cần huấn luyện, không cần
GPU, không cần một byte trọng số nào. "Đếm được tham số" **không** có nghĩa là "đã có trọng
số **dùng được**"; thẻ này giữ nguyên khẳng định ở mục 1.1 rằng trọng số phát hành **chưa
có** — bản trọng số duy nhất đã huấn luyện (26/09/2026) là bản nghiên cứu. Phép đối chiếu
thuộc mã kiến trúc ở `mo-hinh/` — kết quả đọc tại đó, thẻ này không khẳng định thay.

Lý do phải làm ngay chứ không hẹn tới M7: mọi ước tính bộ nhớ và mọi dự toán giờ GPU đều
bắt đầu từ con số tham số. Công thức sai ở đây làm sai toàn bộ dự toán mà **không báo lỗi
gì**, và nếu hoãn phép đối chiếu tới lúc có trọng số thì sai lầm chỉ lộ ra sau khi đã trả
tiền thuê GPU.

### 1.3 Từ vựng (tokenizer)

Byte-level BPE, `SPECIAL_TOKENS_NUM = 36`, `pre_tokenizer = ByteLevel(add_prefix_space=False)`,
thư viện `tokenizers` (Hugging Face).

**Trạng thái: bản THỬ NGHIỆM đã huấn luyện và đã đo (25/09/2026); bản PHÁT HÀNH chưa có.**

Bản thử nghiệm giữ nguyên cỡ từ vựng **6.400** và so với **một từ vựng cùng cỡ 6.400 nhưng
KHÔNG học tiếng Việt**, để so sánh công bằng (tăng cỡ từ vựng rồi khoe số token giảm là so
sánh gian). Đo trên phần giữ lại chưa từng thấy lúc huấn luyện (1.199 đoạn · 1.037.113 ký tự):

| Từ vựng, cùng cỡ 6.400 | Token (tiếng Việt) | ký tự/token | Token (tiếng Anh) | ký tự/token |
|---|---:|---:|---:|---:|
| **KHÔNG** học tiếng Việt | 852.285 | 1,22 | 2.001 | 3,18 |
| BDSG, **CÓ** học tiếng Việt | 289.266 | 3,59 | 2.441 | 2,61 |

Tiếng Việt **giảm 66,1% số token** (gấp 2,95 lần chữ trên cùng ngân sách ngữ cảnh); tiếng
Anh **tệ đi 22,0%**. Con số thứ hai là lý do bản phát hành phải **trộn hai thứ tiếng theo
trọng số** chứ không phải đổi hẳn sang tiếng Việt.

Cơ chế nhìn thấy được: chữ "Công" ở bản **không** học tiếng Việt tốn **4 token** vì dấu
tiếng Việt bị đẩy xuống từng byte UTF-8 thô; ở bản **có** học tiếng Việt nó gộp thành **1
token**. Cả một câu thử: **72 token xuống 21 token**.

**Cỡ từ vựng của bản phát hành: chưa chốt.** Cấu hình trong `huan-luyen/cau-hinh/` do nhóm
cấu hình giữ — đọc tại đó, đừng suy từ thẻ này.

**Vì sao BDSG phải tự huấn luyện từ vựng.** Một bộ BPE mức byte không được luyện trên tiếng
Việt sẽ đẩy chữ có dấu xuống tận từng byte UTF-8 thô. Chữ có dấu chiếm 2–3 byte trong
UTF-8, nên mỗi chữ tốn nhiều token hơn mức cần — phí cả **độ dài ngữ cảnh** lẫn **thời gian
GPU** (chi phí huấn luyện tính theo token, không theo chữ). Muốn tiếng Việt đứng thứ nhất
thì từ vựng phải dựng trên ngữ liệu tiếng Việt; không có đường vòng.

**Hệ quả phải chấp nhận:** trọng số luôn gắn chặt với đúng bộ từ vựng đã huấn luyện cùng
nó. Mô hình của dự án này **không dùng lẫn được** với mô hình dựng trên từ vựng khác, theo
cả hai chiều. Đó là cái giá của việc đặt tiếng Việt lên đầu, không phải khiếm khuyết vá được.

---

## 2. Công dụng dự kiến

### 2.1 Dùng trực tiếp

**Chưa huấn luyện — mục này trống cho tới M7.** Không có trọng số thì không có công dụng
trực tiếp nào để mô tả.

Mục tiêu của dự án (là mục tiêu, không phải trạng thái): mô hình đủ nhỏ để **người dùng
tải về máy cá nhân chạy được**, kể cả khi không có GPU rời.

### 2.2 Dùng làm nền cho việc khác

**Chưa huấn luyện — mục này trống cho tới M7.**

### 2.3 Thứ dùng được ngay hôm nay

Không phải trọng số, nhưng có thật — **có thật trong cơ sở dữ liệu nguồn**, đo ngày
25/09/2026:

| Tài nguyên | Dùng để làm gì |
|---|---|
| Ngữ liệu doanh nghiệp Việt Nam (11.733 đoạn · 7.509.969 ký tự · 7,16 MB) | huấn luyện hoặc đánh giá mô hình khác |
| Lớp có cấu trúc: 5.424 doanh nghiệp đủ ngành + tỉnh + sản phẩm | dựng bộ hỏi–đáp có đáp án kiểm chứng được |
| Bộ đánh giá 227 câu đóng băng (22/09/2026) | đo mô hình tiếng Việt lĩnh vực doanh nghiệp |
| `trien-khai/` — kịch bản phục vụ **Gemma 4 31B của Google** qua vLLM (26/09/2026) | chạy một trợ lý **trên máy nội bộ**, nếu bạn có GPU NVIDIA đủ lớn |

**Về dòng cuối, phải nói đủ ba điều — nó là trọng số của người khác và nó chưa chạy thật:**

1. **Trọng số là của Google DeepMind** (Apache-2.0), không nằm trong kho này. BDSG phục vụ
   chúng. Xem [§0](#0-hai-thu-khac-nhau-dung-lan) và
   [`tai-lieu/GEMMA4-31B.md`](tai-lieu/GEMMA4-31B.md).
2. **Chưa ai chạy thử.** Máy soạn phần đó là macOS arm64 không CUDA: chưa cài được `vllm`,
   chưa nạp trọng số. Bài tự kiểm các hàm tính thì có chạy thật và ĐẠT 45/45 (26/09/2026),
   nhưng nó chỉ chứng minh phép tính đúng như đã viết — **không** chứng minh mô hình chạy.
   Độ trễ, thông lượng, VRAM thật: **chưa đo**.
3. **CHƯA CÓ ĐĂNG NHẬP.** Mặc định nghe `127.0.0.1`, có chủ ý. Đây là bản **demo một người
   trên localhost**, **chưa dùng được cho nhiều nhân viên**: không có "ai đã hỏi gì",
   không có hạn mức theo người, không tách được hội thoại người này khỏi người kia.

> **Phải đọc kèm bảng trên, nếu không nó thành lời hứa.** "Có thật" ở đây nghĩa là *đã đo
> được ở nguồn*, **chưa** nghĩa là *đã nằm sẵn trong bản clone của bạn*. Việc kết xuất ba
> tài nguyên ấy thành tệp thuộc các mốc sau và do nhóm khác làm trong `bo-du-lieu/`,
> `danh-gia/`, `huan-luyen/`. Lúc 22:00 ngày 25/09/2026, `danh-gia/` còn rỗng và
> `bo-du-lieu/` mới có tài liệu cùng script kết xuất, chưa có tệp ngữ liệu. Trạng thái ấy
> đổi theo giờ — hãy liệt kê chính các thư mục đó thay vì tin dòng này.

---

## 3. Ngoài phạm vi và không được dùng

Những việc sau **không** nằm trong phạm vi, kể cả sau khi có trọng số ở M7:

- **Tư vấn đầu tư, định giá doanh nghiệp, khuyến nghị mua bán chứng khoán.** Ngữ liệu có
  `ho-so-niem-yet` (5.192 đoạn) — hồ sơ doanh nghiệp niêm yết. Có dữ liệu về doanh nghiệp
  niêm yết **không** làm mô hình thành công cụ tư vấn đầu tư.
- **Tư vấn pháp lý, kế toán, thuế.** Trong ngữ liệu có mã số thuế và số ĐKKD (thông tin
  đăng ký công khai); đó là dữ liệu định danh doanh nghiệp, không phải cơ sở để tư vấn thuế.
- **Tra cứu thông tin liên hệ của cá nhân.** Email và số điện thoại đã bị gỡ khỏi ngữ liệu
  (đo 25/09/2026: 0 email, 0 số điện thoại). Mô hình không được dựng để trả về thông tin
  liên hệ, và nếu nó trả về thì đó là bịa.
- **Ra quyết định tự động có hệ quả với con người hoặc doanh nghiệp** (cho vay, tuyển dụng,
  chấm tín nhiệm, sàng lọc đối tác).
- **Nguồn dữ kiện chính thức.** Ngữ liệu chụp trạng thái tại thời điểm cào; doanh nghiệp
  thay đổi liên tục.

---

## 4. Dữ liệu huấn luyện

Toàn bộ số đo dưới đây đo ngày **25/09/2026**, trực tiếp trên CSDL.

### 4.1 Lớp văn bản (`bdsg_chat.doan_tri_thuc`)

| Nguồn | Số đoạn | Dung lượng |
|---|---:|---:|
| `ho-so-niem-yet` | 5.192 | 4,20 MB |
| `ho-so-dn` | 6.434 | 2,83 MB |
| `wiki-crm` | 107 | 0,13 MB |
| **Tổng phát hành được** | **11.733** | **7,16 MB** (7.509.969 ký tự) |

Chia tập (trên toàn bộ 17.788 đoạn của bảng gốc, trước khi loại nguồn máy sinh):
huấn luyện **16.151** · kiểm tra **835** · thẩm định **802**.

### 4.2 Lớp có cấu trúc (`postgres`)

| Bảng | Số đo |
|---|---|
| `business.company_profiles` | 6.672 tổng · 5.645 đã xuất bản · 6.439 có sản phẩm · 5.952 có mã tỉnh · 6.608 có tóm tắt |
| Ký tự (trên 5.645 đã xuất bản) | tóm tắt 1.941.353 + sản phẩm 322.477 |
| `business.company_sector_links` | 6.666 công ty có ngành |
| `business.capabilities` | 11.927 dòng · 346.704 ký tự tên (`name` + `name_en`) |

**Con số chính thức cho "doanh nghiệp theo ngành nghề, tỉnh, sản phẩm dịch vụ" là 5.424** —
đủ **cả ba** điều kiện (đã xuất bản ∧ có ngành ∧ có sản phẩm). Các con số 6.672 / 6.439 /
5.952 chỉ đếm theo **một** điều kiện và không được dùng thay.

### 4.3 Phân bố ngôn ngữ

| Thứ tự | Ngôn ngữ | Dung lượng đã đo |
|---|---|---|
| 1 | Tiếng Việt (chính) | 7.509.969 ký tự |
| 2 | Tiếng Anh (phụ) | **chưa tách đo riêng** (346.704 ký tự là tổng `name` + `name_en`) |

Không có ngôn ngữ nào khác trong bộ này. Phạm vi ngôn ngữ của dự án là đúng hai, chốt ngày
26/09/2026.

### 4.4 Tiền xử lý và kiểm tra dữ liệu cá nhân

Quét tự chạy, không tin lời khai của bước trước:

| Phép quét | Kết quả |
|---|---|
| Email | 0 |
| Số điện thoại | 0 |
| URL nội bộ | 0 |
| "mã số thuế" | 29 khớp — phần lớn là mã số thuế / số ĐKKD doanh nghiệp (**thông tin đăng ký công khai** ở Việt Nam), lẫn vài dương tính giả (tên lớp CSS, trường `rev` trong JSON) |
| "địa chỉ IP" | 5 khớp — **tất cả dương tính giả**: số tiền kiểu Việt Nam, ví dụ `120.086.720.000 đồng` |

Nhãn `[EMAIL]` và `[SĐT]` còn trong văn bản là bằng chứng bước gỡ **đã chạy thật**.

**Rác cào web còn sót:** 110 đoạn (menu web / CSS / JS / URL ngoài) = **0,17 MB trên
7,16 MB = 2,3%**, tập trung ở `ho-so-niem-yet` (110/5.192 = 2,1%). Đây là số đo trên bản
thô; bộ lọc của bản phát hành thuộc M4 và trạng thái của nó ghi trong `bo-du-lieu/`.

### 4.5 Nguồn bị loại và lý do

| Nguồn | Quy mô | Lý do |
|---|---|---|
| `map5d.khach_dn` | 1.079.991 bản ghi | 100% `nguon = 'crm_geocode_dot2'` ⇒ dữ liệu khách hàng CRM. Cột chỉ có `id`, `ten`, `do_chinh_xac`, `ma_xa`, `ma_tinh`, `geom`, `nguon`, `ngay_cap_nhat` — **không có ngành nghề, không có sản phẩm** |
| `kho-tri-thuc` | 118 tệp | 118/118 mang dòng cấp phép bên thứ ba ("Licensed to RAI Holdings") |
| `ocop` | 1.727 sản phẩm | văn quảng cáo người bán, `url` trỏ `buudien.vn` |
| `tin-tuc` | — | bản quyền toà soạn |
| `bai-dang` | — | nội dung người dùng đăng trên nền tảng |
| `nao-agent` | 116 đoạn | **máy sinh qua LiteLLM** ⇒ đầu ra mô hình bên thứ ba; thêm nữa 3.601 não agent là cấu hình thương mại của BDSG |
| `bai-dang-bds` | 5.939 đoạn | **máy sinh qua LiteLLM** — cùng lý do |
| `business.capabilities.description` | 696.890 ký tự | chỉ **58 giá trị khác nhau** trên 11.927 dòng ⇒ chuỗi xuất xứ ETL lặp lại, không phải mô tả |

Hai nguồn máy sinh cộng lại 6.055 đoạn — đúng bằng khoảng cách 17.788 − 11.733.

---

## 5. Quy trình huấn luyện

**Chưa huấn luyện — mục này trống cho tới M7.**

Các trường sau **không có giá trị** vì chưa có lần chạy nào:

| Trường | Giá trị |
|---|---|
| Số bước / số epoch | chưa đo |
| Tốc độ học, bộ tối ưu, lịch giảm | chưa đo |
| Kích thước lô, độ dài ngữ cảnh khi huấn luyện | chưa đo |
| Độ chính xác số (fp16/bf16) | chưa đo |
| Phần cứng đã dùng | chưa có — chưa thuê GPU lần nào |
| Thời gian huấn luyện | chưa đo |
| Mất mát cuối cùng | chưa đo |

Trình tự **dự kiến**: huấn luyện từ vựng → tiền huấn luyện → tinh chỉnh có giám sát. Mã của
từng bước do BDSG viết và nằm ở `huan-luyen/`; trạng thái từng bước do nhóm ấy ghi tại đó.

**Không có số chi phí nào để trích, và ô này cố ý để trống.** BDSG chưa thuê GPU lần nào,
nên không có giờ máy, không có đơn giá, không có hoá đơn. Ước tính **bộ nhớ** theo số tham
số thì có, trong `huan-luyen/cau-hinh/` — nhưng ước tính bộ nhớ không phải phép đo tốc độ,
và hai thứ ấy không suy ra nhau.

Mượn số đo trên phần cứng và ngữ liệu của người khác để lấp ô "chi phí của BDSG" là làm hỏng
chính điều thẻ này tồn tại để làm: một con số như thế sẽ được đọc như một lời hứa mà BDSG
chưa có cơ sở nào để giữ.

---

## 6. Đánh giá

### 6.1 Bộ đánh giá

227 câu, **đóng băng ngày 22/09/2026**. Bộ câu hỏi không được sửa sau khi đã đo, để lần đo
sau còn so được với lần này.

### 6.2 Kết quả đường cơ sở M3

> **Đây KHÔNG phải điểm của trọng số BDSG.** Không có trọng số nào để đo. Đây là điểm của
> hệ đang chạy tại `llm.bdsg.vn`: lớp truy hồi `pg_trgm` + `tsvector` của BDSG đặt trước
> một mô hình của bên thứ ba.

| Nhóm | Số câu | Điểm |
|---|---:|---:|
| Nghiệp vụ **trong** kho tri thức | 111 | 0,636 |
| Nghiệp vụ **ngoài** kho tri thức | 31 | 0,539 |
| Câu bẫy chống bịa | 60 | 0,953 |
| Tiếng Việt tổng quát | 25 | 0,908 |
| **Lợi ích truy hồi** (trong − ngoài) | — | **+0,097** |

### 6.3 Cách đọc

- **+0,097 là toàn bộ đóng góp đo được của lớp truy hồi.** Không lớn. Ghi đúng như đo được
  tốt hơn là trưng 0,636 để người đọc tưởng đó là công của BDSG.
- **0,953 ở nhóm chống bịa là đường cơ sở cao**, nghĩa là khoảng cải thiện còn lại rất hẹp —
  không nghĩa là hệ đã an toàn.
- Lớp truy hồi **khớp chữ, không khớp nghĩa**: cổng LiteLLM của BDSG không có mô hình nhúng
  (embedding) nào, nên không có lựa chọn vector.

### 6.4 Đánh giá trọng số BDSG

**Chưa huấn luyện — mục này trống cho tới M7.** Khi có trọng số, chúng sẽ được đo trên
đúng bộ 227 câu đã đóng băng ở trên và kết quả sẽ đặt cạnh đường cơ sở này.

---

## 7. Giới hạn và thiên lệch

### 7.1 Giới hạn do dữ liệu (đo được)

- **Ngữ liệu nhỏ: 7,16 MB.** Ngữ liệu tiền huấn luyện của các mô hình ngôn ngữ mở thường
  tính bằng **GB trở lên**, tức lớn hơn con số này nhiều bậc độ lớn. (Đây là nhận định về
  mặt bằng chung của lĩnh vực, **không phải một phép đo của BDSG**; BDSG không đo ngữ liệu
  của ai khác.) Mô hình huấn luyện trên 7,16 MB sẽ **không** có kiến thức tổng quát; tốt
  nhất nó chỉ thạo miền doanh nghiệp Việt Nam trong ngữ liệu. Đây là giới hạn lớn nhất của
  dự án, và nó là giới hạn về **dữ liệu**, không phải về kiến trúc hay phần cứng.
- **2,3% ngữ liệu còn dính rác cào web** (110 đoạn, 0,17 MB), chưa lọc.
- **Thiên lệch về doanh nghiệp niêm yết và doanh nghiệp có hồ sơ trên nền tảng BDSG.**
  `ho-so-niem-yet` chiếm 4,20/7,16 MB = 59% dung lượng. Doanh nghiệp nhỏ, hộ kinh doanh,
  doanh nghiệp không có hồ sơ số gần như vắng mặt.
- **Thiên lệch địa lý chưa đo.** Có 5.952 hồ sơ mang mã tỉnh, nhưng **phân bố theo tỉnh
  chưa được đo** — không kết luận gì về độ phủ vùng miền.
- **Tiếng Anh chưa tách đo.** Mọi tuyên bố về năng lực tiếng Anh đều chưa có cơ sở đo lường;
  con số duy nhất đã đo là tokenizer **tệ đi 22,0%** khi chỉ học tiếng Việt (25/09/2026).

### 7.2 Giới hạn do cỡ mô hình

**Mô hình ngôn ngữ nhỏ bịa kiến thức.** Đây là giới hạn của cỡ mô hình, không phải lỗi cấu
hình, và không có cách điều chỉnh tham số nào làm nó biến mất. Một mô hình vài chục đến vài
trăm triệu tham số không có đủ chỗ để nhớ sự kiện, nên khi bị hỏi thứ nó không biết, đầu ra
trông trôi chảy vẫn là đầu ra bịa.

Rủi ro thứ hai phải cảnh báo trước: **độ ổn định sự thật thường giảm sau các giai đoạn tinh
chỉnh theo sở thích (RLHF/DPO)** — mô hình học cách trả lời *dễ nghe* hơn, và "dễ nghe" đôi
khi trái với "đúng". Đây là lý do nhóm câu bẫy chống bịa phải được đo lại sau **mỗi** giai
đoạn tinh chỉnh, chứ không chỉ đo một lần ở cuối.

**Cả hai điều trên là dự báo dựa trên hiểu biết chung về mô hình nhỏ, KHÔNG phải số đo của
BDSG.** BDSG chưa có trọng số nào để đo. Đường cơ sở 0,953 ở mục 6.2 là điểm của hệ đang
chạy (truy hồi + mô hình bên thứ ba), không phải của mô hình này.

### 7.3 Khuyến nghị

Đừng dùng đầu ra làm dữ kiện mà không đối chiếu nguồn. Trong miền doanh nghiệp, một cái
tên hay một con số bịa ra trông y hệt một cái tên hay con số thật.

---

## 8. Tác động môi trường

**Chưa huấn luyện — mục này trống cho tới M7.**

| Trường | Giá trị |
|---|---|
| Loại phần cứng | chưa có |
| Số giờ GPU | chưa đo |
| Nhà cung cấp hạ tầng / vùng | chưa chọn |
| Lượng carbon phát thải | chưa đo |

Sẽ khai báo theo *Machine Learning Impact calculator* (Lacoste và cộng sự, 2019) khi có lần
chạy thật. Không điền số của thượng nguồn vào ô của mình.

---

## 9. Cân nhắc đạo đức

- **Dữ liệu khách hàng CRM không được đưa vào, và đây là quyết định lớn nhất của bản phát
  hành này.** 1.079.991 bản ghi `map5d.khach_dn` bị loại vì 100% đến từ `crm_geocode_dot2`.
  Đó là con số lớn nhất mà dự án có; không dùng nó là chỗ bản phát hành này **nói không**
  rõ nhất.
- **Đầu ra máy sinh không được đưa vào.** 6.055 đoạn sinh qua cổng LiteLLM bị loại vì điều
  khoản nhà cung cấp thường cấm dùng đầu ra để huấn luyện mô hình cạnh tranh — và vì huấn
  luyện mô hình trên đầu ra của mô hình khác là chép bài, không phải học.
- **Mã số thuế và số ĐKKD được giữ lại có chủ đích.** Ở Việt Nam đây là thông tin đăng ký
  **công khai** của pháp nhân, không phải dữ liệu cá nhân. Email và số điện thoại thì bị gỡ
  (đo lại: 0 và 0).
- **Nội dung bên thứ ba bị loại theo tỷ lệ đo được, không theo cảm tính.** `kho-tri-thuc`
  bị loại vì **118/118** tệp mang dòng cấp phép của bên khác.
- **Tên miền không phải bằng chứng.** `llm.bdsg.vn` là tên miền; nó không chứng minh có
  trọng số. Trường `bdsg_la_trong_so_bdsg` mới là thứ trả lời câu hỏi đó, và nó đang trả
  `false`.

---

## 10. Trích dẫn

```bibtex
@misc{openbdsgos2026,
  title        = {Open BDSG OS: bộ dữ liệu và bộ đánh giá mở
                  cho tri thức doanh nghiệp Việt Nam},
  author       = {BDSG},
  year         = {2026},
  note         = {Chưa có trọng số; phát hành dữ liệu, mã và bộ đánh giá trước.
                  Kiến trúc và bộ huấn luyện do BDSG viết, dựng từ kỹ thuật đã
                  công bố trong bài báo (arXiv:1706.03762, arXiv:2002.04745,
                  arXiv:1910.07467, arXiv:2104.09864, arXiv:2305.13245,
                  arXiv:2002.05202).},
  howpublished = {\url{https://llm.bdsg.vn}}
}
```

Nếu bạn trích dẫn **kỹ thuật** chứ không trích kho này, xin trích thẳng các bài báo ở mục
1.2. Công của các tác giả ấy thuộc về họ, và một kho mã đứng giữa không được nhận thay.

---

## 11. Liên hệ và phiên bản thẻ

| Trường | Giá trị |
|---|---|
| Phiên bản thẻ | 3 |
| Ngày viết | 25/09/2026 · sửa 26/09/2026 |
| Sửa gì ở bản 2 | Thu phạm vi ngôn ngữ về đúng hai (Việt chính, Anh phụ); ghi lại đúng nguồn gốc kiến trúc — do BDSG viết từ kỹ thuật đã công bố trong bài báo. **Không số đo nào bị sửa theo.** |
| Sửa gì ở bản 3 | Thêm [§0](#0-hai-thu-khac-nhau-dung-lan) tách hẳn **mô hình của BDSG** khỏi **backend phục vụ trọng số Gemma 4 31B của Google** (Apache-2.0, có ghi công và liên kết); ghi lần huấn luyện đầu tiên 26/09/2026 vào §1.1 bằng đúng số đã đo; nói rõ backend **chưa chạy thật** và **chưa có đăng nhập**. **Không số đo cũ nào bị sửa theo.** |
| Ngày số liệu ngữ liệu được đo | 25/09/2026 |
| Ngày số liệu đánh giá được đo | 22/09/2026 |
| Ngày lần huấn luyện đầu tiên | 26/09/2026 — bản nghiên cứu, chưa dùng được |
| Phiên bản mô hình được mô tả | **chưa có bản phát hành** |

Thẻ này sẽ được viết lại ở M7. Cho tới lúc đó, mọi mục ghi "chưa huấn luyện — mục này
trống cho tới M7" phải giữ nguyên chữ ấy, không được điền bằng số suy đoán.
