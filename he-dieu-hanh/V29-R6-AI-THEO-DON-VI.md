# V29 R6 — AI theo đơn vị trong backend thử nghiệm

Ngày 17/11/2026. Tiếp nối [nền hạn mức R5](V29-R5-HAN-MUC-AI-DON-VI.md).
Production vẫn giữ không gian hiện có; chưa bật tenant hoặc chuyển dữ liệu thật.

## Luồng đã nối

Trong gateway khởi tạo rõ `unit_preview=True`, người đã đăng nhập chọn phạm vi
đơn vị hợp lệ qua `X-BDSG-Unit`. Các công cụ `mo_hinh.danh_sach`, `han_muc`,
`cau_hinh`, `luu` đi qua nhân. Chỉ quản trị đơn vị được cấu hình; vai chủ quản
hệ thống không tự cho quyền nội dung hoặc cấu hình AI ở đơn vị đã tham gia.

`AITheoDonVi` lưu cấu hình riêng trong SQLite, trả metadata có lọc khóa. Mỗi
lượt chạy giữ binding danh tính, đơn vị, thế hệ quyền và revision cấu hình.
Tạo hoặc tiếp tục giữ suất cùng giao dịch với lượt chạy. Model đã chọn được
giữ qua lập kế hoạch, chuyên viên và tổng hợp; không đổi biến mô hình toàn cổng
theo yêu cầu. Khi tiếp tục rõ ràng một lượt mới, cấu hình hiện hành được bind lại.

Trước mỗi lần gửi, ngân sách kiểm tác vụ/lượt/quyền dự án và guard cấu hình
trong cùng giao dịch. Thu hồi thành viên, đổi vai vòng, thay khóa, tắt mô hình,
hủy tác vụ hoặc callback lượt cũ không được dùng để gửi tiếp hoặc ghi sang lượt
mới. Yêu cầu đã gửi ra ngoài không thể được rút lại bằng thao tác thu hồi.

## Proxy và bí mật

SQLite riêng là nguồn chuẩn, compiler sinh `litellm-config.json` với alias
đơn vị/mô hình/revision. Master key chỉ backend giữ. Đây là phân quyền do BDSG
thực thi; không phải cơ chế khóa đơn vị được LiteLLM cưỡng chế độc lập. Xem
[đối chiếu chính chủ LiteLLM](../docs/nghien-cuu/V29-AI-DON-VI-LITELLM.md).

Lưu cấu hình khác với proxy đã nạp. Admission và mỗi reservation kiểm đúng
nguồn SQLite–file cùng alias đang có ở proxy. Không tự fallback khi lỗi.
Luồng phát hành file dùng cơ chế nạp lại proxy hiện có; việc restart proxy
chung có thể ảnh hưởng lời gọi đang chạy, chưa có cam kết hot reload không gián đoạn.

Khóa nằm trong dữ liệu SQLite và file proxy riêng, cần quyền hệ tệp và bản sao
được bảo vệ như bí mật. Không trả qua admin/task/event hoặc đưa vào prompt.
Không tự chuyển cấu hình legacy: nếu có `model-private.json` hoặc
`ai-models-private.json`, publish đơn vị bị chặn để chờ chuyển đổi rõ ràng.

## Nhất quán và phục hồi

Backup kiểm proxy được tái sinh đúng từ snapshot SQLite, vẫn giữ kiểm cặp
legacy nghiêm ngặt. Lỗi ghi có rollback hoặc trạng thái bất nhất đóng cổng gửi;
khởi động không tự sửa hay tự công bố. Trên console vận hành tin cậy, chủ quản
hệ thống có thể gọi `AITheoDonVi.repair_proxy(actor)` để dựng lại file từ nguồn
SQLite đã kiểm; không đổi khóa/revision hoặc trả bí mật. Không cấp công cụ này
qua HTTP/MCP. Nếu nguồn DB thiếu hoặc sai, cần đối soát/khôi phục bản sao hợp lệ.

## Kiểm tra

```sh
python3 -m unittest discover -s he-dieu-hanh -p 'thu_ai_don_vi.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_cong_viec_ai_don_vi.py' -v
python3 -m unittest discover -s he-dieu-hanh -p 'thu_don_vi_http.py' -v
```

Kiểm bằng dữ liệu tổng hợp, probe và provider giả; HTTP có bài dùng adapter
LiteLLM thật với transport giả để kiểm payload, kết quả và hạn mức. Đây chưa
là nghiệm thu quyền truy cập/giá tính phí hoặc khả năng tool của provider thật.

MCP theo đơn vị, công cụ ngoài, runtime, delegation, Google/Office callback và
các luồng chưa chuyển vẫn bị chặn. Giao diện chọn đơn vị, migration/cutover đầy
đủ và lộ trình hệ sinh thái ứng dụng/thiết bị còn tiếp; không bật bằng HTTP hay
tự suy từ việc đã cài mã backend lên máy chủ.
