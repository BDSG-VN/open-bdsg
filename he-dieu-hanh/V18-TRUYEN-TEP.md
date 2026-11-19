# V18 — tệp Office lớn và tiếp tục sau gián đoạn

Mốc mã và kiểm tra **15/11/2026**, tiếp nối [V17](V17-VAN-PHONG.md).
Đây là nâng cấp kho tệp, chưa có bộ soạn thảo Word/Excel/PowerPoint hoặc Google.

## Thay đổi người dùng

Mở `/#office`, chọn dự án rồi tải tệp. Giới hạn mới **8 MiB/tệp**; sửa trực
tiếp TXT/MD/CSV vẫn **32 KiB**. Tệp lớn chỉ xem metadata và tải xuống.
Tiến trình hiển thị số byte đã được xác nhận. Có hủy, xem phiên tải dở và chọn
lại cùng tệp để tiếp tục. Không lưu tệp hoặc phiên tải vào web storage.

Khi mạng lỗi, phiên chưa hoàn tất được giữ **15 phút** không truyền thêm;
máy chủ biết vị trí đã nhận. UI cùng lượt làm việc giữ danh tính yêu cầu để
đối soát khi mất phản hồi hoàn tất. Đăng xuất/rời trang xóa metadata retry ở
trình duyệt; sau mở lại vẫn có thể tiếp tục phiên *pending* còn hạn. Không tự
coi mọi tệp giống nhau là cùng một yêu cầu: tải một bản mới sau khi thành công
tạo yêu cầu mới. Không tự retry ghi chưa rõ kết quả bằng request key mới.

Hủy sau khi đã hoàn tất trả rõ tệp vẫn còn, không xóa tệp. Tệp đang tải không
hiện trong danh sách tệp hoàn chỉnh; chỉ công bố sau đủ byte, đúng SHA-256 và
qua điều kiện cấu trúc. Quota tính cả lịch sử, thùng rác và chỗ giữ cho tải dở.

## Giao thức và quyền

| Công cụ `van_phong.*` | Tham số chính | Loại |
|---|---|---|
| `bat_dau_tai` | `project_id,name,total,sha256,request_key` | ghi |
| `ghi_phan` | `id,offset,content_base64` | ghi |
| `trang_thai_tai` | `id` | đọc |
| `phien_tai` | `project_id`; chỉ phiên của actor | đọc |
| `ket_thuc_tai` | `id` | ghi |
| `huy_tai` | `id` | ghi |
| `doc_phan` | `id,version,offset` | đọc |

Phần tải tối đa **512 KiB**, đi qua `/api/upload` với
`destination: "office-part"`. Thân JSON vẫn giới hạn **1.500.000 byte** tại
gateway; cấu hình proxy hiện có cho upload giữ nguyên. `/api/tools` giữ
**64 KiB**, `/mcp` giữ **16 KiB**. Qua MCP vẫn bị trần thân nhỏ hơn; không quảng
bá MCP có thể nhận phần 512 KiB trong một lời gọi với cấu hình này.

Mọi lời gọi qua nhân, vai, cổng ghi, hạn tần suất và audit metadata. Không tự
cấp công cụ cho mô hình hoặc trợ lý. Mỗi phần kiểm lại danh tính, quyền dự án
và chủ phiên. Cộng tác viên editor cũng không được sửa phiên của người khác.
Ghi byte, ledger phần, vị trí nhận và sự kiện được commit cùng giao dịch.

Retry phải khớp đúng offset/kích thước/SHA và byte của phần đã ghi; chồng lấn
tùy ý bị từ chối. Khóa yêu cầu gắn actor và metadata; cùng khóa khác metadata
bị chặn. Hoàn tất giữ ledger trong TTL để trả cùng file ID khi retry, không
tạo file mới. Giao dịch dở rollback về pending khi khởi động lại SQLite.

Tải xuống ghim phiên bản, đọc từng phần qua nhân và kiểm quyền mỗi lần. Trình
duyệt kiểm tổng SHA-256 và số byte trước khi tạo tệp tải về. Không có URL công
khai đến BLOB; không thực thi nội dung hoặc dùng tên tệp làm đường dẫn máy chủ.

## Giới hạn tài nguyên và kiểm định dạng

Mốc cấu hình **15/11/2026**: mỗi dự án **100 tệp, 1.000 phiên bản, 20 MiB** kể
cả reservation; mỗi actor tối đa **2 phiên pending**. Tổng nội dung Office
cộng reservation giới hạn logic **1 GiB**. Giới hạn này không phải kích thước
vật lý cứng của SQLite/WAL hoặc trần dung lượng toàn máy. Tải hết hạn được dọn
khi bắt đầu phiên mới; BLOB và part ledger được giải phóng, không xóa tệp đã lưu.

Kiểm cấu trúc mới áp dụng khi hoàn tất upload theo phần:

- TXT/MD/CSV cần UTF-8, không NUL. PDF chỉ kiểm chữ ký `%PDF-` và luôn ghi
  `pdf-chua-kiem-noi-dung`.
- DOCX/XLSX/PPTX: directory ZIP tối đa **256 KiB**, **2.000 entry**, tổng mở
  nén khai báo **64 MiB**, tỷ lệ nén bị chặn, không multi-disk/ZIP64/encryption,
  kiểm CRC và phần bắt buộc, không giải nén ra filesystem.
- Mọi phần `.xml`/`.rels` được đọc theo luồng; mỗi XML tối đa **16 MiB**, độ
  sâu **128**, toàn gói tối đa **1.000.000 node**. Chặn DTD/entity/external
  entity trước khi xử lý. Không xây DOM đầy đủ hoặc truy cập URL.
- Chặn cơ chế VBA, ActiveX, OLE và nhúng package theo đường dẫn phổ biến và
  khai báo ContentType/relationship Type; các quan hệ ngoài chỉ ghi cảnh báo
  `co-lien-ket-ngoai`, không lấy URL.

Đây là **kiểm cấu trúc cơ bản, không phải antivirus, kiểm tương thích Office
đầy đủ hoặc bảo đảm tệp an toàn**. Tệp chỉ lưu/tải. Chưa đưa vào engine Office.
Tệp V17 và ghi trực tiếp qua công cụ inline cũ vẫn có thể ở trạng thái chưa
kiểm. Kết quả kiểm gắn phiên bản; thiếu kết quả không được biến thành “đã sạch”.

## Kiểm tra và khôi phục

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_truyen_tep_office.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_may_chu.py' -v
```

Bài thử dùng tệp tổng hợp, gồm roundtrip **8 MiB**, retry/overlap/quota/quyền,
header body, XML UTF-16/DTD/depth, ActiveX/OLE đổi tên, hủy và SQLite backup
nhất quán rồi khôi phục phiên pending. Không dùng dữ liệu khách hoặc API tính phí.
Trước deploy giữ SQLite backup, SHA và bản V17 để rollback; quay mã cũ giữ
dữ liệu, nhưng giao diện cũ không hỗ trợ tiếp tục phiên tải mới.
