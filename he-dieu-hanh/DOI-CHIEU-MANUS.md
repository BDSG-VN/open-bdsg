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

Lượt v5 phân tích thêm `2crzlppxwovn3.js` và `42r_m_zh6hhqp.js`: 2.168.248 byte,
2 tệp parse thành công, 0 lỗi cú pháp, 326 findings, 471.952 AST nodes.
Evidence: `ev_339f65cd705e9eede00191f8ca53b8fbf9fbd369d9d29cc3594811dd0f846ba2`.
Summary: `ev_a618a4e57472c7936769176393c1157ce219fad4529e501fdd2ac3214f3cc2c5`.

Tổng cộng năm trong 69 tệp JavaScript được phân tích sâu; giới hạn semantic nodes,
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
| Dự án giữ ngữ cảnh | Dự án văn bản riêng, chụp ngữ cảnh vào tác vụ | Có; chưa tệp/chia sẻ |
| Kết nối ứng dụng | Danh mục mô-đun + gateway MCP hiện có | Có khung; cần endpoint/quyền từng nền tảng |
| Agent dùng mô hình | Adapter OpenAI/Claude/BDSG, công cụ đọc qua nhân | Có mã; cần khóa/mô hình thật |
| Agent đọc MCP bên ngoài | Opt-in từng tác vụ, phạm vi chính xác, kiểm quyền mỗi lần | Có mã và test giả; chưa đầu nối thật |
| Máy tính ảo và trình duyệt agent | Chưa triển khai | Không giả lập |
| Đồng bộ nền tảng và ghi nghiệp vụ tự động | Chưa triển khai | Không tự tuyên bố |

Đây là thiết kế BDSG do mình viết, lấy cảm hứng từ mô hình tương tác đã quan
sát. Không phải mã nội bộ hoặc bản sao hoàn chỉnh của Manus.

Đối chiếu tính năng dựa trên tài liệu chính thức:
[Projects](https://manus.im/docs/features/projects.md) mô tả chỉ dẫn, tệp và
ngữ cảnh dự án; BDSG hiện chỉ có văn bản và bản chụp ngữ cảnh tác vụ.
[Custom MCP](https://manus.im/docs/integrations/custom-mcp.md) mô tả kết nối
hệ thống riêng; BDSG hiện dùng Bearer và danh sách công cụ đọc được duyệt.
[Cloud Browser](https://manus.im/docs/features/cloud-browser.md) mô tả môi
trường trình duyệt thực; BDSG chưa có môi trường đó. Các nhóm chưa triển khai
gồm máy tính/terminal cô lập cho từng tác vụ, điều khiển trình duyệt, tải tệp,
lịch tự động, tác vụ nghiên cứu song song, slide/video và triển khai ứng dụng.
Không có phép đo đầy đủ để tuyên bố tương đương 100% Manus.
