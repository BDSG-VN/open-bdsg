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
quyền trong prompt nguồn. Ngày 17/11/2026, `dung_bo_nhan_su.py` tạo 38 thư mục SKILL.md và
catalog có hash. Hệ thống kiểm hash trước nạp; không chạy mã kèm nguồn.
Các quy trình đã chuẩn hóa có 86 tham chiếu tới đủ 36 nguồn. Đây là tích
hợp phương pháp chuyên môn đã chọn, không phải kích hoạt mọi script hoặc
mọi kỹ năng của từng kho. Có thêm kỹ năng Agent tổng cho gói dùng ngoài.

```sh
python3 trien-khai/dung_bo_nhan_su.py
python3 he-dieu-hanh/thu_doi_ngu.py -v
```

## Lõi đang có

- Công cụ `nhan_su.danh_sach`, `nhan_su.chi_tiet` đi qua nhân xác thực.
- `nhan_su.xuat_bo` xuất ba gói kỹ năng: Agent Plugins, thư mục Codex và
  các zip từng kỹ năng cho Claude. Có 38 chuyên môn và một kỹ năng điều
  phối; giữ giấy phép nguồn, SHA, không chứa chứng thư hoặc dữ liệu vận hành.
- Tác vụ `template=nhan-su-chuyen-mon` dùng Agent tổng lập kế hoạch ngữ
  nghĩa qua mô hình đã cấu hình, chọn từ catalog được duyệt. JSON kế hoạch
  có ID, phần việc, sản phẩm và phụ thuộc; không nhận công cụ hoặc quyền
  do planner tự đề nghị.
- Tối đa sáu chuyên môn/lượt, ba chuyên môn song song; phụ thuộc phải có
  đầu ra thật trước bàn giao. Mỗi chuyên môn có ngữ cảnh riêng, cùng quyền
  đã cấp cho tác vụ; không có đệ quy tự phân việc cho tác vụ khác.
- Agent tổng nhận bản xem trước tài liệu đã chọn và hai kết quả gần nhất để
  phân công đúng chuyên môn. Mỗi bản xem trước tối đa 2000 byte UTF-8, có
  đánh dấu nội dung chưa đầy đủ; chuyên môn vẫn nhận ngữ cảnh tác vụ gốc.
- Mỗi kết quả chuyên môn tối đa 6000 byte UTF-8; vượt hạn báo lỗi, không
  cắt thầm. Agent tổng tổng hợp từ kết quả thật. Có lưu tên, hash kỹ năng,
  phần việc, trạng thái, thời điểm và đầu ra của từng vai trò.
- Mọi lượt gọi mô hình vẫn giữ ngân sách/usage hiện có; hủy hoặc thu hồi
  danh tính chặn bước tiếp theo. Lỗi chuyên môn chặn phần phụ thuộc và
  không chạy tổng hợp thành công giả.
- Kết quả vai trò thành tệp Markdown ngay khi bàn giao xong, giữ được khi
  phần tiếp theo thất bại; báo cáo tổng chỉ có khi tổng hợp thành công. Tiếp tục
  tạo lượt mới, giữ lịch sử; restart đánh dấu đội đang chạy bị gián đoạn.
  Khi nhiều chuyên môn kết thúc cùng đợt, hệ thống thu hết kết quả thành
  công trước khi chuyển lỗi của chuyên môn khác sang trạng thái thất bại.
- Không có mô hình: trạng thái chờ cấu hình, không tạo kết quả chuyên gia.

## Giao việc và theo dõi

Chế độ mặc định của tác vụ mới là Agent tổng/chuyên môn; các quy trình cũ
vẫn chọn rõ bằng `template`. Trang **Nhân sự Agent** có tìm kiếm, nguồn kỹ
năng và tải bộ kỹ năng. Trang tác vụ hiển thị Agent tổng, từng vai trò,
phụ thuộc, trạng thái, thời gian, sản phẩm, dừng và lịch sử lượt tiếp tục.
Không hiện suy luận nội bộ hay phần trăm hoàn thành tự đoán.

Đóng gói ngoại tuyến:

```sh
python3 trien-khai/xuat_bo_nhan_su.py --destination /thu-muc-moi
```

Gói Agent Plugins theo [đặc tả công bố](https://developers.openai.com/plugins/build/plugins),
kỹ năng theo [Agent Skills](https://agentskills.io/specification).
Claude dùng [custom skills](https://platform.claude.com/docs/en/managed-agents/skills).
Gói chưa được công bố lên thư mục plugin ChatGPT và chưa nghiệm thu nhập
trên mọi sản phẩm/tài khoản. Cần kết nối công cụ và xác thực riêng nếu dùng
dữ liệu sống; đóng gói không cấp quyền tài khoản.

## Nghiệm thu và giới hạn

Đã kiểm cấu trúc các kỹ năng, kế hoạch đơn/đa chuyên môn, DAG sai, song song,
bàn giao, hủy, lỗi, lưu sản phẩm từng phần, lịch sử, ACL và restart bằng
mô hình tổng hợp. QA gateway thật trong kho riêng kiểm danh mục/tìm kiếm,
mặc định giao việc, tiến trình/phụ thuộc, tải zip, kết quả từng Agent,
dừng, tiếp tục, đăng xuất và không tràn ngang trang trên desktop/mobile.

Máy chủ chưa có cấu hình mô hình AI được chủ quản cấp nên còn chờ lượt
nghiệm thu mô hình thật. Kiểm tổng hợp không chứng minh chất lượng suy
luận của mọi mô hình hoặc khả năng thao tác Office/CRM chưa được cấp.
Kỹ năng không tự thêm công cụ còn thiếu; khi chỉ có văn bản, phải trả nội
dung/dự thảo và ghi rõ chưa tạo tệp hoặc chưa thực hiện nghiệp vụ.
