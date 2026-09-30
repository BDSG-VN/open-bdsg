# Chạy mô hình BDSG trên máy của bạn

Cập nhật 26/09/2026.

Trang này viết cho **người dùng cuối**: người muốn tải mô hình về máy cá nhân và
chạy, không cần khoá API của ai. Nó nói thật máy cần gì, lệnh nào, và chỗ nào
hôm nay còn chưa có.

---

## 0. Điều phải nói trước: hôm nay chưa có gì để tải

**BDSG chưa huấn luyện trọng số nào.** Không có tệp mô hình để tải về, không có
điểm đánh giá của mô hình BDSG, không có tốc độ sinh chữ đã đo.

Dịch vụ đang chạy tại `llm.bdsg.vn` tự khai `bdsg_la_trong_so_bdsg = false` cho
**mọi** mã mô hình. Thứ chạy ở đó là **truy hồi** (`pg_trgm` + `tsvector` —
*không phải* vector, vì cổng mô hình nội bộ không có mô hình nhúng nào) đặt
trước một mô hình của bên thứ ba. Hai mã công khai: `openbiz-vn-chat` và
`openbiz-vn-reasoner`; `bdsg-ai-v1` và `bdsg-ai-v1-suy-luan` là tên cũ, vẫn
nhận vĩnh viễn như bí danh.

Vậy trang này để làm gì: nó là **hợp đồng kỹ thuật viết trước**. Máy cần gì,
lệnh ra sao, và những chỗ đã biết trước là sẽ vướng — để khi có trọng số thật
thì không phải dò lại từ đầu.

Mọi con số bộ nhớ dưới đây là **tính ra** từ kiến trúc
(`huan-luyen/cau-hinh/tinh_tham_so.py`), **chưa đo trên máy thật**. Chỗ nào
chưa đo đều ghi rõ là chưa đo.

---

## 1. Máy cần gì

Ba cấu hình trong `huan-luyen/cau-hinh/`. Tất cả dùng chung một từ vựng
24.576 và cùng trần ngữ cảnh 2.048 token.

| | `nho.json` | `vua.json` | `lon.json` |
|---|---:|---:|---:|
| Tham số | **36,18 M** | 119,56 M | 295,75 M |
| hidden / lớp | 512 / 8 | 768 / 16 | 1024 / 24 |
| đầu q / đầu kv | 8 / 4 | 12 / 4 | 16 / 4 |
| Trọng số fp16 | **69,0 MiB** | 228,0 MiB | 564,1 MiB |
| Trọng số fp16, đọc theo MB thập phân | **72,4 MB** | 239,1 MB | 591,5 MB |
| Trọng số fp32 | 138,0 MiB | 456,1 MiB | 1.128,2 MiB |
| Bộ đệm KV mỗi token (fp16) | 8,0 KiB | 16,0 KiB | 24,0 KiB |
| Bộ đệm KV ở 2.048 token | 16,0 MiB | 32,0 MiB | 48,0 MiB |
| Bảng cos/sin RoPE lúc chạy | 1,0 MiB | 1,0 MiB | 1,0 MiB |
| **RAM để CHẠY (fp32)** | **~1 GB** | ~1,5 GB | ~2,5 GB |
| **RAM/VRAM để HUẤN LUYỆN** | ~1,5 GB | ~4 GB | ~10 GB |

**Đơn vị trong bảng**: MiB = 1024² byte, KiB = 1024, GiB = 1024³. Kho tính theo
luỹ thừa 2 vì câu hỏi thật là *có vừa RAM/VRAM không*. Hàng “đọc theo MB thập
phân” có mặt vì **kích thước tệp tải về** thì quen đọc theo 1e6 byte — cùng một
lượng byte, hai cách đọc. `mo-hinh/cau_hinh.py` in theo MB thập phân, nên số
bên đó lớn hơn 4,86 %; đó **không** phải hai kết quả khác nhau.

**Cách tính bộ đệm KV**: `2 (K và V) × số_lớp × num_key_value_heads × head_dim ×
2 byte`. Với `nho`: `2 × 8 × 4 × 64 × 2 = 8.192` byte mỗi token. Đây là chỗ
**GQA trả công**: `nho` có 8 đầu truy vấn nhưng chỉ 4 đầu khoá/giá trị, nên bộ
đệm còn một nửa so với kiểu chú ý đầy đủ.

**Cách tính cột huấn luyện**: AdamW giữ 16 byte mỗi tham số (bản trọng số fp32 4
+ gradient 4 + hai moment 4+4). Với `nho` đó là 0,54 GiB. Cột trên đã cộng thêm
phần dôi cho activation và cho chính PyTorch, nhưng **phần dôi ấy là ước lượng,
chưa đo** — activation phụ thuộc kích thước lô và độ dài chuỗi. Coi cột này là
**mức sàn để loại trừ**, không phải mức bảo đảm.

### Có cần GPU không

**Không, với `nho`.** 138 MiB trọng số fp32 chạy được trên CPU của máy tính xách
tay thông thường, và huấn luyện nó cũng vừa trên máy 8 GB RAM.

**Tốc độ sinh chữ thì chưa đo.** Không hứa số token/giây nào cho đến khi có
trọng số thật để bấm giờ.

Một kinh nghiệm hạ tầng của BDSG có liên quan, nhưng **không suy ra được**: trên
VPS của BDSG, mô hình 7B chạy **0,3 token/giây** vì nghẽn băng thông RAM
(~1,4 GB/s). `nho` nhỏ hơn 7B khoảng **190 lần**, nên tình huống ấy không lặp
lại — nhưng con số cụ thể vẫn phải đo, không được suy.

---

## 2. Cài đặt

```bash
git clone <kho BDSG>
cd open-bdsg
python3 -m venv .venv && source .venv/bin/activate
pip install tokenizers
```

Đến đây đã đủ để chạy **toàn bộ khâu chuẩn bị dữ liệu và từ vựng**: chúng dùng
Python thuần + `tokenizers`, không cần torch.

Muốn **huấn luyện** hoặc **chạy mô hình**, cài thêm PyTorch:

```bash
pip install torch          # bản CPU cho máy cá nhân
```

**Vì sao kho này cố ý KHÔNG ghi `torch` vào danh sách phụ thuộc chung:** bản
torch cho CPU, cho GPU NVIDIA và cho Apple Silicon là ba gói khác nhau. Ghi cứng
một bản là chọn thay cho người dùng, và chọn sai. Chọn bản đúng máy mình theo
hướng dẫn ở pytorch.org.

---

## 3. Chạy: chọn một trong hai đường

Khi đã có trọng số, có hai đường, và chúng phục vụ hai nhu cầu khác nhau.

### 3.1. Đường A — chạy thẳng bằng mã của kho này

Không cần công cụ ngoài. Kiến trúc trong `mo-hinh/` có sẵn phương thức sinh chữ:

```python
import importlib.util, sys, torch
from tokenizers import Tokenizer

spec = importlib.util.spec_from_file_location(
    "mo_hinh", "mo-hinh/__init__.py", submodule_search_locations=["mo-hinh"])
mh = importlib.util.module_from_spec(spec)
sys.modules["mo_hinh"] = mh
spec.loader.exec_module(mh)

cfg = mh.CauHinhBDSG.tu_json("huan-luyen/cau-hinh/nho.json")
mo_hinh = mh.BDSGChoNgonNgu(cfg)
mo_hinh.load_state_dict(torch.load("diem-dung.pt", map_location="cpu")["trong_so"])
mo_hinh.eval()

tok = Tokenizer.from_file("tu-vung/tokenizer.json")
loi_nhac = "<|mo-luot|>nguoi\nNgành nghề kinh doanh chính là gì?<|dong-luot|>\n<|mo-luot|>tro-ly\n"
ids = torch.tensor([tok.encode(loi_nhac).ids])
ra = mo_hinh.sinh(ids, so_token_moi=200, nhiet_do=0.7, top_p=0.9,
                  eos_token_id=tok.token_to_id("<|dong-luot|>"))
print(tok.decode(ra[0].tolist()))
```

**Chuỗi lời nhắc phải đúng định dạng hội thoại của BDSG** — xem mục 4. Sai định
dạng thì mô hình vẫn trả lời, chỉ là trả lời kém, và không có lỗi nào báo.

**Giới hạn đã biết, ghi ở chính mã của `mo-hinh/`:** `sinh()` yêu cầu các chuỗi
trong một lô phải **cùng độ dài**, vì kiến trúc chưa có mặt nạ đệm. Sinh từng
chuỗi một thì không vướng.

### 3.2. Đường B — xuất ra định dạng công cụ suy luận đọc được

Đây là đường dành cho người muốn chạy bằng công cụ cục bộ quen thuộc.
`mo-hinh/xuat_hf.py` ghi ra `config.json` + `model.safetensors` theo bố cục
trọng số phổ biến, để bộ chuyển đổi sang GGUF đọc được:

```bash
python3 mo-hinh/xuat_hf.py \
    --cau-hinh huan-luyen/cau-hinh/nho.json \
    --diem-dung out/tinh-chinh-nho/diem-dung.pt \
    --ra ./bdsg-nho-xuat
```

Sau đó dùng bộ chuyển đổi GGUF của công cụ suy luận bạn chọn, rồi nạp tệp GGUF
ấy như mọi mô hình khác.

**Trường `architectures` trong `config.json` là khai báo về CÁCH SẮP XẾP TRỌNG
SỐ, không phải khai báo về tác giả.** Nó nói "trọng số của tôi nằm theo bố cục
đã biết này" để công cụ khác đọc được. Mã trong kho này do BDSG viết; bố cục
trọng số thì cố ý làm cho trùng một bố cục phổ biến, vì đó là điều kiện để bạn
chạy được. Chi tiết và ba chỗ hỏng-mà-không-báo của bước xuất nằm ở đầu
`mo-hinh/xuat_hf.py`.

---

## 4. Định dạng hội thoại — phải đúng, không có lỗi nào báo nếu sai

Mô hình được tinh chỉnh trên đúng một khuôn. Ba token đặc biệt:

| id | token | việc |
|---:|---|---|
| 0 | `<\|het-van-ban\|>` | ngăn hai văn bản khác nhau, và làm token đệm |
| 1 | `<\|mo-luot\|>` | mở một lượt nói |
| 2 | `<\|dong-luot\|>` | đóng một lượt nói |

Hai vai hợp lệ, **và chỉ hai**: `nguoi` và `tro-ly`. Không có vai hệ thống.

Một lượt hỏi–đáp đầy đủ:

```
<|mo-luot|>nguoi\n{câu hỏi}<|dong-luot|>\n<|mo-luot|>tro-ly\n{trả lời}<|dong-luot|>\n
```

Khi **hỏi**, bạn dừng ở `<|mo-luot|>tro-ly\n` và để mô hình viết tiếp. Đặt
`eos_token_id` là id của `<|dong-luot|>` để nó dừng đúng chỗ.

**Vì sao phải kỹ:** mô hình chỉ được tính mất mát trên phần trả lời của `tro-ly`
và trên chính token `<|dong-luot|>` kết thúc lượt ấy (xem
`huan-luyen/tinh_chinh.py`). Đưa vào một khuôn khác thì bạn đang hỏi mô hình ở
một phân bố nó chưa từng học. Nó vẫn trả lời. Chỉ là trả lời kém hơn, và không
có ngoại lệ nào được ném ra.

---

## 5. Tự huấn luyện, nếu bạn muốn

Cả hai bước đều chạy được trên máy cá nhân với cấu hình `nho`.

```bash
# 1. Tiền huấn luyện
python3 huan-luyen/huan_luyen.py \
    --du-lieu  duong/dan/pretrain.jsonl \
    --cau-hinh huan-luyen/cau-hinh/nho.json \
    --tu-vung  duong/dan/tu-vung \
    --thu-muc-ra out \
    --max-seq-len 512 --batch 8 --tich-luy 4 --ky 1

# 2. Tinh chỉnh theo chỉ dẫn
python3 huan-luyen/tinh_chinh.py \
    --du-lieu  duong/dan/sft.jsonl \
    --cau-hinh huan-luyen/cau-hinh/nho.json \
    --tu-vung  duong/dan/tu-vung \
    --tu-diem-dung out/tien-huan-luyen-nho/diem-dung.pt \
    --thu-muc-ra out --ky 2
```

Cả hai **tự chọn thiết bị**: CUDA nếu có, rồi MPS (Apple Silicon), rồi CPU. Ép
tay bằng `--thiet-bi cpu|cuda|mps`.

Cả hai **lưu điểm dừng định kỳ và tiếp tục được**: thêm `--tiep-tuc` vào đúng
lệnh cũ. Bấm Ctrl-C giữa chừng cũng lưu trước khi thoát.

### Ba lệnh nên chạy TRƯỚC khi tiêu một giây GPU nào

```bash
# a. Phép đếm tham số có đúng số học không
python3 huan-luyen/cau-hinh/tinh_tham_so.py --tu-kiem

# b. Lề một bước giữa bộ huấn luyện và kiến trúc có khớp không
python3 huan-luyen/huan_luyen.py --tu-kiem-dich --cau-hinh huan-luyen/cau-hinh/nho.json

# c. Mặt nạ mất mát có phủ đúng phần trả lời không — NHÌN BẰNG MẮT
python3 huan-luyen/tinh_chinh.py --du-lieu sft.jsonl --tu-vung tu-vung \
    --cau-hinh huan-luyen/cau-hinh/nho.json --xem-mat-na 3
```

Lệnh (b) và (c) tồn tại vì hai lỗi chúng bắt đều thuộc họ **hỏng mà không báo**:
lệch lề một bước, hoặc mặt nạ phủ sai chỗ, đều làm mất mát giảm đều và đồ thị
đẹp, chỉ có kết quả là hỏng.

---

## 6. Bốn chỗ đã biết trước là sẽ vướng

**1. `vocab_size` trong cấu hình phải khớp tuyệt đối với từ vựng thật.**
Lệch kiểu "cấu hình lớn hơn từ vựng" **không báo lỗi gì cả** — nó chỉ tạo một
mảng embedding chết, không bao giờ được học. Cả `huan_luyen.py` lẫn
`tinh_chinh.py` đều kiểm và **dừng hẳn** nếu lệch.

**2. Thư mục `mo-hinh` có dấu gạch ngang nên không `import` thẳng được.**
Tên mô-đun Python không được chứa gạch ngang. Phải nạp bằng `importlib` theo
đường dẫn tệp — xem đoạn mã ở mục 3.1. Bộ huấn luyện đã làm sẵn việc này.

**3. Trên CPU, đừng ép fp16.** PyTorch chạy fp16 trên CPU rất chậm và một số
phép chưa hỗ trợ. Bộ huấn luyện **mặc định tắt** autocast trên CPU và trên MPS,
và chỉ bật trên CUDA khi bạn thêm `--amp`. Đổi lại là trọng số chiếm gấp đôi RAM
(`nho`: 138 MiB thay vì 69 MiB) — vẫn thoải mái trên máy cá nhân.

**4. Đừng mở cổng ra toàn bộ card mạng.** Nếu bạn bọc mô hình sau một máy chủ
HTTP, đặt `host="127.0.0.1"` chứ đừng `0.0.0.0`. Ở quán cà phê hay mạng công ty,
ai cùng mạng cũng gọi được mô hình của bạn.

---

## 7. Đặt kỳ vọng cho đúng

Mô hình 36 M–296 M tham số **không phải** trợ lý đa năng. Hai hạn chế đã biết
trước, và chúng thuộc về quy mô chứ không thuộc về mã:

- **mô hình bịa ra kiến thức nó không có**;
- kiến thức càng xa lĩnh vực đã tinh chỉnh thì càng không đáng tin.

Đường cơ sở BDSG **đo được** (bộ M3, 227 câu, 22/09/2026). Đây là điểm của **hệ
truy hồi + mô hình bên thứ ba** đang chạy, **không phải** của mô hình sẽ huấn
luyện:

| Nhóm câu | Điểm | Số câu |
|---|---:|---:|
| Nghiệp vụ trong kho | 0,636 | 111 |
| Nghiệp vụ ngoài kho | 0,539 | 31 |
| Lợi ích của truy hồi | +0,097 | — |
| Câu bẫy chống bịa | 0,953 | 60 |
| Tiếng Việt tổng quát | 0,908 | 25 |

Một mô hình 36 M huấn luyện từ đầu **gần như chắc chắn sẽ thấp hơn các số này**
ở giai đoạn đầu. Đó không phải thất bại — đó là điều đã biết trước khi bắt đầu.

Giá trị của mô hình nhỏ chạy cục bộ nằm ở chỗ **dữ liệu không rời khỏi máy** và
**không tốn tiền gọi API**, không nằm ở chỗ nó khôn hơn.

Khi có trọng số thật, **mọi con số ở trang này phải được đo lại và thay**, kèm
ngày đo.
