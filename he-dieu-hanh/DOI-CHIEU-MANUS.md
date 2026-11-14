# Đối chiếu Manus và quyết định thiết kế riêng — 14/11/2026

Yêu cầu: dùng REA phân tích cấu trúc/mã công khai của Manus để phát triển
không gian thực thi và mô-đun BDSG trên thực thể Thanh Hoá.

## Bằng chứng quan sát

- Trình duyệt công khai `https://manus.im/` có ô giao mục tiêu, các mẫu tác vụ,
  liên kết ứng dụng và tài liệu. Không đăng nhập hoặc chạy tác vụ có tính phí.
- HTML khai báo 69 tệp JavaScript trên `files.manuscdn.com`. Các URL chứa
  `_next/static/chunks` và một tên `turbopack`; đây là dấu vết đóng gói phía
  client, không chứng minh kiến trúc máy chủ.
- REA 6.9.0 phân tích tĩnh ba tệp được chọn: `2zwac0dmwzkf0.js`,
  `0g-poc01y0nq1.js`, `0xpbnh77udu1q.js`: 613.360 byte, 3 tệp phân tích cú
  pháp thành công, 0 lỗi cú pháp, 191 findings. Evidence gốc:
  `ev_3ba9762418289904a10f8516572e015e0d025d9c4814c29049d2d9de9405ec9f`.
  Summary: `ev_5d9ab82adabbe91d4762d3365dda154bc55b61f1c53612be49091cb138a15cc3`.
- Kiểm chuỗi độc lập trong các tệp đã chọn thấy định danh `projectUid`,
  `/app/artifacts`, đường dự án `/app/project/...`, `connectorSource`,
  `taskReferences` và liên kết giới thiệu connector. Đây chỉ là chuỗi mã
  client; không chứng minh endpoint reachable, quyền hay tác vụ đã chạy.
- [Tài liệu Manus](https://manus.im/docs/introduction/welcome) mô tả agent
  thực thi và connectors. [Tài liệu API](https://open.manus.ai/docs/v2/introduction)
  mô tả tasks, follow-up, projects, files và webhooks.

## Giới hạn của phép phân tích

Chỉ ba trong 69 tệp JavaScript được phân tích sâu; giới hạn semantic nodes,
unknowns và alias expansion làm kết quả có phạm vi **partial**. Turbopack và
tham chiếu động không được khôi phục đầy đủ. View route không trả candidate;
không được suy ra rằng ứng dụng không có route. Không có source map, mã máy
chủ, prompt hệ thống, trọng số, môi trường máy tính ảo hoặc phiên đăng nhập
Manus để kiểm chứng. REA đọc mã như văn bản, không thực thi bundle.

Một lệnh mở trình duyệt phân tích riêng bị cơ chế phê duyệt tự động từ chối.
Đã dùng phương án phân tích tệp JavaScript công khai bằng REA và quan sát UI
qua trình duyệt hiện có. Không bỏ qua chặn đăng nhập hoặc cảnh báo bảo mật.

Bundle bằng chứng và bản tệp gốc lưu riêng tại môi trường điều tra, không
đưa mã, logo, stylesheet hay tài nguyên Manus vào kho BDSG hoặc bản web triển khai.

## Quyết định triển khai BDSG

| Ý tưởng tham khảo | Mã riêng trong Open BDSG | Trạng thái |
|---|---|---|
| Giao mục tiêu qua một ô nhập | `khong-gian/cong-viec.js` | Có |
| Theo dõi công việc và bổ sung ngữ cảnh | `he-dieu-hanh/cong_viec.py` | Có, SQLite và worker |
| Kết quả tải xuống | Báo cáo Markdown riêng theo quyền | Có |
| Kết nối ứng dụng | Danh mục mô-đun + gateway MCP hiện có | Có khung; cần endpoint/quyền từng nền tảng |
| Agent dùng mô hình | Adapter OpenAI/Claude/BDSG, công cụ đọc qua nhân | Có mã; cần khóa/mô hình thật |
| Máy tính ảo và trình duyệt agent | Chưa triển khai | Không giả lập |
| Đồng bộ nền tảng và ghi nghiệp vụ tự động | Chưa triển khai | Không tự tuyên bố |

Đây là thiết kế BDSG do mình viết, lấy cảm hứng từ mô hình tương tác đã quan
sát. Không phải mã nội bộ hoặc bản sao hoàn chỉnh của Manus.
