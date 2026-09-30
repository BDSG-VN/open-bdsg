# Cài đặt Open BDSG

> Tệp này ghi theo **kết quả đo**, không theo mong đợi. Mọi dòng "chạy được" dưới đây đều
> có một lần chạy thật đứng sau. Mọi dòng "chưa" cũng vậy.

## Một câu trả lời trước khi bạn tải về

**Hôm nay kho này chưa phải một hệ điều hành chạy đủ.** Nó có phần nhân, khe cắm lĩnh
vực, bảng điều khiển, giao diện trò chuyện, kiến trúc mô hình và các cổng nghiệm thu —
còn cơ chế bật lĩnh vực theo giấy phép và phần lớn các lĩnh vực thì **chưa viết**. Bảng
ở mục 3 nói rõ từng phần.

Nếu bạn cần một hệ chạy được ngay hôm nay, đây chưa phải. Nếu bạn muốn xây một hệ điều
hành kinh doanh cho chính mình và cần một khe cắm chuẩn để từng mảng cắm vào, thì có.

## 1 · Cần gì

| | mức tối thiểu | đo được ngày 01/10/2026 |
|---|---|---|
| Python | **3.8** | chạy thật trên **3.8.10** của một hosting DirectAdmin, mã thoát **0** |
| pip | **không cần** cho lõi | chính máy đo ấy **không có pip**, lõi vẫn chạy trọn |
| Thư viện ngoài cho lõi | **0** | đọc 43 tệp `.py` trong lõi, không tệp nào nhập thư viện ngoài |
| Đĩa cho lõi | vài MB | 143 tệp, phần lớn là tài liệu và mã Python |
| torch | chỉ cho `mo-hinh/` | bản CPU: cài 45 giây, chiếm 773 MB |

Lõi là: `nhan/` · `tac-nhan/` · `phuc-vu/` · `linh-vuc/` · `cong/` · `bang-dieu-khien/`.

Con số "0 thư viện ngoài" không phải may mắn mà là một quyết định: một doanh nghiệp cài
trên hosting chia sẻ thường **không có quyền cài gói**. Lõi không cần pip thì lõi cài
được ở những nơi mà một dự án bình thường bó tay.

## 2 · Cài

```bash
git clone https://github.com/BDSG-VN/open-bdsg.git
cd open-bdsg

bash cai.sh --chi-kiem     # chỉ đo môi trường, KHÔNG cài gì, không tạo tệp nào
bash cai.sh                # cài phần mô hình rồi chạy mọi cổng nghiệm thu
```

`cai.sh` **fail-closed**: không có `|| true` ở bất kỳ đâu trong tệp. Một bước hỏng là
dừng, vì một bộ cài báo "xong" trên một hệ nửa vời còn tệ hơn một bộ cài báo lỗi — người
ta sẽ tin nó rồi mất một buổi mới biết.

Nó cũng **không tin lời khai của chính kho**: bước 2 tự đọc mọi lệnh `import` trong lõi
để kiểm rằng `requirements.txt` rỗng là đúng, chứ không chỉ đọc tệp ấy.

Muốn chạy cổng nghiệm thu thì tạo thêm danh sách danh tính cần chặn (tệp này **không**
vào git, và có lý do — xem `cong/khong-danh-tinh.py`):

```bash
cp cong/danh-tinh.mau cong/danh-tinh.local   # rồi sửa theo danh tính của bạn
```

## 3 · Phần nào chạy được — bảng đo

| thư mục | cài được | chạy được | phép đo |
|---|---|---|---|
| `nhan/` `tac-nhan/` `tich-hop/` | có | **có** | **179/179** phép kiểm đạt, mã thoát 0 |
| `phuc-vu/` | có | **có** | 0 thư viện ngoài, 10/10 tệp biên dịch, 6/6 mô-đun nhập được |
| `linh-vuc/` | có | **có** | 8 bản khai hợp lệ, **20/20** phép thử ngược đạt |
| `bang-dieu-khien/` | có | **có** | chạy thật bằng DOM giả: dựng đủ 8 ô, đúng đường dẫn |
| `cong/` | có | **có** | **7/7** cổng ĐẠT trên Python 3.8.10 |
| `trang-openos/` `trang-agent/` `trang-web3/` | có | **có** | phục vụ thật HTTP 200, 0 tham chiếu tài nguyên ngoài |
| `mo-hinh/` `huan-luyen/` | có (cần torch) | **có** | 13/13 phép kiểm kiến trúc, trên máy **không GPU** |
| `chat/` | có | **một phần** | giao diện tải được đúng từng byte, nhưng **6/8** đường `/api/*` chưa có bản hiện thực trong kho |
| `trien-khai/` (vLLM) | **chưa kiểm** | không | `yeu-cau.txt` tự khai chưa từng được cài thử; cần GPU |
| Cơ chế giấy phép, bật lĩnh vực | **chưa có** | không | chưa viết |

## 4 · Sau khi triển khai, hãy đo lại

```bash
python3 linh-vuc/do_trang_thai.py --goc https://<tên-miền-của-bạn>
```

Lệnh này gọi thật từng đường dẫn lĩnh vực rồi **tải thật từng tệp `.js`/`.css`** mà trang
khai, giải đường dẫn đúng như trình duyệt. Nó có một nhãn riêng — **`trang-trang`** — cho
đúng một trường hợp: trang trả **mã 200 nhưng tài nguyên 404**. Người dùng thấy trang
trắng, còn mọi phép kiểm chỉ nhìn mã HTTP đều báo lành.

Trường hợp ấy không hiếm. Đo trên chính hệ của BDSG ngày 01/10/2026: **5 trong 8** sản
phẩm đang tham chiếu tài nguyên bằng đường dẫn tuyệt đối, nên gộp chúng dưới một đường
dẫn mà không dựng lại là cả 5 trắng trang.

Chưa truyền `--goc` thì mọi lĩnh vực hiện **`chua-do`**. Đó là câu trả lời đúng: chưa gọi
thử lần nào thì không được nói "chạy được", và "chưa đo" khác "hỏng".

## 5 · Ba lỗi đã tìm ra bằng chính lần cài thật này

Ghi lại vì chúng cùng một họ — **công cụ đo trả lời sai thay vì báo lỗi** — và họ lỗi ấy
là thứ tốn thời gian nhất của bất kỳ ai làm tiếp.

1. **`sys.stdlib_module_names` chỉ có từ Python 3.10.** Bản đầu của `cai.sh` viết
   `getattr(sys, "stdlib_module_names", ())`; trên Python 3.8 nó trả tuple rỗng, nên
   "không gì là thư viện chuẩn" và bộ kiểm báo cả `json`, `os`, `sys` là thư viện ngoài.
   Nó trả lời sai đúng trên phiên bản cần nó nhất. Đã thay bằng phép dò thật qua
   `importlib.util.find_spec`.
2. **`Path.is_relative_to()` chỉ có từ Python 3.9.** Chỉ lộ ra ở bước 5 của lần chạy
   thật trên 3.8 — không phép kiểm cú pháp nào bắt được.
3. **Một phép quét bằng biểu thức chính quy báo "kho cần Python 3.10"** vì nó khớp dấu
   `|` bên trong chuỗi biểu thức chính quy `r"(?:run|call)"` và tưởng đó là hợp kiểu
   `X | Y`. Chạy thật trên 3.8 mới phân xử được.

## 6 · Hai bản song song, và vì sao điều đó quan trọng

`bdsg.vn` **không phải** một bản đặc biệt. Nó là **một thực thể** của chính mã nguồn này,
và BDSG là khách hàng số 0. Nguyên tắc ấy có một hệ quả cứng:

> Mọi thứ riêng của BDSG phải là **dữ liệu hoặc một lĩnh vực**, không được là một nhánh mã
> riêng. Chỗ nào hai bản lệch nhau, chỗ đó là **lỗi**.

Vì vậy khe cắm ở `linh-vuc/` chốt **trước** bản viết lại đầu tiên, không phải sau: viết
lại từng mảng nghiệp vụ là việc nhiều năm nhiều người, và nếu mỗi bản tự nghĩ ra cách cắm
riêng thì đến bản thứ ba là không ai ghép được nữa.
