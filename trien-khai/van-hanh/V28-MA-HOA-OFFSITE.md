# V28 — chuẩn bị gói mã hóa trước khi sao lưu ngoài máy

Phạm vi ngày 17/11/2026: công cụ cục bộ `v28_ma_hoa.py` đóng gói một bản sao
V20 đã hoàn chỉnh rồi mã hóa bằng **age v1.3.2** do người vận hành chỉ định.
Không tạo khóa riêng, không tải/cài phần mềm, không gọi Google Drive, không
thay timer và không công bố đã có offsite.

## Chuẩn bị

Người vận hành kiểm nguồn phát hành, checksum và quyền sở hữu tệp thực thi
age trước khi dùng. Công cụ kiểm `--version` đúng `v1.3.2`; chuỗi phiên bản
không thay việc xác minh nguồn tải. Tệp người nhận chỉ chứa khóa **công khai
native age**, một dòng mỗi người nhận, có thể có dòng trống/chú thích `#`.
Cả native cổ điển và PQ được chấp nhận về loại; age tự kiểm định dạng/khóa.
Không chấp nhận khóa riêng, SSH hoặc plugin. Mỗi người nhận đều có thể giải
mã; danh sách này cần được chủ quản duyệt. Không sửa tệp người nhận hoặc
chương trình age trong khi lệnh đang chạy.

Khóa riêng do chủ quản giữ qua quy trình riêng và có phương án giữ bản dự
phòng; không để cùng gói đưa lên cloud, Git, web hoặc máy gateway nếu không
được duyệt. Công cụ này không đọc identity và không tự tạo khóa.

## Tạo tệp mới

Chạy tại gốc kho, chọn thư mục đích riêng do người vận hành sở hữu, không cho
tài khoản ứng dụng hoặc người khác ghi. Các đường dẫn dưới là ví dụ.

```sh
umask 077
python3 trien-khai/van-hanh/v28_ma_hoa.py \
  --age-executable /usr/local/lib/bdsg/age-v1.3.2/age \
  --recipients-file /root/bdsg-offsite-recipients.txt \
  --bundle /var/backups/bdsg-thanhhoa/BAN-SAO-DA-CHON \
  --destination /root/bdsg-offsite/BAN-SAO-MOI.tar.age \
  --timeout 300
```

Công cụ kiểm gói bằng `sao_luu_he_thong.verify`, đưa manifest và các tệp
thường đã kiểm vào tar qua stdin của age. Kiểm SHA lại trên từng byte đưa
vào tar để chặn tệp đổi sau lần kiểm ban đầu. Header tar dùng tên tương đối,
không mang tên người dùng, UID/GID hoặc đường dẫn máy nguồn. Không lưu bản
tar chưa mã hóa xuống đĩa.

Đầu ra age ghi vào `<đích>.part` mới, quyền `0600`, kiểm mã thoát/định dạng,
flush/fsync rồi tạo tên cuối bằng hard link nguyên tử không ghi đè. Đích và
`.part` phải ở cùng filesystem có hỗ trợ hard link. Không chuyển sang cơ
chế ghi đè nếu filesystem không hỗ trợ. Tệp đích hoặc `.part` đã tồn tại
được giữ nguyên; đích xuất hiện trong khi mã hóa cũng được giữ nguyên.
Lỗi chỉ dọn `.part` do chính lượt này tạo, không xóa bản sao nguồn hay đích.
Tiến trình age quá hạn bị dừng. Không tự dọn tệp còn lại sau máy bị tắt đột
ngột; người vận hành kiểm trước khi xử lý.

Từ chối symlink/junction trong đường dẫn đầu vào/đích, tệp đặc biệt, đích nằm
trong gói và đích không có đuôi `.age`. Không nhận đường dẫn qua HTTP/MCP.
stdout chỉ có trạng thái, mốc đo, thời lượng, số tệp, kích thước và SHA-256
của **ciphertext**; không có đường dẫn, recipient, manifest hoặc ngoại lệ.
Mã thoát `0` nghĩa age đã tạo tệp mã hóa mới; `1` nghĩa chưa hoàn tất.

## Bằng chứng còn cần cho offsite

`decryption_verified` luôn `false` và `offsite.configured` luôn `false` trong
báo cáo của công cụ này. Chưa gọi Drive hoặc chứng minh giải mã được.
Sau khi chủ quản xác nhận đúng tài khoản/thư mục, bước vận hành riêng phải:

1. Giải mã bằng identity đã được giữ an toàn vào môi trường phục hồi cô lập,
   kiểm danh sách tar chỉ gồm manifest và các đường dẫn cho phép trước khi
   giải nén vào thư mục mới; không giải nén lên kho sống.
2. Chạy `verify` rồi `kiem_tra_khoi_phuc.py` trên gói đã giải mã, ghi số lượng,
   integrity và thời gian phục hồi.
3. Tải **ciphertext** lên đúng nơi được duyệt, tải lại từ đó, so SHA-256 và
   lặp bước giải mã/kiểm/phục hồi từ bản đã tải lại. Không tải identity lên.
4. Ghi ngày đo và bằng chứng từng bước; chỉ sau bằng chứng thực tế mới cập
   nhật mô tả trạng thái ngoài máy theo schema được kiểm duyệt.

Không dùng việc tạo tệp `.age` hoặc thấy tệp trên Drive để thay bằng chứng
phục hồi. Phục hồi dữ liệu thành công cũng chưa chứng minh RTO toàn dịch vụ.

## Kiểm thử

```sh
python3 trien-khai/van-hanh/thu_v28_ma_hoa.py -v
```

Bộ kiểm dùng adapter tiến trình giả để kiểm tar stream, từ chối gói hỏng,
đích đã có/đích xuất hiện giữa chừng, giữ `.part` cũ, dọn `.part` của lượt
lỗi và lọc stdout. Adapter giả **không kiểm mật mã**. Phép thử age thật và
giải mã bằng identity thật trong môi trường cô lập cần bằng chứng riêng.

## Nguồn kỹ thuật chính thức

- [Hướng dẫn age tại bản v1.3.2](https://github.com/FiloSottile/age/blob/v1.3.2/doc/age.1):
  stdin/stdout mặc định, `--recipients-file`, `--version`; `--output` của age
  có thể ghi đè, vì vậy wrapper tự quản lý tệp đầu ra mới.
- [Bản phát hành age v1.3.2](https://github.com/FiloSottile/age/releases/tag/v1.3.2).
