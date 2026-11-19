# V29 — Phiên web và các quyền đã cấp

Đối chiếu mã nguồn cục bộ ngày 17/11/2026, trước khi tích hợp quản lý phiên
web V29. Chỉ đọc source; không đọc CSDL, cấu hình riêng hoặc máy chủ, không
gọi Google, Office hay API AI thật. Số dòng là mốc của lần đối chiếu này;
tên hàm là điểm tìm lại khi bản V29 làm dịch chuyển mã.

## Kết luận dùng cho bản V29

Xóa một hàng `phien` thu hồi cookie đó ở lần xác thực tiếp theo. Không đồng
nghĩa dừng mọi công việc hoặc thu hồi mọi quyền mà trình duyệt từng nhận.
Phạm vi giao diện nên ghi: **“Thu hồi phiên đăng nhập web. Công việc đang
chạy và kết nối ứng dụng có thể tiếp tục; quản lý chúng riêng.”**

Không gọi `thu_hoi_agent`, `cancel_owner`, `google_office.forget` hoặc
`khoa_phien(identity=...)` khi chỉ thu hồi một phiên web: các thao tác đó có
phạm vi danh tính, rộng hơn thiết bị đang chọn.

## Bằng chứng và giới hạn hiện tại

| Khả năng | Hành vi đọc được từ source | Tác động khi xóa phiên web |
|---|---|---|
| Cookie web | `Kho.dang_xuat` chỉ `DELETE FROM phien WHERE hash=?`; `tu_phien` tìm hash còn hạn rồi kiểm operator còn hoạt động. [kho.py](../../he-dieu-hanh/kho.py), dòng 100–119, 157–159. HTTP lấy cookie qua `actor()`. [may_chu.py](../../he-dieu-hanh/may_chu.py), dòng 184–199, 398–405, 482–487. | Yêu cầu mới dùng cookie bị xóa không xác thực được. Yêu cầu đã lấy `actor` trước thời điểm xóa không tự bị hủy bởi câu DELETE này. |
| Google Drive đang chờ đồng ý | `start` lưu hash phiên khởi tạo trong state; callback kiểm đúng binding, thời hạn và hash phiên trước đổi code. Sau đổi code kiểm lại; `_store` còn kiểm trong `BEGIN IMMEDIATE` trước ghi token. [google_office.py](../../he-dieu-hanh/google_office.py), dòng 205–232, 264–349. | Chặn callback lưu kết nối mới nếu phiên gốc bị xóa trước giao dịch lưu. Không phải thu hồi một kết nối Google đã lưu thành công trước đó. |
| Google Drive đã kết nối / Picker | Vault dùng khóa `actor`; `_access` nạp/refresh theo actor; `picker` trả access token cho trình duyệt. Chỉ `disconnect` gọi `/revoke` rồi xóa vault/state; `forget` xóa cục bộ. [google_office.py](../../he-dieu-hanh/google_office.py), dòng 234–247, 351–408. | API BDSG mới cần phiên hợp lệ; DELETE phiên không gọi Google revoke, không xóa vault theo actor, không vô hiệu hóa token đã giao cho Picker. Không có bằng chứng source để cam kết token bên Google đã ngừng dùng ngay. |
| Chốt UI Editor / Picker | Guard ghi nhớ `actorId`; kiểm `/api/me` khi khởi tạo, focus và `check()`; nghe BroadcastChannel/storage; 401 hoặc `identity_changed` làm invalidation. Editor hủy iframe; Picker đóng hộp thoại và xóa tham chiếu token/selection. [bao-ve-phien.js](../../khong-gian/bao-ve-phien.js), dòng 6–70; [soan-thao.js](../../khong-gian/soan-thao.js), dòng 15–24; [google-picker.js](../../khong-gian/google-picker.js), dòng 9–20, 103–127. | Đây là chốt phía trình duyệt. Guard không có vòng kiểm định kỳ và chỉ so actor, không so phiên; đăng nhập lại cùng actor không được phân biệt. Xóa tham chiếu JS không phải revoke token phía Google hoặc quyền engine đã nhận. |
| Cổng engine Office | `/api/office-engine-auth` lấy actor từ cookie; `engine_access` kiểm file tương ứng key và phiên Office còn active. [may_chu.py](../../he-dieu-hanh/may_chu.py), dòng 292–294; [soan_thao_office.py](../../he-dieu-hanh/soan_thao_office.py), dòng 179–200. | Lần kiểm cổng mới bị từ chối nếu cookie không còn hợp lệ. Đoạn mã này không đóng một kết nối engine đã được chấp nhận trước đó. |
| Cấu hình / nguồn / callback Office | Office tái sử dụng một key active theo file; member là `(key, actor)`, user engine là actor. Key/cap và JWT config có hạn riêng; `_row` kiểm state/hạn Office. Nguồn cần JWT download và cap, rồi kiểm quyền file bằng actor lưu trong Office; callback cần JWT engine, chọn member/request rồi kiểm quyền và revision. [soan_thao_office.py](../../he-dieu-hanh/soan_thao_office.py), dòng 28–38, 63–70, 95–177, 323–371, 390–428. | Nguồn và callback không tra hàng phiên web gốc. DELETE phiên không đổi state/key/cap hoặc member, vì thế không chứng minh nguồn hay callback đã bị thu hồi. Callback vẫn phải qua các chốt quyền, revision và CAS đang có. |
| AI / tác vụ | Khi tạo, worker nhận bản sao actor; `_auth` và hàm `cancelled` kiểm danh tính hoạt động qua `verify_actor`, cờ cancel và trạng thái đóng. `verify_actor` dùng `active_actor`, không dùng hash phiên. [cong_viec.py](../../he-dieu-hanh/cong_viec.py), dòng 162–173, 395, 481–518, 788–795; [may_chu.py](../../he-dieu-hanh/may_chu.py), dòng 60–66; [hanh_dong.py](../../he-dieu-hanh/hanh_dong.py), dòng 10–23. | Logout không đặt cancel, không gọi `cancel_owner`. Tác vụ đã giao không gắn với phiên web tạo nó và có thể tiếp tục dưới danh tính còn hoạt động. |
| Trình duyệt tác vụ / hành động đã duyệt | Adapter và worker dùng owner/task, có `revoke-owner`/`revoke-task`; hành động duyệt dựng lại `active_actor(owner)` và kiểm payload/task, không có hash phiên web. [trinh_duyet.py](../../he-dieu-hanh/trinh_duyet.py), dòng 27–40, 88–100, 143–174; [trinh_duyet_worker.py](../../he-dieu-hanh/trinh_duyet_worker.py), dòng 176–182, 231–264; [hanh_dong.py](../../he-dieu-hanh/hanh_dong.py), dòng 145–191. | Không có đường logout → revoke browser hoặc hủy phê duyệt. Đường thu hồi danh tính riêng mới nối cancel tác vụ, revoke browser và forget Google. [may_chu.py](../../he-dieu-hanh/may_chu.py), dòng 81–88. |
| MCP Bearer | `/mcp` dùng `tu_token` thay cho cookie; token hash và active của agent nằm riêng với bảng phiên. [may_chu.py](../../he-dieu-hanh/may_chu.py), dòng 191–199, 394; [kho.py](../../he-dieu-hanh/kho.py), dòng 161–193. | Thu hồi cookie không thu hồi chứng thư MCP. Đây là một thông tin xác thực độc lập. |

Kiểm thử sẵn có xác nhận consent Google bị từ chối sau logout trước đổi code:
`test_logout_denies_pending_consent_before_token_exchange`,
[thu_google_office.py](../../he-dieu-hanh/thu_google_office.py), dòng 98–105.
Không suy từ test đó ra việc token đã phát, callback Office hoặc AI đã dừng.

## Ranh giới mô-đun tiếp theo

Thực hiện tiếp ở **quyền tham gia một phiên Office**, trước khi mở rộng thành
điều phối thu hồi tất cả khả năng. Mô-đun cần sở hữu việc cấp, kiểm và thu hồi
một lượt tham gia, tách biệt với key tài liệu dùng chung và với actor. Mỗi lượt
tham gia cần một định danh riêng, liên kết nội bộ với phiên web tạo nó; mã
định danh công khai không được là cookie hoặc hash dùng xác thực cookie.

Giao diện nhỏ nên thể hiện được ba việc: cấp lượt tham gia đã kiểm quyền;
kiểm lượt đó còn hợp lệ tại biên HTTP và trước commit; thu hồi đúng các lượt
thuộc phiên đích và trả công việc ngắt engine cần thực hiện sau commit. Giữ
JWT engine, source cap, CAS và callback ledger bên trong mô-đun, tránh để
route logout tự cập nhật nhiều bảng Office.

Điều kiện phải giải quyết trước khi quảng cáo “đóng Office trên thiết bị”:

- Hiện `office_editor_members` chỉ có `(key,actor)` và config đặt
  `editorConfig.user.id=actor`. Hai trình duyệt cùng actor không có định danh
  engine tách biệt. Cần ánh xạ participant engine riêng về actor và xác định
  callback/status save nào thuộc participant còn hiệu lực; không lấy `users[0]`
  làm bằng chứng của một phiên web cụ thể.
- `khoa_phien` khóa toàn bộ key nếu tìm thấy member; `ngat_phien` gửi lệnh
  `drop` theo key, không chỉ participant. [quyen_office.py](../../he-dieu-hanh/quyen_office.py),
  dòng 11–55. Không tái sử dụng nguyên đường này cho thu hồi một thiết bị.
- Cần xác minh hành vi engine thực tế về ngắt participant, callback khi có
  nhiều người và socket đã mở bằng môi trường thử nghiệm; source gateway
  hiện tại không đủ bằng chứng để chọn lệnh engine hay cam kết ngắt tức thì.
- Nếu nội dung coedit đã trộn thay đổi của participant bị thu hồi và người
  hợp lệ, phải chốt chính sách snapshot/ghi trước triển khai. Không loại cả
  tài liệu hoặc ghi nhận toàn bộ snapshot là của một phiên mà không có chứng cứ.

Google vault, MCP token và tác vụ dài hạn tiếp tục có chính sách riêng theo
danh tính. Khi cần điều phối thêm, chỉ nối các khả năng đã có provenance phiên
và chính sách rõ; không suy luận từ “cùng owner” thành “do phiên bị thu hồi”.

## Các ca đối kháng cần có cho đợt triển khai tiếp

Các mục dưới là đề xuất kiểm thử, chưa được thực hiện bởi ghi chú này.

1. Hai cookie cùng actor: thu hồi A; API/engine handshake mới của A bị từ
   chối, B vẫn đọc/ghi được; MCP token độc lập vẫn dùng được theo quyền cũ.
2. Một cookie A đã hết hiệu lực rồi đăng nhập lại cùng actor thành C: trang
   Editor/Picker cũ phải nhận biết grant cũ khi chính sách yêu cầu, dù actor
   không đổi; không để actor guard thay cho kiểm grant phía máy chủ.
3. Google consent: thu hồi trước đổi code, trong lúc đổi code và ngay trước
   `_store`; không lưu kết nối sau thu hồi. Nếu vault đã commit trước thu hồi,
   giữ đúng chính sách theo actor, không xóa kết nối của B.
4. A và B cùng actor, cùng key tài liệu, thêm C khác actor: thu hồi A chỉ
   khóa participant A; B/C vẫn lưu được. Thử source URL, JWT config cũ, socket
   cũ và callback đến chậm; không dùng `drop(key)` để vượt qua bài kiểm này.
5. Callback A đang tải snapshot trong lúc thu hồi: kiểm lại grant trước
   commit, giữ CAS revision và tính lặp an toàn. Callback hợp lệ của B vẫn
   commit; callback cũ không ghi đè revision mới; retry callback đã commit
   không sinh thêm phiên bản.
6. Công việc do A giao nhưng được xác định chạy độc lập theo owner: thu hồi
   A không hủy nó hoặc browser của B. Với loại công việc tương lai được đánh
   dấu phụ thuộc phiên, chứng minh chỉ loại đó nhận cancel/revoke và xử lý rõ
   lời gọi bên ngoài đang chạy; không hứa hoàn tác hiệu ứng đã gửi đi.
7. Engine ngắt mạng, restart sau giao dịch thu hồi: các chốt DB vẫn từ chối
   grant bị thu hồi, ngắt sau commit có thể thử lại an toàn, không tự cấp lại
   quyền cũ và không khóa participant hợp lệ còn lại.
