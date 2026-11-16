# LiteLLM cho BDSG Thanh Hoá

Ghim image theo `source-lock.json`. Bản v1.109.1 đã được kiểm chữ ký bằng
cosign v3.1.4 và khóa công khai tại commit
`e82a3c646908ba0a6ee0beddc4310d7a6cac4065` theo [release chính chủ](https://github.com/BerriAI/litellm/releases/tag/v1.109.1).
Không thay bằng tag latest. Lặp kiểm chữ ký/digest khi nâng phiên bản.

Các unit trong thư mục này dành cho máy Thanh Hoá có Docker và tài khoản
`bdsg-thanhhoa`. Chưa tạo secret hay khóa mẫu trong unit. Khi cài:

1. Giữ release/gateway cũ và snapshot riêng có thử phục hồi.
2. Tải image đã xác minh, không chạy installer của full repo.
3. Đặt các unit `.service`/`.path` vào systemd, daemon-reload và enable
   `bdsg-litellm.path`; service chỉ khởi động khi tệp config riêng tồn tại.
4. Admin BDSG nhập model/key/giá trong Trung tâm AI. File watcher nạp
   config mới; chỉ nhận tác vụ khi `/v1/models` chứa alias đúng revision.
5. Kiểm loopback 4000, thiếu master key bị từ chối, gateway health; dùng
   dữ liệu tổng hợp trước khi nghiệm thu provider bằng khóa của chủ quản.

`chay_litellm.py` không nhận lệnh tùy ý hoặc mount thêm thư mục từ admin.
Nó chạy một image cố định, UID thường, rootfs chỉ đọc, tmpfs giới hạn,
2 GiB RAM và 2 CPU là trần do dự án chọn ngày 17/11/2026. Telemetry tắt;
production không lưu log nội dung. Nhật ký BDSG chỉ giữ tác vụ/model ID,
trạng thái, usage và quota theo quyền, không lưu API key.

Không public LiteLLM, không dùng master key làm API key khách hàng. Chưa
có DB/Postgres hoặc LiteLLM virtual keys/budgets: quota do BDSG giữ trước
atomic. Xem [V23](../../he-dieu-hanh/V23-TRUNG-TAM-AI.md). Khi rollback mã
V22, dừng `bdsg-litellm.path`/`bdsg-litellm.service`, trả unit gateway và
symlink cũ; giữ nguyên dữ liệu mới, không tự khôi phục snapshot vào kho sống.
