# Kiểm nghiệm lõi V14 — 15/11/2026

Bản này tiếp tục giao diện V13, tập trung vào khôi phục tác vụ, giới hạn đầu ra
và trạng thái dự án đã lưu trữ. Không sửa quyền truy cập máy chủ hoặc dữ liệu
khách hàng. Các tài khoản và bản ghi nghiệm thu riêng có nhãn `KIEM THU V14`.

## Lỗi được tái hiện và sửa

1. Python chạy thêm trên công việc đã hoàn tất có thể giữ `runtime_running`
   sau khi gateway chết. Lần khởi động mới nay giải phóng cờ, đánh dấu gián
   đoạn, giữ kết quả cũ và cho phép chủ quản tiếp tục; không tự chạy lại mã.
   Bài kiểm đợi dấu do Python thực trong vùng cách ly ghi ra rồi mới gây crash.
2. Kiểm hạn mức trước khi chạy chưa đủ: 79 tệp cộng lô 8 tệp hoặc gần 8 MiB
   cộng lô mới có thể vượt hạn. Kiểm số tệp và byte UTF-8 nay nằm cùng khóa
   với thao tác lưu, áp dụng cả báo cáo tác vụ và Python. Từ chối nguyên lô
   vượt hạn, giữ nguyên tệp cũ và giải phóng cờ runtime.
3. Xưởng vẫn hiện tải tài liệu khi chỉ còn dự án lưu trữ. Nay hiển thị đường
   tạo/khôi phục dự án, chỉ hiện tải lên khi có dự án đang hoạt động.

Ba lỗi đã có bài hồi quy thất bại trên mã trước sửa và qua trên bản sửa.
`thu_loi_van_hanh.py` kiểm hai hạn mức riêng; `thu_xuong.cjs` kiểm cả dự án
lưu trữ và dự án hoạt động. Không dùng thời gian ngủ cố định để kết luận Python
đã bắt đầu chạy.

## Ma trận chức năng

“Máy chạy” là gọi HTTPS origin có xác minh chứng thư, dùng dữ liệu tổng hợp.
“Bộ kiểm” là chạy công cụ/HTTP/worker với kho riêng; không phải kết nối nghiệp
vụ bên ngoài. Không tính ca bị bỏ qua thành đạt.

| Chức năng | Bằng chứng | Giới hạn |
|---|---|---|
| Đăng nhập, đăng xuất, thu hồi phiên | Máy chạy; bộ kiểm HTTP | Không thay mật khẩu của chủ quản |
| Danh mục nền tảng và trạng thái kết nối | Máy chạy; tìm kiếm JS | Liên kết web không chứng minh đồng bộ dữ liệu |
| Dự án: tạo, sửa, lưu trữ, khôi phục | Máy chạy; bộ kiểm dự án | Dự án lưu trữ chặn tạo việc mới |
| Tài liệu: tải, phiên bản, tải xuống/SHA | Máy chạy; bộ kiểm tài liệu/khôi phục | PDF ảnh quét/OCR chưa hỗ trợ |
| Quyền người xem, chia sẻ, thu hồi | Máy chạy; bộ kiểm quyền | Không xóa bản ngữ cảnh đã giao trước đó |
| Giao việc, kết quả bền vững, tiếp tục | Máy chạy; bộ kiểm tác vụ | Khi chưa có AI chỉ chạy quy trình có sẵn |
| Hủy Python, thời gian, inode, không mạng | Bộ kiểm Linux non-root thực | Không phải máy ảo đa mục đích |
| Khôi phục khi Python thực đang chạy | Bài hồi quy crash mới | Không tự thực thi lại tác động |
| Tổng CSV và lưu tệp Python | Máy chạy, đầu ra 45 từ CSV 10/20/15 | Dùng `open()` ghi tệp đã khai báo; không tạo tệp tùy ý |
| Giới hạn 80 tệp/8 MiB mỗi tác vụ | Hai bài hồi quy runtime thực | Từ chối toàn bộ lô vượt hạn |
| Trình duyệt mở, quan sát, đóng | Máy chạy với example.com; Chromium sandbox | Không thử dữ liệu/đăng nhập của khách |
| Form, nonce, quyền phê duyệt browser | 9 bài Chromium với trang thử | Không nguyên tử với JavaScript và máy chủ đích |
| Phê duyệt yêu cầu kinh doanh một lần | Máy chạy; bộ kiểm claim/restart | Tác động bên ngoài chưa rõ không tự gửi lại |
| Yêu cầu kinh doanh và đổi chặng | Máy chạy, bản ghi tổng hợp | Không xác nhận nghiệp vụ khách hàng thật |
| Hộp thư agent | Máy chạy với tài khoản thử | Hộp thư không đồng nghĩa mô hình AI đã hoạt động |
| Giao việc con với quyền dự án | Máy chạy; bộ kiểm ACL | Không tự mở thêm quyền cho tác vụ con |
| Lịch tạo/tắt và chống chạy trùng | Tạo/tắt trên máy chạy; claim qua bộ kiểm | Không chờ 15 phút rồi tuyên bố đã chạy lịch thật |
| Mức sử dụng và nhật ký | Máy chạy; bộ kiểm che dữ liệu nhạy cảm | Token dự trù không phải trần tiền chính xác |
| MCP gateway: giao thức, danh tính, quyền | Bộ kiểm HTTP/MCP | Chưa có đầu nối nghiệp vụ thật được duyệt |
| OpenAI/Claude/BDSG adapter và lỗi API | Bộ kiểm transport mô phỏng | Máy chạy chưa cấu hình model/key, chưa nghiệm thu AI trả phí |
| Xưởng và các trang chính | Kiểm trình duyệt thật có render | Chromium desktop, viewport emulation; chưa thiết bị cảm ứng vật lý/Safari |

## Tái lập kiểm nguồn

Theo `.github/workflows/thanhhoa.yml`: năm chương trình tự kiểm nhân, gateway,
đóng gói, cú pháp JavaScript và hai chương trình hồi quy giao diện. CI thường
bỏ qua runtime/Chromium nếu không có môi trường riêng.

Trên Linux đã cài bubblewrap/seccomp, bằng tài khoản không phải root:

```sh
BDSG_TEST_RUNTIME=1 python3 -m unittest discover -s he-dieu-hanh -p 'thu_*.py' -v
```

Với Playwright và Chromium sandbox đã cài, bằng tài khoản worker không phải root:

```sh
BDSG_TEST_BROWSER=1 python3 -m unittest discover -s he-dieu-hanh -p 'thu_browser_bieu_mau.py' -v
```

Lượt kiểm Linux có runtime: 79 bài qua, 9 bài Chromium được bỏ qua trong lượt
gateway và chạy riêng đủ 9 bài qua. Thêm 4 bài đóng gói và 2 chương trình JS:
94 kiểm tra đạt, cộng 5 chương trình tự kiểm nhân. Bài crash được chạy lại sau
khi thêm dấu xác nhận Python đã khởi chạy: đỏ trên mã cũ, xanh trên bản sửa.

## Phát hành và rà soát

Trên máy chạy, 16 nhóm thao tác trong ma trận đã qua bằng dữ liệu tổng hợp.
Đã tắt lịch thử, thu hồi mọi tài khoản thử V14 và lưu trữ dự án thử. Hai kết
quả của tác vụ cũ vẫn còn. Giao diện có 15 bước đạt: đăng nhập qua form, bốn
trang chính, trạng thái chỉ có dự án lưu trữ, cả bảy thẻ Xưởng, mở thiết lập
giao việc và đăng xuất. Kiểm ở 1280/768/390px không tràn ngang, không lỗi JS.
Đây là Chromium thực và giả lập kích thước màn hình, không phải thử cảm ứng
trên điện thoại vật lý. Bài kiểm chủ động giãn yêu cầu để tuân thủ hạn mức;
không suy ra đã kiểm tải đồng thời lớn hoặc đo hiệu năng ở quy mô khách thật.

Lõi được phát hành từ `901e34188c8f2fd3c5379a7818187b55fb815f25`.
Hai lượt rà riêng: chuẩn mã không còn phát hiện; đối chiếu yêu cầu phát hiện
một điểm yếu bằng chứng crash và đã kiểm tra lại bản bổ sung là đạt.

Backup SQLite nhất quán, SHA-256, bản unit cũ, đường giao diện cũ và rollback
được chuẩn bị trước thay đổi. Unit vẫn giữ non-root, cách ly và `AF_NETLINK`;
không thay worker browser hoặc mở thêm cổng. Rollback trả mã/unit/giao diện cũ,
giữ dữ liệu hiện tại; không tự ghi đè DB bằng bản cũ. Sổ tay giữ nguyên hash.
Kết quả gốc nằm trong thư mục quản trị riêng, không công khai ảnh phiên chủ
quản hoặc dữ liệu xác thực trong kho mã.

Chưa nghiệm thu B01–B10 trong `NGHIEM-THU-V11.md` bằng AI và đầu nối dữ liệu
thật. Không kết luận “mọi nền tảng đã liên thông” hoặc “an toàn tuyệt đối”.
