# Đóng góp cho Open BDSG

Cảm ơn bạn đã quan tâm. Tài liệu này ngắn có chủ đích: chỉ nêu những điều mà nếu không biết
trước thì đóng góp sẽ bị trả lại.

## 1. Đọc trước khi mở pull request

- [README.md](README.md) — nhất là [bảng trạng thái](README.md#bang-trang-thai-thang-than).
  Dự án **chưa có trọng số**; đừng gửi đóng góp dựa trên giả định là đã có.
- [MODEL-CARD.md](MODEL-CARD.md) — để biết mục nào đang trống và vì sao.

## 2. Lối viết bắt buộc

| Quy tắc | Vì sao |
|---|---|
| Viết bằng **tiếng Việt** | đây là dự án lấy tiếng Việt làm ngôn ngữ thứ nhất |
| **Tên tệp và định danh không dấu** (`huan-luyen/`, `tu_vung`, không phải `huấn-luyện/`) | dấu tiếng Việt trong đường dẫn gây lỗi trên một số hệ tệp và công cụ |
| Chú thích giải thích **VÌ SAO**, không chỉ mô tả mã làm gì | "hàm này lọc rác web" là thừa; "lọc vì 110/5.192 đoạn nguồn ho-so-niem-yet dính menu web, đo 25/09/2026" mới là thông tin |
| **Mỗi con số kèm ngày đo** | số không có ngày đo là số không kiểm chứng được |
| **Không bịa số.** Chưa đo thì ghi "chưa đo" | xem quy tắc kế tiếp |
| **Không hứa điều chưa có** | một bản phát hành nghiêm túc được đánh giá bằng chỗ nó nói **không** |

Pull request nào thêm một con số không có ngày đo, hoặc thêm một lời hứa về tính năng chưa
tồn tại, sẽ bị yêu cầu sửa trước khi xem xét nội dung.

## 3. Thứ TUYỆT ĐỐI không được gửi vào kho

Danh sách này không thương lượng được. Lý do đầy đủ ở
[README](README.md#nhung-gi-co-y-khong-co-trong-bo-nay-va-vi-sao).

- **Dữ liệu khách hàng** dưới mọi dạng — đặc biệt bất cứ thứ gì có nguồn gốc từ CRM.
- **Dữ liệu cá nhân**: email, số điện thoại, địa chỉ nhà, số căn cước. Ngữ liệu hiện tại
  quét được **0 email · 0 số điện thoại · 0 URL nội bộ** (đo 25/09/2026); đừng làm hỏng
  con số đó. Mã số thuế và số ĐKKD doanh nghiệp thì được — đó là thông tin đăng ký công khai.
- **Văn bản máy sinh bởi mô hình bên thứ ba.** Kho này đã loại 6.055 đoạn vì lý do ấy.
  Đóng góp máy sinh cũng bị loại theo đúng lý do.
- **Nội dung có giấy phép của bên thứ ba** mà bạn không có quyền tái phát hành: bài báo,
  tài liệu nội bộ doanh nghiệp, sách.
- **Khoá, mật khẩu, chuỗi kết nối.** `.gitignore` chặn các mẫu thường gặp, nhưng nó không
  thay được việc bạn tự kiểm trước khi commit.
- **Tệp trọng số hoặc bất kỳ tệp nhị phân lớn nào.** Trọng số đi lên kho trọng số, không đi
  vào git.

## 4. Bộ đánh giá 227 câu đã đóng băng

Bộ đánh giá được đóng băng ngày **22/09/2026**. **Không sửa, không thêm, không bớt câu hỏi.**
Sửa bộ câu hỏi sau khi đã đo là làm mất khả năng so sánh giữa các lần đo — đường cơ sở M3
sẽ trở thành vô giá trị.

Muốn thêm câu hỏi thì mở issue đề xuất **một bộ thứ hai**, đặt tên khác, có ngày đóng băng
riêng.

## 5. Quy trình

1. **Mở issue trước** nếu thay đổi động tới ngữ liệu, tokenizer, hay bộ đánh giá. Với sửa
   lỗi chính tả hay lỗi liên kết thì gửi thẳng pull request.
2. Làm việc trên một nhánh riêng.
3. Trong mô tả pull request, ghi rõ: **đã đo gì, đo ngày nào, bằng lệnh nào**.
4. Nếu bạn thay đổi một con số đang có trong README hoặc model card, **đính kèm phép đo mới**.
   Không nhận thay đổi số liệu không kèm cách tái lập.

Thư mục `huan-luyen/`, `bo-du-lieu/`, `danh-gia/`, `cong/` do các nhóm của dự án giữ theo
từng mốc M2–M6. Trước khi gửi pull request vào các thư mục đó, hãy mở issue để tránh trùng việc.

## 6. Giấy phép của phần bạn đóng góp

Khi gửi pull request, bạn đồng ý rằng:

- phần **mã** bạn đóng góp được cấp phép theo **Apache License 2.0** ([LICENSE-CODE](LICENSE-CODE));
- phần **dữ liệu** bạn đóng góp vào `bo-du-lieu/` được cấp phép theo
  **CC BY 4.0** ([LICENSE-DATA](LICENSE-DATA));
- bạn **có quyền** cấp phép như vậy cho phần mình gửi.

Điểm cuối là điểm hay bị bỏ qua nhất. Nếu bạn không chắc mình có quyền tái phát hành một
tập dữ liệu, thì câu trả lời là **đừng gửi** và hãy mở issue hỏi trước.
