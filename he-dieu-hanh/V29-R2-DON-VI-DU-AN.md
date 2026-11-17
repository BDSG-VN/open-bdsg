# V29 R2 — Backend đơn vị, dự án và tệp trên dữ liệu thử

Tiếp nối: [V29 R3 — HTTP và tác vụ theo đơn vị, vẫn thử nghiệm](V29-R3-HTTP-VA-TAC-VU.md).

Ngày 17/11/2026. **Chưa nối vào gateway hoặc UI production.** `UngDung` đang
dùng luồng một không gian hiện có. Đây là phần xây dựng tiếp theo của V29,
không phải công bố toàn hệ thống đã cách ly nhiều doanh nghiệp. Không chạy
migration này trên kho vận hành trước khi hoàn tất các đường còn lại.

## Phần đã có trong source

`DonVi` nhận actor do lớp xác thực tin cậy tạo, kiểm danh tính còn hiệu lực
và membership trong SQLite; nó không thay đăng nhập cookie/Bearer. Chủ quản
hệ thống tạo đơn vị và chỉ định quản trị đích danh. Người tạo không tự trở
thành thành viên. Quản trị đơn vị quản lý thành viên ở đúng đơn vị; không
tự có quyền nội dung của mọi dự án. Thay đổi membership kiểm trong giao
dịch và giữ ít nhất một quản trị còn hiệu lực, kể cả hai người cùng hạ quyền.

`bind(actor, unit_id)` trả actor kèm phạm vi bất biến trong tiến trình;
`require(actor, db)` kiểm lại trên giao dịch của caller. Không chấp nhận
phạm vi khai bằng JSON hoặc từ registry khác. Phạm vi cũ bị từ chối khi
thu hồi/thay vai; thêm lại thành viên không làm sống lại grant trước lần
thu hồi. Thay vai của thành viên đang hoạt động giữ grant nhưng cần bind lại.

`DuAn(kho, units=registry)` kiểm cả đơn vị và quyền tài nguyên khi liệt kê,
đọc, tạo, sửa, lưu trữ, xem thành viên và chia sẻ. Một người ở hai đơn vị
không trộn dự án. Chia sẻ viewer/editor ghi rõ đơn vị nhận và danh tính,
không cho người nhận chia sẻ tiếp. `quan-tri` không bypass nội dung trong
luồng này. Thêm tệp và sửa dự án kiểm quyền sau khi lấy khóa ghi; tài liệu
kiểm lại sau scan trước khi ghi/trả byte. Trạng thái Office tính quyền sửa
qua chốt dự án, không suy từ vai toàn cổng.

Tệp lưu trong Office SQLite và tài liệu bất biến dùng dự án làm nguồn đơn
vị. Backend này đã kiểm tạo/đọc tệp, thu hồi trong lúc scan và backup/restore
bằng dữ liệu tổng hợp. Chưa coi callback của bộ soạn thảo là đã mang phạm vi.

## Migration dự án cũ trên bản sao

`chuyen_du_an_don_vi.migrate_legacy(scoped_projects, authenticated_owner)`
đưa các quan hệ dự án cũ vào không gian “chưa phân loại”, giữ ID, owner,
nội dung tệp và ngữ cảnh. Quyền chủ quản cũ trở thành grant manager đích
danh trên từng dự án legacy; không mở rộng sang đơn vị mới. Quyền viewer/
editor cũ được giữ theo đơn vị legacy, không suy tên doanh nghiệp từ email.

Chạy lại có marker thì không gán lại dữ liệu. Dữ liệu mồ côi, quyền/chủ sở
hữu không xác định hoặc writer cũ thêm dự án thiếu phạm vi đều chặn chuyển
tiếp để đối soát, không xóa hoặc tự rơi về đơn vị mặc định. Luồng `DuAn`
thiếu registry từ chối hoạt động khi đã có đơn vị, kể cả instance tạo trước
migration. Chốt này có trong mã mới, không thể khiến mã cũ tự hiểu schema.

Migration hiện chỉ xử lý quan hệ dự án/tài liệu/tệp, **không** chuyển task,
mailbox, lịch, actions, Google vault, AI/connector credentials hoặc audit
toàn hệ thống. Giữ bảng cũ để đối soát; không chạy writer cũ song song.

## Cổng còn thiếu trước khi bật đa đơn vị

- Xác lập phạm vi từ cookie/token ở HTTP/MCP; lọc actor khi trả JSON. Không
  lấy actor/role từ body. Frontend cần tách cache/window theo đơn vị và chặn tab cũ.
- Task, lịch, worker, browser/runtime, actions, ngân sách và kết quả phải
  giữ đơn vị đã lưu, kiểm lại membership trước công cụ/commit.
- Office editor/member/callback, Google OAuth/vault/import/export và các
  đầu nối/model cần phạm vi cố định; không fallback sang quyền toàn cổng.
- Khóa idempotency upload/tạo tệp của cùng identity ở nhiều đơn vị cần
  namespace theo đơn vị; audit/search/export phải cùng chính sách.
- Diễn tập gateway từ bản tenant đã phục hồi, chuyển dữ liệu vận hành đầy
  đủ, rollback/cutover và kiểm độc lập toàn bộ trước production.

Kiểm từ gốc kho, dữ liệu tạm, không gọi mạng hoặc provider thật:

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_*don_vi.py' -v
```

Xem [quyết định kiến trúc](../docs/adr/0001-pham-vi-don-vi.md),
[bản đồ chuyển đổi](../docs/nghien-cuu/V29-KHONG-GIAN-DON-VI.md) và
[quản lý phiên web đã phát hành](V29-PHIEN-WEB.md).
