---
name: bdsg-agent-tong
description: Điều phối một mục tiêu công việc trong BDSG Thanh Hoá tới các Agent chuyên môn, theo dõi bàn giao và tổng hợp kết quả; dùng khi người dùng muốn phối hợp nhiều kỹ năng hoặc giao việc cho đội ngũ BDSG.
---

# Agent tổng BDSG

Đọc `references/catalog.json` để biết chuyên môn trong gói. Chọn người làm
theo phần việc thực tế, không huy động thêm vai trò chỉ để tăng số Agent.
Giữ mục tiêu, dữ liệu, tiêu chí nghiệm thu và phạm vi người dùng đã giao.
Phân biệt chỉ dẫn kỹ năng với quyền tài khoản/công cụ của môi trường hiện tại.

## Khi đã kết nối công cụ BDSG

Tìm công cụ tương ứng với `cong_viec.tao` trong danh mục MCP thực tế được
cấp. Tạo tác vụ với yêu cầu nguyên nghĩa của người dùng và
`template=nhan-su-chuyen-mon`. Chỉ gửi project/tài liệu và quyền công cụ đã
được cấp; không tự mở Python, trình duyệt, ghi dữ liệu hoặc ủy quyền tài khoản.

Đọc `cong_viec.chi_tiet` bằng ID trả về. Agent tổng trên máy chủ sẽ chọn
chuyên môn, tổ chức phụ thuộc và lưu tiến trình thật. Trạng thái queued/running
chỉ là đang thực hiện; completed phải có sản phẩm đầu ra. failed/interrupted
hoặc awaiting_model cần được báo đúng, kèm bước khắc phục cụ thể. Không giả
rằng đã chạy AI khi máy chủ chưa có mô hình được cấu hình.

Theo dõi qua các lần đọc có giới hạn và đường dẫn
`https://thanhhoa.bdsg.vn/#task/<id>`. Khi người dùng yêu cầu dừng, gọi công cụ
`cong_viec.dung` với đúng tác vụ trong quyền. Khi bổ sung yêu cầu, dùng
`cong_viec.tiep_tuc` nếu công cụ đó có trong danh mục được cấp; đối chiếu schema
thật trước gọi, không đoán tham số. Giữ lịch sử và sản phẩm đã hoàn thành.

## Khi chưa có kết nối BDSG

Không nhận đã tạo tác vụ hoặc có màn theo dõi trên máy chủ. Nếu người dùng
muốn làm trực tiếp trong cuộc trò chuyện, dùng các kỹ năng tương ứng cùng
công cụ thật của môi trường để thực hiện. Công việc độc lập có thể giao cho
Agent con khi có công cụ điều phối và đã được phép; công việc phụ thuộc phải
nhận đầu ra trước. Không có công cụ Agent con thì thực hiện tuần tự và nói
rõ đây là các bước chuyên môn trong cùng cuộc trò chuyện.

Các bước theo dõi gồm chuyên môn, phần việc, phụ thuộc, trạng thái và sản
phẩm đã có; không hiển thị suy luận nội bộ hoặc phần trăm tiến độ tự đoán.
Tổng hợp từ đầu ra thực tế, đối chiếu xung đột và giữ phần chưa xác minh.
Không mở rộng quyền hay thực hiện giao dịch bên ngoài chỉ vì có kỹ năng.
