# Trình duyệt và tìm kiếm BDSG — V27

Ngày thực hiện và kiểm thử cục bộ: 17/11/2026.

Ứng dụng tại `/trinh-duyet.html`, gồm HTML/CSS/JavaScript riêng. Diện mạo theo
yêu cầu iOS mới: font hệ thống, nền trắng và xám nhóm, hành động xanh, thanh
công cụ gọn và điều khiển bo góc. Không sử dụng thế giới Manus cũ.

Có tạo, chuyển và đóng tab trong phiên; giới hạn thiết kế là 12 tab. Đóng tab
cuối cùng mở một tab trống. Mỗi tab có lịch sử địa chỉ/tìm kiếm riêng; quay lại,
tiến tới và tải lại hoạt động trong phạm vi ứng dụng. Thanh địa chỉ dùng
`BDSGOSState.normalizeAddress` từ `/he-dieu-hanh-state.js`.

Tìm kiếm gọi `GET /api/catalogue`, cùng nguồn danh mục công khai với cổng ứng
dụng. Chỉ giữ tên, mô tả mục đích, nhóm và URL HTTPS công khai trong bộ nhớ. Đối sánh
tiếng Việt không phân biệt dấu/chữ hoa và yêu cầu khớp mọi từ khóa. Kết quả là
danh mục nền tảng thực, không phải chỉ mục nội dung website hay kết quả web.
Lỗi tải có hướng dẫn thử lại; request có thời gian chờ và bỏ phản hồi cũ.

Liên kết nền tảng, Google và Bing mở tab thiết bị bằng anchor có
`target="_blank" rel="noopener noreferrer"`. Khi nhập URL bất kỳ, giao diện
hiển thị tên miền, địa chỉ và nút **Mở website**. Liên kết dùng cùng chính sách
địa chỉ với webOS: HTTPS, tên miền công khai, không địa chỉ IP/mạng riêng,
không tài khoản trong URL và không cổng tùy ý. Không nhúng website, không
proxy, không đọc nội dung/cookie website khác và không thay CSP. Reload tại
trang địa chỉ chỉ làm mới phần địa chỉ trong ứng dụng; tải website bằng nút mở.

Dấu trang lưu địa chỉ hoặc từ khóa đang xem. Tab, lịch sử và dấu trang chỉ ở
bộ nhớ trang, mất khi reload ứng dụng; không ghi localStorage hay máy chủ.
Lưu địa chỉ không tạo đăng nhập dùng chung hay kết nối dữ liệu.

Điều khiển có nhãn tiếng Việt và focus bàn phím. Phím mũi tên/Home/End chuyển
tab khi focus tab; Ctrl/Cmd+L chọn thanh địa chỉ; Alt+mũi tên quay lại/tiến tới;
Escape thoát thanh địa chỉ. Bố cục điện thoại đặt thanh địa chỉ thành hàng riêng,
vùng bấm chính tối thiểu 44px và tab cuộn ngang. Ứng dụng nhận tùy chọn chữ lớn
và giảm chuyển động từ cửa sổ cha cùng origin, kiểm cả nguồn gửi và loại tin.

Kiểm thử logic: `node --test khong-gian/thu_trinh_duyet.cjs`. Kiểm tra cú pháp:
`node --check khong-gian/trinh-duyet.js`. Các bài kiểm tra dùng dữ liệu tổng
hợp, không gọi website bên ngoài hoặc API tính phí. Kiểm nghiệm giao diện
được thực hiện cùng kiểm tra tích hợp webOS; không triển khai máy chủ thật.
