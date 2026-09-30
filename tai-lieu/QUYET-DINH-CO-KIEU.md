# Quyết định kiến trúc — BDSG làm mô hình quyết định, không làm mô hình sinh văn

Viết ngày **01/10/2026**. Thay thế hướng "phục vụ Gemma 4 31B" trong
[`GEMMA4-31B.md`](GEMMA4-31B.md) và [`LO-TRINH-LORA.md`](LO-TRINH-LORA.md) ở
vai trò **mô hình chính của hệ điều hành**. Hai tài liệu ấy vẫn đúng như tài
liệu kỹ thuật và vẫn giữ lại; chúng chỉ không còn là đường đi chính.

> **Ba câu đủ để hiểu quyết định này**
>
> 1. Mục tiêu sinh văn đòi ~538 triệu token cho 26,88 triệu tham số. BDSG có
>    2,07 triệu. Thiếu **260 lần**, và không mẹo nào bù được.
> 2. Mục tiêu quyết-định-có-kiểu không đo bằng token mà bằng **số ví dụ có
>    nhãn** — thứ mà bộ luật tất định của BDSG sinh ra đúng theo định nghĩa,
>    bằng tiếng Việt, không giới hạn.
> 3. Trọng số BDSG đã huấn luyện **không mất gì**: 74/74 tensor thân nạp
>    được sang mô hình quyết định, cộng 4.620 tham số đầu ra.

---

## 1 · Vì sao bỏ hướng "phục vụ mô hình 31 tỷ của người khác"

Không phải vì kỹ thuật sai. `trien-khai/chay-vllm.sh` đạt 45/45 phép tự kiểm,
và Gemma 4 31B là Apache-2.0 nên phục vụ nó là hợp pháp và có ghi công đầy đủ.
Bỏ vì **ba lý do đo được**, không vì sở thích:

**(a) Một hệ điều hành không được mượn nhân của người khác.** Nếu thứ trả lời
mọi câu là trọng số của Google thì `bdsg_la_trong_so_bdsg` sẽ mãi là `false` —
đúng như API tại `llm.bdsg.vn` đang tự khai cho **mọi** mã mô hình. Hệ điều
hành cho doanh nghiệp Việt Nam mà nhân là của nước ngoài thì chủ quyền dữ liệu
chỉ là cách nói.

**(b) Suy luận sinh văn không trả nổi tiền ở quy mô 100 triệu agent.** Đo trên
máy BDSG ngày 01/10/2026:

| cách quyết định | độ trễ một quyết định | đo ở đâu |
|---|---|---|
| laya trên CPU 6 lõi | **59.785 – 121.125 ms** | container `bdsg/thu-laya:1`, 4 tình huống |
| bộ luật tất định của BDSG | **20 ms** trung vị (nhỏ nhất 9) | cổng nội bộ `127.0.0.1:3100`, 29 lượt |

Chênh **3.000–6.000 lần**. Một mô hình sinh văn 31 tỷ tham số trên GPU sẽ
nhanh hơn laya-trên-CPU rất nhiều, nhưng nó vẫn là **suy luận theo từng token**,
và 100 triệu agent nhân với bất kỳ số giây nào cũng ra một con số không ai trả.

**(c) Sinh văn thì bịa được; phân loại thì không.** `CLAUDE.md` của dự án cấm
bịa số. Một đầu phân loại trả một trong N nhãn đã khai — nó **không thể** phát
minh ra một con số hay một cái tên ngoài tập nhãn. Tính chất ấy có được từ
kiến trúc, không phải từ lời nhắc.

---

## 2 · Khoảng thiếu dữ liệu: con số làm đổi hướng

Bản trọng số BDSG huấn luyện 26/09/2026 (xem
[`LAN-HUAN-LUYEN-DAU-TIEN.md`](LAN-HUAN-LUYEN-DAU-TIEN.md)):

| | số đo |
|---|---|
| tham số | **26.878.464** (công thức và phép đếm khớp tuyệt đối) |
| ngữ liệu | **2.068.295 token** |
| ngữ liệu mục tiêu sinh văn cần | **537.569.280 token** (Hoffmann 2022, ~20 token/tham số) |
| **thiếu** | **260 lần** |
| perplexity học / kiểm | 19,9 / **102,5** — quá khớp **5,2 lần** |

Perplexity kiểm gấp 5,2 lần perplexity học không phải lỗi cài đặt. Đó là điều
phải xảy ra khi một mô hình 26,88 triệu tham số nhìn 2,07 triệu token: nó học
thuộc. Ba đường ra khỏi tình trạng ấy, và hai đường đầu đều không đi được:

- **Gom thêm 536 triệu token tiếng Việt.** Không có trong tay, và ngữ liệu
  tiếng Việt chất lượng ở quy mô ấy là một dự án riêng nhiều năm.
- **Thu nhỏ mô hình cho khớp dữ liệu.** 2,07 triệu token chỉ đỡ nổi ~100 nghìn
  tham số. Mô hình cỡ ấy không sinh được câu tiếng Việt dùng được.
- **Đổi mục tiêu.** ← đường này.

---

## 3 · Đổi mục tiêu thì khoảng thiếu biến mất

Mục tiêu sinh văn đo bằng token vì mô hình phải học **phân bố của cả ngôn ngữ**.
Mục tiêu quyết-định-có-kiểu chỉ cần học **một hàm từ tình huống sang nhãn**. Số
liệu cần không còn là token mà là **ví dụ có nhãn**, và nhãn ở đây có nguồn:

`LocalDecisionProvider` — bộ luật tất định đang chạy thật trên `agent.bdsg.vn` —
trả về quyết định **kèm tên luật đã quyết** (`nguon`). Nhãn do luật sinh ra thì
đúng theo định nghĩa. Nó bằng tiếng Việt. Và số lượng không giới hạn.

Đo ngày 01/10/2026 qua cổng HTTP nội bộ: trung vị **20 ms** một quyết định. Nên
một triệu ví dụ có nhãn mất ~5,6 giờ một luồng, ~42 phút với 8 luồng — và gọi
trực tiếp hàm luật (không qua HTTP, không ghi nhật ký kiểm toán) thì rẻ hơn
nhiều, vì phần lớn 20 ms ấy là Fastify và một lần ghi cơ sở dữ liệu.

**Điều này không có nghĩa mô hình chỉ học thuộc bộ luật.** Nếu mô hình chỉ sao
lại luật thì đã không cần mô hình — dùng luật là xong, và nhanh hơn. Giá trị
nằm ở chỗ khác: luật cần **số đã bóc tách** (ngân sách, số ngày) mới chạy được,
còn mô hình nhận **câu tiếng Việt thô**. Hôm nay bước bóc tách làm bằng biểu
thức chính quy, và nó trả `null` khi gặp cách viết ngoài quy ước — ví dụ
"1.5 tỷ" không khớp quy ước nào nên bị trả về null thay vì đoán. Mô hình quyết
định là thứ xử lý được **phần đuôi dài** mà biểu thức chính quy không phủ,
trong khi vẫn trả về đúng kiểu dữ liệu ấy.

---

## 4 · Kiến trúc: giữ thân, đổi đầu ra

[`../mo-hinh/dau_quyet_dinh.py`](../mo-hinh/dau_quyet_dinh.py) giữ nguyên
`embed_tokens` + `layers` (`KhoiGiaiMa`) + `norm` của
[`kien_truc.py`](../mo-hinh/kien_truc.py), và thay `lm_head` bằng các đầu phân
loại có kiểu. Ba kiểu, lấy theo hình dạng đã công bố của thuật toán quyết định
có kiểu:

| kiểu | đầu ra | độ tin cậy tính thế nào |
|---|---|---|
| `choice` | softmax trên N nhãn | xác suất của nhãn thắng |
| `noul` | sigmoid, một xác suất | `\|p − 0,5\| × 2` — xa 0,5 bao nhiêu thì chắc bấy nhiêu |
| `score` | softmax trên N mức, trả kỳ vọng `Σ i·pᵢ` | `1 − σ/σ_max`, **không** phải xác suất mức cao nhất |

Dòng cuối là một chi tiết đáng nói. Một phân bố dồn vào hai mức 0 và 4 có kỳ
vọng đúng 2 nhưng **không hề chắc mức 2** — nó đang nói "hoặc rất thấp hoặc rất
cao, tôi không biết". Lấy xác suất mức cao nhất làm độ tin cậy sẽ che mất đúng
trường hợp ấy, nên ở đây dùng độ lệch chuẩn đã chuẩn hoá.

### Số tham số — đếm thật bằng `parameters()`

| cấu hình | tham số | riêng các đầu | fp32 |
|---|---|---|---|
| `quyet-dinh-nho` (256 ch · 4 lớp) | **4.592.140** | 2.316 | 17,5 MiB |
| `quyet-dinh-vua` (384 ch · 6 lớp) | **12.198.156** | 3.468 | 46,5 MiB |
| `quyet-dinh-lon` (512 ch · 8 lớp) | **26.883.084** | 4.620 | 102,6 MiB |

`quyet-dinh-lon` trùng khít thân bản đã huấn luyện, nên **74/74 tensor thân nạp
lại được** (kiểm bằng `nap_than_tu_ngon_ngu()`, chỉ bỏ `lm_head.weight`). Trọng
số đã bỏ 53 phút 54 giây ra huấn luyện không mất gì cả.

Và `quyet-dinh-nho` là con số đáng chú ý cho quy mô 100 triệu agent: **4,59
triệu tham số, 17,5 MiB ở fp32** — nhỏ đến mức nhiều bản nạp được cùng lúc trên
một máy.

---

## 5 · Hai khiếm khuyết của laya, chặn bằng mã chứ không bằng tài liệu

Đo laya ngày 01/10/2026 trên máy BDSG (container riêng, 6 lõi CPU, không đụng
dịch vụ đang chạy). Hình dạng `choice`/`noul`/`score` là thứ đáng học. Hai thứ
không đáng mang theo:

**(a) Độ tin cậy không hiệu chuẩn mà vẫn phát ra.** laya tự in:

> `this checkpoint ships invalid temperatures or values outside [0.5, 5]; using
> choice:11+=0.1005… -> 0.5. Treat confidence from the affected entries as
> uncalibrated.`

Cảnh báo ấy ra **stderr**, còn `confidence` vẫn nằm trong kết quả JSON như
thường. Ai đọc kết quả sẽ không thấy cảnh báo. Ở
`dau_quyet_dinh.py`, nhiệt độ bị kẹp cứng vào [0,5 ; 5,0] trong `forward`,
`kiem_hieu_chuan()` liệt kê mọi đầu lệch, và trường **`hieu_chuan_dung` đi kèm
từng đáp án** — không thể nhận một độ tin cậy mà không biết nó có hiệu chuẩn
hay không. Đã kiểm: đặt nhiệt độ 0,1006 thì `hieu_chuan_dung = False` xuất hiện
ngay trong đáp án.

**(b) Không nhận ra tiếng Việt.** Cả 4 tình huống tiếng Việt đều cho
`language: null`, `language_undecided: true`, và laya rơi về checkpoint
`multilingual` như **lưới an toàn** ("not safe for the English checkpoint"),
không phải vì hiểu tiếng Việt. Đáp án đúng, nếu có, là tình cờ. Ở đây không có
bước đoán ngôn ngữ nào: tokenizer là bộ 6.400 token do BDSG luyện trên chính
ngữ liệu tiếng Việt của mình.

Kèm theo, `score` của laya không phân biệt được gì trên 4 tình huống của BDSG:
1,40 – 1,87 (giãn 0,47) với độ tin cậy 0,199 – 0,369. Nó không tách được *200
triệu / 2 năm* khỏi *50 tỷ / 7 ngày*. Còn việc nó làm đúng thì cũng phải ghi:
hồ sơ 50 tỷ / 7 ngày là hồ sơ **duy nhất** nó đòi người duyệt (0,67).

---

## 6 · Luật về con số: không ai được viết bằng tay

BDSG bỏ cách nói "30 tỷ tham số". Không phải bằng cách sửa câu chữ — câu chữ sẽ
lại lệch ở bản cập nhật sau — mà bằng cách **lấy quyền viết số ra khỏi tay
người**:

[`../mo-hinh/con_so_thuc.py`](../mo-hinh/con_so_thuc.py) đếm từ
`parameters()` hoặc từ tensor trong tệp `.pt`, rồi phát ra
`cong/con-so-thuc.json`. README, thẻ mô hình và trang web **đọc tệp ấy**. Muốn
đổi con số thì phải đổi mô hình.

Ba trường luôn đi cùng nhau, và trường thứ ba là trường quan trọng nhất:

- `tham_so` — đếm được, không tính ra
- `muc_tieu` — `sinh-van` hay `quyet-dinh-co-kieu`; **hai mục tiêu này không so
  được với nhau bằng số tham số**
- `dung_duoc` — đã đạt cổng nghiệm thu chưa

Không có trường thứ ba thì một con số hoàn toàn đúng vẫn dựng nên một lời khai
sai: bản 26.878.464 tham số quá khớp 5,2 lần **là** 26,88 triệu tham số. Con số
đúng, kết luận sai.

Tệp `con_so_thuc.py` còn chặn một lỗi đếm cụ thể: với `tie_word_embeddings`,
hai khoá `state_dict` khác nhau trỏ **cùng một vùng nhớ**, nên đếm theo khoá sẽ
thổi con số lên. Nó đếm theo `data_ptr()` của storage.

---

## 7 · Còn chưa làm — ghi ra để không ai tưởng đã xong

| việc | trạng thái 01/10/2026 |
|---|---|
| Kiến trúc đầu quyết định | **đã viết, đã kiểm bằng torch** (đếm tham số, lan truyền ngược 83/83, nạp thân 74/74, bắt được nhiệt độ lệch) |
| `con_so_thuc.py` | **chạy thật**, khớp công thức độc lập của kho ở cả 3 cấu hình sinh văn |
| Sinh nhãn từ bộ luật tất định | **chưa làm** — đã đo được chi phí (20 ms/quyết định qua HTTP) nhưng chưa sinh tập nào |
| Huấn luyện mô hình quyết định | **chưa chạy lần nào** |
| Bộ đánh giá riêng cho quyết định | **chưa có**. Bộ 227 câu hiện tại đo truy hồi, không đo quyết định |
| Nối vào `agent.bdsg.vn` | **chưa** — thanh quyết định hôm nay chạy bằng luật tất định, `nhan_tang = "luật tất định"` |
| Đo trên GPU | **chưa có GPU**. Mọi số bộ nhớ trong kho vẫn là số **tính ra** |

Một điều nữa phải nói thẳng: **bỏ Gemma là bỏ khả năng nói chuyện tự do.**
`chat.bdsg.vn` hôm nay trả lời có trích dẫn nhờ một mô hình bên thứ ba, và
`llm.bdsg.vn` tự khai `bdsg_la_trong_so_bdsg = false` cho mọi mã mô hình. Bỏ nó
thì chat còn hai lối: truy hồi cộng **mẫu câu** (không cần mô hình, vẫn có
trích dẫn, vẫn tiếng Việt đúng), hoặc chờ mô hình BDSG đủ dùng. Mô hình quyết
định **không** thay được việc ấy — nó trả nhãn, không trả câu.
