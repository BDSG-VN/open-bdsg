# V26 — chốt kết quả và giới hạn thời gian tác vụ

Kiểm ngày **17/11/2026**, dùng dữ liệu và transport tổng hợp, không gọi API tính phí.

## Hành vi đã sửa

- Khi người dùng dừng trong lúc quy trình đang tổng hợp báo cáo, kết quả đến
  sau không được thêm vào sản phẩm đầu ra hoặc gửi thông báo hoàn tất.
- Trước khi chốt báo cáo cuối, kiểm lại danh tính còn hiệu lực. Danh tính bị
  thu hồi trong lúc tổng hợp không được xuất bản báo cáo mới.
- Thêm sản phẩm, hoàn tất bước và hoàn tất tác vụ trong cùng khóa với thao
  tác dừng, tránh khoảng giữa các lần lưu tạo trạng thái không nhất quán.
- Phản hồi mô hình đến sau giới hạn tổng lượt chạy bị từ chối. Vẫn ghi mức
  sử dụng provider đã báo trước khi từ chối: hết thời gian không hoàn lại
  lượt API hay giả định provider chưa tính phí.

Không thay chính sách chọn mô hình, chứng thư, ngân sách, nhà cung cấp hoặc
quyền công cụ. Kết quả đã lưu từ lượt trước vẫn được giữ. Dừng tác vụ không
thể thu hồi request mà provider đã nhận, cũng không tự đảo ngược thao tác
ngoài đã hoàn tất.

## Kiểm chứng

Ba bài hồi quy mới đã thất bại trước bản vá và đạt sau bản vá:

- `test_cancel_during_report_does_not_publish_late_result`
- `test_revocation_during_report_does_not_publish_late_result`
- `test_response_after_deadline_keeps_usage_but_not_result`

Ngày 17/11/2026: **67 bài đạt** trên Windows bằng lệnh sau từ
`he-dieu-hanh/`:

```sh
python -m unittest thu_cong_viec thu_mo_hinh_bdsg thu_doi_ngu thu_trung_tam_ai thu_du_an -q
```

`thu_mo_rong` cần kiểm trên Linux vì worker dùng Unix socket
`ThreadingUnixStreamServer`; Windows không cung cấp lớp này. Kết quả trên
không thay thế nghiệm thu API thật của từng provider hoặc endpoint MCP của
các nền tảng. Phần đó tiếp tục cần tài khoản/quyền và môi trường thử được cấp.
