# V21 — tích hợp ứng dụng Việt Nam

Phạm vi bắt đầu ngày 16/11/2026. Mục tiêu chủ quản chốt: tăng mã toàn kho
từ **55.311** lên **110.622** dòng có ích, đo cùng phương pháp tại commit
`c8eb9901adc010e16e6a0103ef3bcc368521cdd1`. Đây là mục tiêu công việc đang làm,
không phải kết quả đã đạt. Không sửa ngữ liệu/bộ đánh giá đóng băng để tăng số.

```sh
python3 trien-khai/do_ma_nguon.py --ref c8eb990
python3 trien-khai/do_ma_nguon.py
```

Đo dòng vật lý của `.py/.js/.cjs/.html/.css/.sh`, có mã kiểm thử; không tính
Markdown, JSON cấu hình, ngữ liệu, font, ảnh hoặc nhị phân. Đạt dòng mã chưa
chứng minh nghiệp vụ, quyền tài khoản, bảo mật hoặc chất lượng sản phẩm.

## Mã đang có trong đợt đầu

- Danh mục sản phẩm/API riêng, các thao tác đọc cố định; không dùng URL tùy ý.
- Kho chứng thư AES-GCM gắn chủ quản, provider, connection và revision.
- Cấu hình không tự gọi mạng. Thao tác đọc cần tên quyền trong danh sách đã cấp.
- Nhân vẫn kiểm danh tính, quyền, cổng ghi cấu hình, hạn mức và audit metadata.
  Operator/agent chưa được cấp công cụ tích hợp mới.
- Lượt gọi có request key và revision: đọc lại kết quả không gửi thêm request;
  sai ngữ cảnh bị từ chối. Thu hồi trong khi đọc bỏ phản hồi đến sau.
- Timeout, giới hạn payload/trang, HTTPS có kiểm TLS, DNS công khai được ghim
  và không theo redirect. Không lấy proxy từ môi trường.
- Trạng thái lỗi quyền/429/cooldown lưu bền; không tự phát lại lượt gián đoạn
  hoặc tự chuyển nhà cung cấp. Chỉ metadata xuất hiện trong lịch sử.
- Giao diện mở từ **Quản lý kết nối → Ứng dụng Việt Nam**; giữ giao diện MCP cũ.

## Hợp đồng đầu nối

| Sản phẩm | Mã đọc đã có | Điều kiện còn cần |
|---|---|---|
| Zalo OA | Thông tin OA | OA OAuth, quyền và token thật |
| Zalo ZBS | Metadata dữ liệu mẫu template | Nhóm quyền ZBS đúng ứng dụng |
| Facebook Pages | Thông tin Page, ID/thời điểm hội thoại | Pin Graph version theo App Dashboard; Page token, task và App Review |
| TikTok Display | Hồ sơ, danh sách video | Login Kit và scope thật; khác TikTok Business Messaging |
| KiotViet Retail | Sản phẩm, đơn, hóa đơn bán hàng | Token Public API và đúng retailer |
| Sapo Web | Sản phẩm, đơn | Shop OAuth; không coi là POS/FnB |
| Haravan Omni | Sản phẩm, đơn | Token và com.read_* scopes |
| AMIS ACT | Danh mục vật tư | MISA cấp app_id/token; đối chiếu sandbox và Content-Type trước nghiệm thu |
| payOS | Trạng thái yêu cầu thanh toán, kiểm chữ ký | Client ID/API key/checksum key; không có sandbox riêng |
| VietQR | Danh mục ngân hàng công khai | Chưa phải tra cứu số dư/tên chủ tài khoản |
| MoMo | Query trạng thái, tách sandbox/production | Khóa merchant đúng môi trường; không có capture/refund/transfer |
| meInvoice | Chưa bật công cụ | MISA xác nhận hợp đồng hiện hành |
| VNPAY | Chưa bật công cụ | Chốt production endpoint/hợp đồng/chứng thư |
| Ngân hàng trực tiếp | Chưa bật công cụ | Ngân hàng cấp đặc tả, sandbox, scope và chứng thư/mTLS |

HTTP 200 không tự là thành công nghiệp vụ. Chữ ký payOS phải đạt trước trả
trạng thái; MoMo resultCode=9000 không được tự ghi nhận là đã thanh toán.
Không ghi sổ, chuyển tiền, tạo thanh toán, phát hành/hủy hóa đơn, gửi tin
hoặc đăng bài trong đợt đọc này. Bảng kết quả chỉ giữ các trường cho phép,
không trả Page token, email/số điện thoại/người tham gia hội thoại.

## Cấu hình vận hành

Dependency mật mã dùng pin trong `requirements-office.txt`. Đặt
`BDSG_INTEGRATION_VAULT_KEY_FILE` tới tệp nhị phân ngẫu nhiên 32 byte ngoài
Git/web, chỉ root và tài khoản gateway đọc. Không tái dùng khóa Google.
Backup đã thêm `integrations-vault.key` vào danh sách bí mật cần bảo vệ.
Mất khóa thì chứng thư phải được cấp/lưu lại; không lấy token từ trình duyệt.

Không tự lấy khóa từ tài khoản Codex/plugin, không nhập mật khẩu ngân hàng,
không đề nghị gửi OTP hay khóa vào chat. Token đầu nối đợt này do chủ quản
cấp qua form riêng; tự OAuth/refresh theo từng nhà cung cấp còn ở đợt tiếp.

## Nghiệm thu và phần việc tiếp theo

### Checkpoint đồng bộ đọc

Nhóm công cụ `tich_hop_vn.dong_bo_*` có tạo phiên, danh sách metadata, chạy
một bước, tạm dừng/tiếp tục/hủy và xem từng trang snapshot. Mỗi bước đi qua
nhân với quyền ghi nội bộ; chưa chạy theo lịch. Tạo phiên không gọi mạng.
Cursor lấy từ adapter đã kiểm hợp đồng; không nhận URL phân trang tùy ý.
Chỉ chốt một trang khi revision kết nối và generation phiên còn nguyên.
Thu hồi hoặc hủy khi request đang chạy không chốt dữ liệu đến sau.

Ngày 16/11/2026: giới hạn mỗi phiên tối đa 100 trang, 10.000 bản ghi và
5 MiB kết quả đã chuẩn hóa; mặc định 20 trang. Đạt giới hạn trang thì dừng,
không dùng resume để vượt trần. Lỗi giữ checkpoint và yêu cầu tiếp tục rõ
ràng; Retry-After phải hết trước tiếp tục. Khởi động lại chuyển lượt đang
chạy sang paused/interrupted, không tự gọi lại provider. Snapshot dùng ledger
đã lọc, không sao chép token hoặc tự nhập dữ liệu vào sổ nghiệp vụ. Snapshot
cũ bị chặn khi kết nối hết hạn, đổi revision hoặc bị thu hồi.

Đây là công cụ backend/MCP, chưa có bảng điều khiển đồng bộ trong giao diện.
Chưa phải CDC, snapshot nhất quán xuyên trang hoặc cam kết exactly-once với
provider: dữ liệu phía nhà cung cấp có thể thay đổi giữa các trang.

Kiểm hợp đồng dùng transport và dữ liệu tổng hợp; chưa chứng minh tài khoản
thật hoạt động. Phải kiểm bằng tenant thử đã được cấp trước mở quyền rộng.
Mỗi đầu nối có trạng thái: có mã, đã kiểm hợp đồng, đã đọc thật tại thời điểm
nào; không gộp thành nhãn “kết nối toàn bộ”.

Các chặng để đạt mục tiêu đầy đủ: OAuth/refresh chính thức; webhook ký và
chống lặp; hàng đợi đồng bộ/cursor/checkpoint; ánh xạ dữ liệu và xử lý xung đột;
quyền theo người dùng/dự án; sổ đối soát tài chính không tự hạch toán; adapter
ngân hàng/kế toán theo hợp đồng được cấp; dự thảo và duyệt từng hành động ghi;
kiểm tải/sự cố/thu hồi trên từng môi trường thật. Không đánh dấu hoàn tất chỉ
vì đủ dòng hoặc có tên nhà cung cấp.

## Nguồn chính chủ đối chiếu ngày 16/11/2026

- [Zalo OA](https://docs.zaloplatforms.com/docs/OA/quan-ly/quan-ly-thong-tin-oa/lay-thong-tin-zalo-official-account)
- [Meta Conversations](https://developers.facebook.com/docs/graph-api/reference/page/conversations)
- [TikTok video list](https://developers.tiktok.com/docs/en/tiktok-api-v2-video-list)
- [KiotViet Public API](https://www.kiotviet.vn/huong-dan-su-dung-kiotviet/retail-ket-noi-api/public-api/)
- [Sapo product](https://support.sapo.vn/phuong-thuc-get-cua-product)
- [Haravan orders](https://docs.haravan.com/docs/omni-apis/orders/)
- [MISA ACT](https://actdocs.misa.vn/g2/graph/ACTOpenAPIHelp/index.html)
- [payOS API](https://payos.vn/docs/api/), [chữ ký](https://payos.vn/docs/tich-hop-webhook/kiem-tra-du-lieu-voi-signature/)
- [VietQR banks](https://www.vietqr.io/api-bank)
- [MoMo query](https://developers.momo.vn/v3/vi/docs/payment/api/payment-api/query/)
- [BIDV Open API](https://openapi.bidv.com.vn/)
