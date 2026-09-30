# trang-web3 — trang của web3.bdsg.vn

Trang tĩnh, không có bước đóng gói, không một dòng JavaScript nào. Triển khai
bằng cách chép thẳng `index.html` vào docroot.

Cùng khuôn với `trang-agent/`: cùng bảng màu, cùng Roboto, cùng lối viết, cùng
quy tắc "chưa đo thì nói là chưa đo".

## Vì sao không có JavaScript

Chính sách bảo mật nội dung của vhost khai `script-src 'none'`. Khai đúng như
vậy thì một ngày nào đó có ai chèn script vào, trang hỏng **ngay** thay vì chạy
âm thầm. Một lời khai rộng tay hơn sự thật là một lời khai vô dụng.

Tài nguyên ngoài duy nhất: Google Fonts (`fonts.googleapis.com`,
`fonts.gstatic.com`). Không ảnh ngoài, không phân tích, không nhúng gì khác.

## Trang này nói gì

BDSG Web3 là **lớp blockchain** của Open BDSG. Trạng thái thật ngày
26/09/2026: **đang dựng, chưa có mã, chưa chọn chuỗi khối**.

Bố cục cố ý đặt mục **"Trang này chưa làm được gì"** ngay sau phần mở đầu,
không giấu xuống cuối. Một trang sản phẩm mở đầu bằng lời hứa rồi nhắc chữ
"sắp" ở chân trang thì người đọc đã tin xong từ màn hình đầu. Thứ tự là một
lời khai.

Phần giới thiệu ba việc (nhật ký không sửa được · chứng thực nguồn gốc dữ liệu
· hợp đồng thông minh giữa các doanh nghiệp) **kèm phản biện cho từng việc**, và
có một bảng đối chiếu "cách rẻ hơn đã có sẵn". Lý do: cả ba việc đều có cách
làm không cần chuỗi khối, và nếu cách rẻ hơn đủ dùng thì lớp này không nên tồn
tại. Trang phải khó tự thuyết phục mình.

## Khẳng định trên trang, và cách đo lại

Trang không có một con số bịa nào. Ba khẳng định kiểm chứng được:

| Khẳng định | Cách đo lại |
|---|---|
| `web3.bdsg.vn` gốc trả **404** — **phép đo CŨ, đã hết đúng** | Vhost được nạp ngay sau đó. Đo lại 20:13 ngày 26/09/2026: `curl -sS -o /dev/null -w "%{http_code}\n" https://web3.bdsg.vn/` → `200`, trả đúng byte của `index.html`. Xem `TRIEN-KHAI.md` mục 0 |
| Kho **chưa có mã blockchain** | `grep -rail "blockchain\|web3\|smart contract\|hợp đồng thông minh" . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=trang-web3` |
| Bản ghi nhật ký **không móc nối bằng băm** | đọc `nhan/nhat_ky.py`, hàm `NhatKy.ghi()`: bản ghi gồm `thoi_diem`, `ma_theo_doi`, `danh_tinh`, `cong_cu`, `tham_so`, `so_truong_da_lam_mo`, `ket_qua`, `ly_do`, `mili_giay` — không có trường nào trỏ về dòng trước |

### Một phép đo suýt bị ghi sai

Bản đầu của trang ghi "**0 tệp** khớp". Đo lại thì khớp **1 tệp**:
`huan-luyen/tu-vung/ket-qua/tokenizer-vi-6400-thu-nghiem.json`, và ở đó
"blockchain" là một **từ trong bảng từ vựng** của bộ tách từ, nằm cạnh "bưu" và
"nóng" — không phải mã. Kết luận không đổi, nhưng con số thì đổi. Giữ lại ghi
chú này vì "0" là loại con số không ai đi kiểm lại.

Ghi chú kỹ thuật cho người đo lại: `grep` **im lặng bỏ qua** tệp có byte NUL nếu
thiếu cờ `-a`. Chính cổng chủ quyền `chu-quyen.mjs` của kho landing là một tệp
như vậy — `grep` không cờ `-a` trên nó trả về rỗng và trông y hệt "không có gì".
Đã suýt kết luận nhầm vì chuyện này.

## Cổng chủ quyền: kết quả thật, và một lỗ

Cổng `scripts/kiem-tra/chu-quyen.mjs` của kho landing chạy được trên tệp này:

```
node scripts/kiem-tra/chu-quyen.mjs --path <đường dẫn tới index.html>
```

Chạy thật ngày 26/09/2026, mã thoát **0**, và đây là dòng quan trọng:

```
· …/trang-web3/index.html — quét 0 tệp văn bản
  (bỏ qua: 1 tệp khác đuôi, 0 tệp nhị phân, 0 symlink, 0 thư mục loại trừ)
✓ SẠCH — 0 tệp không có chuỗi cấm
```

**Cổng ĐẠT mà quét 0 tệp.** Danh sách đuôi quét là `.js .mjs .cjs .json
.geojson` (hằng `DUOI_QUET`), nên `.html` rơi vào ô "khác đuôi". Phép fail-closed
"không thấy gì" **không** kích hoạt, vì tệp bị bỏ qua có chủ đích vẫn được tính
là "đã thấy" — một lựa chọn cố ý, ghi rõ trong chính cổng. Hệ quả phải nhớ:
**mã thoát 0 ở đây không nói gì về nội dung tệp HTML.** Đây đúng là họ lỗi
"ĐẠT mà rỗng" của dự án này, chỉ khác là lần này nhìn thấy trước.

Nên nội dung được soi thật bằng cách ép cổng đọc chính những byte ấy: chép
`index.html` sang một tệp đuôi `.json` trong thư mục tạm rồi chạy cổng lên thư
mục đó.

```
✓ SẠCH — 1 tệp không có chuỗi cấm
```

Lần này **quét 1 tệp**, mã thoát 0. Trang không chứa chuỗi nào trong `MAU_CAM`,
và cũng không tự nhận là lớp chủ quyền nên không rơi vào phép kiểm "nhãn bắt
buộc".

Việc nên làm ở kho landing (không làm trong lần này, vì nó sửa cổng dùng chung
cho cả kho): thêm `.html` vào `DUOI_QUET`. Trang tĩnh giờ đã là một dạng nội
dung phát hành thật, mà cổng đang không nhìn thấy nó.

## Bảy cổng của kho này thì có đọc `.html`

`bash cong/chay-tat-ca.sh` chạy ngày 26/09/2026 sau khi thêm thư mục này:
**7/7 cổng ĐẠT cả tự kiểm lẫn quét kho, mã thoát 0**.

Và đây là phép chứng minh cổng THẬT SỰ đọc tệp `.html` chứ không lặng lẽ bỏ
qua: chép `index.html` sang thư mục tạm, chèn thêm một dòng chú thích HTML chứa
một IPv4 công cộng, chạy `cong/khong-ha-tang.py --goc <thư mục tạm>` → **mã
thoát 1**. Bỏ dòng ấy đi thì về 0. Cổng cắn được, nên "ĐẠT" ở đây có nghĩa.

(Ghi chú phụ, đo cùng lúc: một IP thuộc dải tài liệu `203.0.113.0/24` **không**
làm cổng cắn — đúng như thiết kế. Nếu chỉ thử bằng IP tài liệu thì sẽ kết luận
nhầm là cổng không đọc HTML.)

## Triển khai

Chép `index.html` vào docroot của tên miền rồi đặt lại chủ sở hữu tệp. Đường dẫn
cụ thể **cố ý không ghi ở đây**: kho này công khai, và bố cục thư mục của máy
chủ là thứ chỉ có ích cho người đang dò nó.

`web3.bdsg.vn` **đã có vhost** (khối `:80` + `:443`, chứng chỉ ECC, đủ 4 header
bảo mật và CSP `script-src 'none'`) — đo 20:13 ngày 26/09/2026, gốc trả **200**.
Khối vhost đầy đủ, lệnh tạo thư mục, lệnh xin chứng chỉ và **7 phép kiểm chứng sau
deploy** nằm trong **`TRIEN-KHAI.md`** cạnh tệp này. Vhost nằm trong tệp cấu hình
Apache **dùng chung cho 56 tên miền**. Quy trình sửa, không được bỏ bước nào:

1. sao lưu tệp cấu hình,
2. `apachectl configtest`,
3. **chỉ khi ĐẠT** mới `apachectl graceful`.

**Không bao giờ `restart`** — restart làm đứt kết nối của mọi tên miền dùng
chung tệp cấu hình ấy, còn graceful thì không.

Khi khai vhost, khai `script-src 'none'` đúng như trang đang cần, và nhớ rằng
một tên miền có DNS mà thiếu vhost thì **không** trả 404 sạch sẽ ở mọi cấu hình
— ở máy chủ này nó từng rơi vào vhost mặc định của một tên miền khác. Kiểm bằng
`curl` từ ngoài, kèm `Host:` đúng, chứ không kiểm bằng `curl 127.0.0.1`.
