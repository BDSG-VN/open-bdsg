# Nhân sự chuyên môn theo kỹ năng — V22 đang phát triển

Yêu cầu chủ quản ngày 16/11/2026: tuyển chọn khoảng 30–50 nguồn GitHub quốc
tế nhiều sao, không giới hạn quốc tịch tác giả; chuẩn hóa kỹ năng phù hợp cá
nhân/doanh nghiệp Việt Nam. Không dùng số dòng mã làm tiêu chí hoàn thành.

## Nguồn và bản chuẩn hóa

`source-selection.json` ghi 36 kho được chọn từ truy vấn có giới hạn và
review nguồn chính chủ, xếp theo số sao đo ngày 16/11/2026. Đây không phải
tuyên bố top tuyệt đối của toàn GitHub. `vendor/sources.lock.json` giữ 133
tệp hướng dẫn/giấy phép đã tải bằng commit đầy đủ cùng SHA-256. Giấy phép
riêng của nguồn vẫn áp dụng; không đổi nội dung vendor thành Apache chung.
Các nguồn chỉ mục không có skill thực, hoặc chưa rõ giấy phép tài liệu,
không được tính thành kỹ năng thực thi.

Bản archive đầy đủ của các kho nguồn được tải riêng tại máy phát triển,
ngoài Git; không chạy installer/hook/script của nguồn. Gói vendor trong
ứng dụng chỉ chứa văn bản được chọn và giấy phép tương ứng. Các nguồn
nghiên cứu có giả định chuyên ngành không tự kích hoạt chỉ vì đã tải.

`chuyen-mon.json` là quy trình chuyên môn tiếng Việt do dự án biên soạn,
tham khảo các nguồn có attribution, không nhập persona hư cấu hoặc đặc
quyền trong prompt nguồn. `dung_bo_nhan_su.py` tạo 24 thư mục SKILL.md và
catalog có hash. Hệ thống kiểm hash trước nạp; không chạy mã kèm nguồn.

```sh
python3 trien-khai/dung_bo_nhan_su.py
python3 he-dieu-hanh/thu_doi_ngu.py -v
```

## Lõi đang có

- Công cụ `nhan_su.danh_sach`, `nhan_su.chi_tiet` đi qua nhân xác thực.
- Tác vụ `template=nhan-su-chuyen-mon` dùng Agent tổng lập kế hoạch ngữ
  nghĩa qua mô hình đã cấu hình, chọn từ catalog được duyệt. JSON kế hoạch
  có ID, phần việc, sản phẩm và phụ thuộc; không nhận công cụ hoặc quyền
  do planner tự đề nghị.
- Tối đa sáu chuyên môn/lượt, ba chuyên môn song song; phụ thuộc phải có
  đầu ra thật trước bàn giao. Mỗi chuyên môn có ngữ cảnh riêng, cùng quyền
  đã cấp cho tác vụ; không có đệ quy tự phân việc cho tác vụ khác.
- Mỗi kết quả chuyên môn tối đa 6000 byte UTF-8; vượt hạn báo lỗi, không
  cắt thầm. Agent tổng tổng hợp từ kết quả thật. Có lưu tên, hash kỹ năng,
  phần việc, trạng thái, thời điểm và đầu ra của từng vai trò.
- Mọi lượt gọi mô hình vẫn giữ ngân sách/usage hiện có; hủy hoặc thu hồi
  danh tính chặn bước tiếp theo. Lỗi chuyên môn chặn phần phụ thuộc và
  không chạy tổng hợp thành công giả.
- Kết quả vai trò thành tệp Markdown riêng cùng báo cáo tổng. Tiếp tục
  tạo lượt mới, giữ lịch sử; restart đánh dấu đội đang chạy bị gián đoạn.
- Không có mô hình: trạng thái chờ cấu hình, không tạo kết quả chuyên gia.

## Chưa hoàn tất

Màn theo dõi và danh mục nhân sự trong giao diện chưa được triển khai ở
đợt nền này. Chế độ đội ngũ chưa thay mặc định giao việc hiện hành. Các
nguồn bổ sung còn cần ánh xạ chuyên môn và kiểm nội dung trước kích hoạt.
Chưa có bộ xuất/nhập đa hệ AI hoặc nghiệm thu nhà cung cấp mô hình thật.
Không có tuyên bố toàn bộ 36 kho đã chuyển thành kỹ năng thực thi.

Ngày 16/11/2026: 24 SKILL.md đạt trình kiểm cấu trúc; 10 bài kiểm mới đạt,
kiểm kế hoạch, song song, phụ thuộc, hủy, giới hạn, lưu lịch sử, ACL và
restart bằng mô hình tổng hợp. Toàn bộ kiểm lõi Linux: 198 bài, 183 đạt và
15 bỏ qua theo môi trường. Kiểm tổng hợp không chứng minh chất lượng suy
luận của mô hình thực tế hoặc khả năng thao tác Office/CRM chưa được cấp.
