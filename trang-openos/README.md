# trang-platform — trang của openos.bdsg.vn

Trang tĩnh, không có bước đóng gói, không một dòng JavaScript nào. Triển khai
bằng cách chép thẳng `index.html` vào docroot.

Cùng khuôn với `trang-agent/` và `trang-web3/`: cùng bảng màu Brand Guidelines,
cùng Roboto, cùng lối viết, cùng quy tắc "chưa đo thì nói là chưa đo".

## Vì sao không có JavaScript

Chính sách bảo mật nội dung của vhost khai `script-src 'none'`. Khai đúng như
vậy thì một ngày nào đó có ai chèn script vào, trang hỏng **ngay** thay vì chạy
âm thầm. Một lời khai rộng tay hơn sự thật là một lời khai vô dụng.

Tài nguyên ngoài duy nhất: Google Fonts (`fonts.googleapis.com`,
`fonts.gstatic.com`). Không ảnh ngoài, không phân tích, không nhúng gì khác.

Đo lại bằng một lệnh:

```
grep -c '<script' trang-platform/index.html     # phải ra 0
```

## Trang này nói gì

`openos.bdsg.vn` là **trang sản phẩm của BDSG OS** — hệ điều hành gồm những
nhân viên agent làm theo bốn chặng **Tư vấn → Triển khai → Vận hành → Kinh
doanh**, mã nguồn mở Apache-2.0 để cơ quan nhà nước, doanh nghiệp và tổ chức xã
hội tự cài trên máy chủ của mình.

### Phạm vi mở nguồn: chỉ hệ điều hành

Thứ được phát hành là **hệ điều hành** — nhân quyền, trí nhớ agent, vòng lặp
agent, chương trình huấn luyện. Những nền tảng nghiệp vụ BDSG đang vận hành là
thứ hệ điều hành này **điều khiển**, không phải thứ được phát hành kèm — đúng
như một hệ điều hành máy tính được mở nguồn mà không phát hành kèm mọi phần mềm
chạy trên nó.

Vì thế trang **không** có bảng "sản phẩm nào không mở nguồn được". Những nền
tảng ấy chưa bao giờ nằm trong phạm vi, nên liệt kê chúng ra như một khiếm
khuyết là tự nhận một tội không có. Chúng xuất hiện trên trang đúng một lần,
với đúng một vai trò: **bằng chứng** rằng hệ điều hành này được viết để điều
khiển thứ có thật, ở quy mô thật.

## Câu then chốt của trang: "Chạy được, nhưng chưa chạy như mô tả"

Mục trạng thái đặt **ngay sau phần mở đầu**, ngang hàng với phần giới thiệu,
không giấu xuống cuối — cùng lý do đã viết trong `trang-web3/README.md`: một
trang sản phẩm mở đầu bằng lời hứa rồi nhắc chữ "sắp" ở chân trang thì người
đọc đã tin xong từ màn hình đầu. Thứ tự là một lời khai.

Hai vế đều là phép đo ngày 26/09/2026 và **không mâu thuẫn nhau**:

| Vế | Phép đo |
|---|---|
| **Chạy được** | Từ bản giải nén sạch của nhánh chính tới câu trả lời chảy từng chữ qua HTTP: **7 giây**, **0** lệnh `pip install`. **291** phép thử ĐẠT chỉ bằng thư viện chuẩn Python; thêm `torch` thành **304**, vòng huấn luyện chạy thật trên máy xách tay trong **40 giây**. `phuc-vu/may_chu.py` (**1.205** dòng) phục vụ **6/7** đường hợp đồng — đường thiếu là `POST /api/dang-xuat`, thiếu có chủ ý vì bản này chưa có đăng nhập. |
| **Chưa chạy như mô tả** | Số lần một gói trong kho nhập một gói **khác** trong cùng kho: **0**. `phuc-vu/` **không nhập** `nhan/`, nên lời gọi qua máy chủ **không** đi qua nhân: không phép thử quyền, không dòng nhật ký nào của nhân. Số lời gọi công cụ thật đã đi qua nhân: **0**. Trình điều khiển thật cho một nền tảng BDSG: **0**. `phuc-vu/rag.py` (**657** dòng) là mã chết trên đường chạy. |

### ⚠ Một câu TUYỆT ĐỐI không được chép vào trang

Trang `bdsg.vn/open-bdsg` đang chạy viết nguyên văn:

> "mọi lời gọi công cụ đều đi qua nhân, nên nó luôn có một chủ thể, một phép thử
> quyền và một dòng nhật ký"

Câu ấy đúng như mô tả **thiết kế** và sai như mô tả **hệ đang chạy** — mà nó
được viết ở thì hiện tại. Trang này cố ý nói ra cả cái bẫy ấy, trong chính mục
trạng thái. Người sửa trang về sau đừng "dọn cho gọn" bằng cách bỏ nó đi.

### Ba câu khác nhau, và chuỗi suy luận đã sai một lần

README gốc kho viết "chưa có `requirements.txt`". Từ đó suy ra "chưa cài được",
rồi suy tiếp "chưa chạy được" — **cả hai bước suy đều sai**. Mã này không cần
cài gì để chạy, nên nó không cần một bản kê phụ thuộc để chạy. Bản nháp đầu của
trang này đã viết sai đúng theo chuỗi ấy và phải sửa lại. Giữ ghi chú này vì cái
bẫy sẽ quay lại với người đọc tiếp theo.

Và `requirements.txt` cũng không hẳn là "không có": `trien-khai/yeu-cau.txt` có
**88** dòng, ghim phiên bản — nhưng **chỉ phủ nhánh vLLM**. Nhánh `torch` mới là
lỗ thật.

## Bốn chỗ trang nói thẳng điều chưa có

Liệt kê ra đây để lần sửa sau không ai vô tình làm mềm mất chúng.

1. **Nhân chưa nằm trên đường chạy** — mục riêng, đặt thứ hai trên trang. Đây là
   điều quan trọng nhất trên cả trang.
2. **Xã hội số: CHƯA trả lời được.** Hai khu vực kia trả lời được một phần; khu
   vực này thì không, và thẻ ghi thẳng "chưa" thay vì nặn ra một câu chuyện dùng
   thử.
3. **Bản cloud và bản tải về: cả hai đều CHƯA CÓ**, không có mốc thời gian nào.
   Có một khối cảnh báo nói rõ trang không nhận đăng ký, không bán gì, không có
   danh sách chờ.
4. **Khoảng cách tới "chạy đúng như mô tả": ước 2–3 ngày công** — ghi rõ đây là
   ước lượng của người vừa đo, không phải cam kết, không gắn với ngày nào.

Con số 2–3 ngày công nằm trên trang vì nó là phần thông tin hữu ích nhất của cả
mục: khoảng cách này là **một sợi dây**, không phải một chương trình nhiều
tháng. Bỏ nó đi thì mục trạng thái đọc như một lời tự thú mà không có lối ra.

## Con số trên trang, và cách đo lại

Mọi con số là phép đo có ngày, hoặc một phép chia từ những số đo ấy. Không có
con số nào được làm tròn lên.

| Con số | Nguồn / cách đo lại |
|---|---|
| **28.755** dòng Python · **59** tệp · **9.341** dòng (32,5 %) là bài tự kiểm | đếm dòng kho này, 26/09/2026 |
| `nhan/` **7.116** · `tri-nho/` **817** · `tac-nhan/` **882** dòng | cùng phép đếm |
| **7 giây** khởi động · **0** lệnh `pip install` | chạy thật từ bản giải nén sạch của HEAD, 26/09/2026 |
| **291** phép thử (thư viện chuẩn) · **304** (thêm `torch`) · **40 giây** một vòng huấn luyện | cùng lần chạy ấy, trên máy xách tay |
| **1.205** dòng `phuc-vu/may_chu.py` · **6/7** đường hợp đồng | đọc tệp và đối chiếu `chat/README.md` |
| **657** dòng `phuc-vu/rag.py`, mã chết trên đường chạy | không tệp nào trên đường chạy nhập nó |
| **88** dòng `trien-khai/yeu-cau.txt`, chỉ phủ nhánh vLLM | đọc tệp |
| **≈ 205.000** dòng toàn bộ mã BDSG tự viết | cộng bốn kho, 26/09/2026 |
| **1.079.991** doanh nghiệp định danh được | cùng phép đếm dùng ở `trang-agent/` |
| **11.733** đoạn ngữ liệu · 7,16 MB · **227** câu bộ đánh giá | bảng trạng thái README gốc kho |
| **26.878.464** tham số — trọng số BDSG, bản nghiên cứu | bảng trạng thái README gốc kho |
| **45/45** tự kiểm `trien-khai/chay-vllm.sh` | chạy `--tu-kiem` |

### Khẳng định "chưa có", và cách kiểm lại từng cái

| Khẳng định | Kiểm lại thế nào |
|---|---|
| Sáu lớp là sáu hòn đảo | đếm số lần một gói trong kho nhập một gói khác trong cùng kho → **0** |
| `phuc-vu/` không đi qua nhân | `grep -rn "nhan" phuc-vu/*.py` → không có lệnh nhập `nhan/` nào |
| Chưa có bản đóng gói | `ls pyproject.toml Dockerfile INSTALL.md` → không tồn tại |
| Trình điều khiển thật: 0 | `ls trinh-dieu-khien/` → đúng hai tệp: `hop_dong.py`, `vi_du_bo_nho.py`; đọc phần đầu tệp sau để thấy nó tự khai "dữ liệu sống trong bộ nhớ và mất khi tiến trình thoát" |

## Một lỗi tài liệu nên sửa ở kho (không sửa trong lần này)

`chat/README.md` viết "phần máy chủ chưa phát hành", trong khi máy chủ nằm ngay
thư mục bên cạnh (`phuc-vu/may_chu.py`, 1.205 dòng, 6/7 đường). Người tải về đọc
câu ấy sẽ ngồi viết lại một thứ đã có sẵn. Trang có nhắc lỗi này trong mục
trạng thái, nhưng **tệp ấy chưa được sửa** — nó không thuộc thư mục này.

## Bảy cổng của kho, chạy lên chính tệp này

```
bash cong/chay-tat-ca.sh --goc trang-platform
```

Chạy ngày 26/09/2026: **7/7 cổng ĐẠT cả tự kiểm lẫn quét kho, mã thoát 0**, và
các cổng có đọc thật tệp `.html` (dòng "Đã đọc 1 tệp văn bản").

**"ĐẠT" ấy chỉ có nghĩa nếu cổng chứng minh được nó cắn.** Phép chứng minh đã
chạy: chép `index.html` sang thư mục tạm, thêm một dòng chú thích HTML chứa một
IPv4 **công cộng**, chạy `cong/khong-ha-tang.py --goc <thư mục tạm>` → **mã
thoát 1**. Bỏ dòng ấy đi thì về **0**.

Lưu ý giữ lại từ `trang-web3/README.md`: đừng thử bằng IP thuộc dải tài liệu
`203.0.113.0/24` — cổng **cố ý** không cắn dải ấy, và thử bằng nó sẽ dẫn tới
kết luận nhầm là cổng không đọc HTML.

### Chạy toàn kho thì đang HỎNG, và không phải vì tệp này

`bash cong/chay-tat-ca.sh` không tham số (quét cả kho) trả **mã thoát 1** lúc
21:20 ngày 26/09/2026: `khong-ha-tang` bắt **1 vị trí**, và vị trí ấy nằm trong
`tai-lieu/BA-KHU-VUC.md` — một tệp chưa theo dõi bởi git, do việc khác tạo ra
cùng buổi, không thuộc thư mục này. Sáu cổng còn lại ĐẠT toàn kho.

Ghi ra đây vì hai lẽ: (a) người deploy trang này đừng tưởng lỗi ở trang; (b)
kho **không được đẩy lên** chừng nào dòng ấy còn — cổng đúng khi chặn.

## Bề ngang điện thoại

Đo thật ở khung nhìn **400 × 900**, phục vụ qua HTTP cục bộ (không phải ảnh
chụp tĩnh của tệp `file://`, vì bản chụp tĩnh dựng thiếu):

- `document.documentElement.scrollWidth` = **400** = `innerWidth` → **không có
  cuộn ngang** trên trang.
- Thanh đầu sticky cao đúng **101 px** ở bề ngang này (nó xuống hai dòng).
- Mở `#chay-duoc-den-dau`: mép trên của khối dừng ở **116 px**, tức chừa được
  **15 px** dưới thanh đầu. Đó là lý do `section[id]` khai
  `scroll-margin-top:116px`. **Hạ số ấy xuống dưới 101 là nhãn và tiêu đề khối
  chui xuống dưới thanh đầu** — cùng cái bẫy đã ghi trong `trang-web3/`.
- Ba bảng đều nằm trong `.bang` có `overflow-x:auto`, `min-width:640px`: bảng
  tự cuộn ngang trong khung của nó, trang thì không.

## Triển khai

Chép `index.html` vào docroot của tên miền rồi đặt lại chủ sở hữu tệp. Đường dẫn
cụ thể **cố ý không ghi ở đây**: kho này công khai, và bố cục thư mục của máy
chủ là thứ chỉ có ích cho người đang dò nó. Cổng `cong/khong-ha-tang.py` bắt
đúng lỗi ấy khi bản đầu của tệp tương đương ghi ra — giữ nguyên bài học.

**Trạng thái `openos.bdsg.vn` tại 26/09/2026: chưa đo.** Tên miền có bản ghi
DNS, nhưng có DNS **không** suy ra có vhost. Ở máy chủ này một tên miền có DNS
mà thiếu vhost từng rơi vào vhost mặc định của một tên miền khác thay vì trả
404 sạch sẽ. Kiểm bằng `curl` **từ ngoài**, kèm `Host:` đúng — không kiểm bằng
`curl 127.0.0.1`, vì lệnh ấy trúng nhầm vhost.

Vhost nằm trong tệp cấu hình Apache **dùng chung cho nhiều tên miền**. Quy trình
sửa, không được bỏ bước nào:

1. sao lưu tệp cấu hình,
2. `apachectl configtest`,
3. **chỉ khi ĐẠT** mới `apachectl graceful`.

**Không bao giờ `restart`** — restart làm đứt kết nối của mọi tên miền dùng
chung tệp cấu hình ấy, còn graceful thì không.

Khi khai vhost, khai `script-src 'none'` đúng như trang đang cần. Mẫu khối vhost
đầy đủ, lệnh xin chứng chỉ và các phép kiểm chứng sau deploy có sẵn ở
`trang-web3/TRIEN-KHAI.md` — trang này dùng đúng khuôn ấy, chỉ đổi tên miền.

## Sửa trang về sau

Trước khi đẩy bất kỳ thay đổi nào:

```
grep -c '<script' trang-platform/index.html        # phải ra 0
bash cong/chay-tat-ca.sh --goc trang-platform      # phải rc=0
bash cong/chay-tat-ca.sh                           # toàn kho, phải rc=0
```

Ba luật riêng cho trang này:

1. **Thêm một tính năng thì phải thêm luôn trạng thái đo được của nó.** Không có
   phép đo thì ghi "chưa đo". Một dòng mô tả tính năng không kèm trạng thái sẽ
   được đọc là tính năng đã chạy.
2. **Phân biệt ba câu: cài được ≠ chạy được ≠ chạy đúng như mô tả.** Dự án này
   đã trượt chân đúng chỗ ấy một lần rồi.
3. **Đừng liệt kê các nền tảng nghiệp vụ như hàng hoá của bản phát hành.** Chúng
   là bằng chứng về thứ hệ điều hành này điều khiển, không phải thứ nó phát hành
   kèm.
