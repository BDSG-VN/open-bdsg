# V17 — nền lưu tệp cho BDSG Office

Mã thử nghiệm ngày **15/11/2026**, tiếp nối V16. Không phải tuyên bố đã có bộ
Google Workspace tương đương hoặc bộ soạn thảo đang vận hành trên website.

## Phần đã có trong mã

`van_phong.py` giữ tệp theo dự án trong SQLite riêng ngoài web. Các công cụ
`van_phong.trang_thai`, `danh_sach`, `tao`, `doc`, `lich_su`, `cap_nhat` được
đăng ký qua nhân; cùng dùng phiên web hoặc chứng thư operator hiện có.
Không tự cấp các công cụ này cho vai agent hoặc mô hình tác vụ.

- Chủ dự án/chủ quản quản lý tệp; viewer chỉ đọc, editor được sửa. Thu hồi quyền
  dự án chặn cả các mã tệp và phiên bản đã biết. Kiểm quyền và ghi dùng cùng
  giao dịch, không dựa vào quyền do trình duyệt tự khai.
- `revision` tăng khi đổi nội dung, tên hoặc trạng thái; mọi cập nhật cần
  `expected_revision` hiện tại. Hai lần lưu cùng revision chỉ một lần thành công.
- `version` chỉ tăng khi lưu nội dung hoặc khôi phục phiên bản. Khôi phục tạo
  phiên bản mới, không ghi đè bản cũ. Thùng rác có thể khôi phục, không xóa cứng.
- Dấu SHA-256 được kiểm trước khi đọc và khôi phục. Metadata, nội dung và sự
  kiện lưu trong cùng giao dịch. Nhật ký không chép tên hoặc nội dung tệp.
- Dự án lưu trữ vẫn đọc được, chặn sửa. Cổng ghi nhân đóng thì chặn mọi thao tác ghi.

## Giao diện công cụ

| Công cụ | Tham số |
|---|---|
| `trang_thai` | `project_id` |
| `danh_sach` | `project_id`, `trashed` tùy chọn |
| `tao` | `project_id`, `name`, `content_base64` |
| `doc` | `id`, `version` tùy chọn; trả nội dung base64 |
| `lich_su` | `id`; metadata phiên bản, không trả toàn bộ nội dung |
| `cap_nhat` | `id`, `expected_revision`, `action` và trường theo hành động |

`action`: `save` + `content_base64`; `rename` + `name` giữ phần mở rộng;
`trash`; `untrash`; `restore-version` + `version`.

Mốc cấu hình **15/11/2026**: mỗi tệp tối đa **32 KiB**, mỗi dự án **100 tệp**,
**1.000 phiên bản**, **20 MiB** kể cả lịch sử/thùng rác. Tệp rỗng được hỗ trợ.
Nhận TXT, MD, CSV, PDF, DOCX, XLSX, PPTX dưới dạng dữ liệu mờ; phần mở rộng không
chứng minh cấu trúc hợp lệ hoặc an toàn. Không thực thi/chuyển đổi/giải nén.

API web `/api/tools` giữ giới hạn thân **64 KiB**, MCP giữ **16 KiB** tại mốc
trên; vì mã hóa base64, tải lên qua MCP có giới hạn thực tế nhỏ hơn giới hạn
tệp. Không thay cấu hình proxy để mở tải lớn. Bộ lưu BLOB nhỏ tránh tạo dữ liệu
nằm ngoài bản sao lưu SQLite; tệp lớn cần một đợt thiết kế và kiểm chứng riêng.

## Chưa có

Chưa có giao diện Drive, thư mục, tìm kiếm nội dung, chia sẻ công khai, quét mã
độc, Docs/Sheets/Slides editor, đồng tác giả, chuyển đổi Office, lịch người dùng,
Google OAuth hoặc đồng bộ Google. Trạng thái trả rõ `chua-cau-hinh`, `chua-ket-noi`,
`chua-quet`. Không chuyển tệp này sang bộ soạn thảo cho đến khi có đường kiểm
định dạng/quét tệp và phiên editor được xác thực. Không gửi tệp tới mô hình AI.

Kế hoạch nghiên cứu riêng được giữ trong tracker `.scratch/thanhhoa/office-plan-20261115/`.
Giao diện tương lai giữ hệ màu và các quy tắc tại `DESIGN.md`.

## Kiểm tra có thể tái lập

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_van_phong.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_may_chu.py' -v
```

Chỉ dữ liệu tổng hợp trong thư mục tạm; không dùng khóa Google, API tính phí
hoặc dữ liệu khách. Kết quả đo lưu trong báo cáo của lần kiểm tương ứng.
