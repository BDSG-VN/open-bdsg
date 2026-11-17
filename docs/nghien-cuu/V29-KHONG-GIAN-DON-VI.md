# V29 — Không gian dữ liệu của doanh nghiệp, đơn vị

Ngày đối chiếu source: 17/11/2026. Yêu cầu chủ quản: mỗi doanh nghiệp/đơn vị
có không gian dữ liệu riêng; chia sẻ khi được cấp quyền. Đây là đề xuất pha
triển khai, **chưa phải tính năng cách ly đơn vị đã hoàn thành**. Không đọc dữ
liệu vận hành hoặc bí mật; số dòng dưới đây là mốc lần đọc, tìm lại bằng tên
hàm khi mã thay đổi. Dùng kỹ năng `codebase-design` để chọn một seam có
Interface nhỏ, che việc kiểm thành viên, quyền tài nguyên và giao dịch.

## Hiện trạng đã có và phần còn thiếu

| Phần | Đã có trong source | Khoảng trống với yêu cầu đơn vị |
|---|---|---|
| Danh tính / phiên | `chu`, `agents`, `web_users`, `phien` dùng mã danh tính toàn cổng; actor web có id/role/name. [kho.py](../../he-dieu-hanh/kho.py), dòng 29–38, `tu_phien`; Google login ánh xạ `(issuer,subject)` sang actor và cấp phiên. [dang_nhap_google.py](../../he-dieu-hanh/dang_nhap_google.py), dòng 85–90, 181–200. | Các đường này chưa chứa đơn vị đang thao tác, thành viên đơn vị hoặc vai theo đơn vị. Đăng nhập Google thành công không chứng minh được mời vào doanh nghiệp. |
| Dự án / chia sẻ | `du_an.owner`; `du_an_members(project_id,identity,role)` với viewer/editor. `authorize` và `list` cho `quan-tri` truy cập toàn cổng. [du_an.py](../../he-dieu-hanh/du_an.py), dòng 15–19, 51–85, 175–200. | Chia sẻ hiện tại là giữa các danh tính trên cổng, chưa phải chia sẻ có đơn vị nguồn/đích và chính sách xuyên đơn vị. Không dùng project như tenant: một đơn vị có thể có nhiều project. |
| Tác vụ / lịch / AI | Tác vụ có owner và JSON document; quyền detail theo owner hoặc `quan-tri`. Lịch chạy dựng lại actor từ owner. [cong_viec.py](../../he-dieu-hanh/cong_viec.py), dòng 78–81, 236–239, 267–269, 398–405; [lich_cong_viec.py](../../he-dieu-hanh/lich_cong_viec.py), dòng 17, 25–27, 143. Ngân sách AI ghi theo owner. [ngan_sach_ai.py](../../he-dieu-hanh/ngan_sach_ai.py), dòng 57–67, 83–101. | Cùng một người làm cho hai doanh nghiệp chưa có phạm vi tác vụ, lịch, ngữ cảnh hoặc ngân sách riêng theo đơn vị. Worker không được suy đơn vị từ phiên web hiện tại. |
| Tài liệu / Office | Document/file gắn project; Office kiểm lại quyền project và danh tính trong giao dịch. [tai_lieu.py](../../he-dieu-hanh/tai_lieu.py), dòng 26–36; [van_phong.py](../../he-dieu-hanh/van_phong.py), dòng 44–80, 155–191. Phiên coedit có key theo file, member theo actor. [soan_thao_office.py](../../he-dieu-hanh/soan_thao_office.py), dòng 28–38, 95–124. | Có thể làm điểm tựa cho kiểm quyền tài nguyên; chưa có bất biến file/project/đơn vị cùng phạm vi hoặc grant coedit gắn đơn vị. |
| Google Drive | Vault mã hóa với actor làm dữ liệu xác thực kèm ciphertext; khóa bảng token và import/export theo actor/request. [google_office.py](../../he-dieu-hanh/google_office.py), dòng 80–92, 205–246. | Một kết nối Google theo người hiện có chưa thể coi là kết nối được phép dùng cho mọi doanh nghiệp người đó tham gia. Chuyển khóa lưu cần xử lý cả dữ liệu mã hóa kèm actor, không chỉ đổi tên khóa SQL. |
| MCP / agent | Bearer token tra agent hoạt động, khác cookie web. [kho.py](../../he-dieu-hanh/kho.py), `tao_agent`, `tu_token`; [may_chu.py](../../he-dieu-hanh/may_chu.py), `actor`. Nhân nhận id/name/role; đầu nối chọn bằng platform_id và role. [dieu_phoi.py](../../he-dieu-hanh/dieu_phoi.py), dòng 65–85, 980–1004. | Token và vai hiện tại không chứng minh quyền tại một đơn vị cụ thể. Quyền gọi tên công cụ không thay quyền đọc đúng hàng dữ liệu. |
| Cấu hình riêng | Đầu nối lưu chung tại `connections-private.json`, hợp nhất theo platform_id và chỉ `quan-tri` sửa; mô hình dùng `model-private.json`. [cau_hinh_ket_noi.py](../../he-dieu-hanh/cau_hinh_ket_noi.py), dòng 29–44, 66–69; [cau_hinh_mo_hinh.py](../../he-dieu-hanh/cau_hinh_mo_hinh.py), dòng 11–13, 50–68. | Không được cho chủ quản đơn vị sửa cấu hình toàn hệ thống hoặc dùng khóa của đơn vị khác qua cùng platform_id. |

Schema yêu cầu kinh doanh, hộp thư và nhật ký hiện cũng dùng owner/sender/
recipient/actor toàn cổng, không có đơn vị trong khai báo tại
[kho.py](../../he-dieu-hanh/kho.py), dòng 32–35. Vì vậy chỉ thêm bộ chọn đơn vị
trên UI hoặc lọc danh sách project sẽ không tạo cách ly dữ liệu.

## Seam đề xuất: quyền trong không gian đơn vị

Đặt một Module quản lý phạm vi dữ liệu ở seam giữa danh tính đã xác thực và
các truy vấn nghiệp vụ, tiếp nối điểm kiểm cùng giao dịch đang có trong
`DuAn.authorize`. Interface cần cho phép: xác lập ngữ cảnh đơn vị từ danh
tính và membership còn hiệu lực; tìm tài nguyên được phép đọc/ghi trong
ngữ cảnh đó; cấp/thu hồi chia sẻ rõ ràng bởi người có quyền. Không trả một
boolean để mọi caller tự ghép lại luật truy vấn.

Ngữ cảnh đã kiểm gồm identity, unit_id, vai tại đơn vị và nguồn ủy quyền;
caller không tự tạo từ `unit_id` trong JSON/header. Chọn đơn vị trên UI chỉ
là đề nghị; máy chủ kiểm membership ở mỗi request và trước commit quan trọng.
ID tài nguyên hợp lệ nhưng thuộc đơn vị khác phải nhận kết quả không tồn tại
trong phạm vi quyền; list/search/count/export không lộ metadata của nó.

Mô hình tối thiểu đề xuất:

- `don_vi` và `don_vi_members(unit_id,identity,role,state)`; một người có thể
  tham gia nhiều đơn vị, vai có hiệu lực riêng tại từng nơi.
- Mỗi tài nguyên nghiệp vụ có đơn vị nguồn bất biến. Owner vẫn chỉ người
  tạo/chịu trách nhiệm, không thay cho đơn vị sở hữu. File/version/upload phải
  thuộc đúng project và đơn vị; task/schedule/run/artifact giữ đơn vị lúc tạo.
- Grant chia sẻ ghi tài nguyên hoặc project, đơn vị nguồn, người/đơn vị đích,
  quyền viewer/editor, bên cấp và trạng thái. Khởi đầu với cấp đích danh;
  không mặc định mọi thành viên được đọc mọi dữ liệu của đơn vị. Chia sẻ cả
  đơn vị là quyền riêng phải được chọn rõ.
- Chia sẻ xuyên đơn vị là đường riêng kiểm grant; người nhận không được
  giả thành thành viên đơn vị nguồn, không tự chia sẻ tiếp hoặc quản trị nguồn.
  Thu hồi chặn lần truy cập/ghi mới, không hứa xóa bản sao đã tải hay ngữ cảnh
  đã gửi nhà cung cấp AI. Tác vụ đã chụp dữ liệu cần giữ provenance của nguồn.
- Tách chủ quản hệ thống khỏi chủ quản đơn vị. Chủ quản hệ thống quản lý vận
  hành, tạo đơn vị và vòng đời tài khoản; quyền này không mặc nhiên đọc dữ
  liệu nghiệp vụ mọi đơn vị. Truy cập hỗ trợ đặc biệt nếu cần phải cấp rõ,
  có thời hạn và nhật ký. Chủ quản đơn vị quản lý membership và chia sẻ trong
  phạm vi được cấp, không quản trị máy chủ hoặc khóa toàn cổng.

Mặc định từ chối khi thiếu đơn vị, membership bị thu hồi, resource không có
đơn vị rõ hoặc không có grant phù hợp. Không giữ nhánh `role == quan-tri`
bypass dữ liệu rồi đổi tên vai trên UI. Không mở rộng Interface nhân bằng
tenant do khách tự khai: context phải được xác lập trước khi định tuyến;
mọi truy vấn nghiệp vụ vẫn phải kiểm phạm vi tài nguyên.

## Pha triển khai và điều kiện chuyển tiếp

1. **Lập bản đồ và migration có thể quay lại.** Trên bản sao thử nghiệm,
   kiểm schema/tham chiếu/blob/JSON và thống kê chỉ số lượng, không in nội
   dung riêng. Tạo một đơn vị legacy chứa dữ liệu cũ chưa phân loại; ghi ánh
   xạ tường minh để chủ quản phân bổ về đơn vị đúng sau này. Không suy doanh
   nghiệp từ email, tên tài khoản hoặc role. Giữ ID, bytes tệp, version,
   lịch sử và owner; không sao chép khóa Google/MCP/model cũ sang mọi đơn vị.
   Khóa cũ chưa được phân quyền dùng theo đơn vị thì chưa cho đơn vị mới dùng.
2. **Đi hết một lát cắt project → document/Office.** Thêm unit và membership,
   kiểm scoped query tại Module, bảo toàn quyền riêng/chia sẻ cũ bên trong
   legacy theo ánh xạ đã duyệt. Dữ liệu mồ côi hoặc liên kết không xác định
   đưa vào diện đối soát hạn chế truy cập, không tự xóa và không để rơi sang
   đơn vị mặc định. Migrate grants cũ nguyên quyền được duyệt; không tự biến
   viewer/editor thành membership doanh nghiệp. Chưa bật nhiều doanh nghiệp
   trên production khi còn đường đọc/ghi không kiểm unit.
3. **Tác vụ và thực thi nền.** Gắn đơn vị vào task JSON lẫn cột truy vấn,
   schedule, model budget, actions, mailbox/delegation, browser/runtime và
   output. Worker phục hồi context từ phạm vi đã lưu, kiểm lại quyền hiện tại;
   không chạy bằng vai toàn cổng của owner. Thu hồi membership phải chặn
   lượt/công cụ tiếp theo; chính sách với lời gọi đã chạy được ghi rõ. Chặn
   nối task/project/document khác đơn vị trừ đường import/chia sẻ được cấp.
4. **Ủy quyền ngoài cổng.** Agent/MCP credentials bị giới hạn đơn vị và tập
   công cụ; đầu nối có khóa `(unit_id,platform_id)`, không rơi về cấu hình của
   đơn vị khác. Google consent/vault/import/export và Office participant
   grants mang phạm vi đã cấp; không đổi phạm vi của callback theo đơn vị
   đang chọn trên UI. Khóa model dùng riêng hay pooled phải có chính sách
   chi phí và quyền riêng trước khi cho doanh nghiệp dùng.
5. **Mở chia sẻ và nghiệm thu tổng thể.** Thêm đường cấp/thu hồi grant cùng
   audit nguồn/đích, kiểm cache/search/export/backup/restore và dữ liệu hỗ trợ.
   Mở nhiều doanh nghiệp sau khi các đường đang bật đạt kiểm tra cách ly.
   Tắt tính năng chưa chuyển đổi thay vì cho fallback toàn cổng.

Mỗi pha cần backup, migration idempotent và manifest đối soát tham chiếu/số
lượng/hash nội dung trên dữ liệu giả. Quay lại mã cũ sau khi đã có dữ liệu
nhiều đơn vị có thể bỏ mất các chốt cách ly: bản quay lại phải hiểu unit,
hoặc khôi phục toàn bộ snapshot trước cutover trong cửa sổ ghi đã dừng.
Không cho bản mã cũ chạy ghi song song vào schema đã chuyển.

## Kiểm thử chặn phát hành

- Hai đơn vị A/B, cùng một người có vai khác nhau: đọc/ghi/list/count/search/
  download/export và ID đoán trước không vượt phạm vi; không có membership
  hoặc context phải bị từ chối. Cùng owner ở A/B không làm lẫn dữ liệu.
- Chủ quản đơn vị A không thấy B; chủ quản hệ thống không có quyền nội dung
  tự động. Thử sửa unit_id/role trong JSON, cookie/header và tool arguments.
- Viewer/editor cấp rõ dùng được đúng tài nguyên; không tự cấp tiếp; thu hồi
  trong lúc chờ SQLite, upload hoặc callback phải chặn commit trái quyền.
  Những người vẫn được cấp không bị khóa coedit do thu hồi người khác.
- Lịch, AI tools, browser, MCP agent và callback vẫn giữ đúng đơn vị khi người
  dùng đổi tab/đơn vị hoặc đăng xuất. Token A không dùng được connector B;
  grant chia sẻ không tiết lộ thông tin kết nối hay khóa nguồn.
- Migration fixture có user nhiều vai, project chia sẻ, task chụp ngữ cảnh,
  file nhiều version và orphan: giữ nguyên dữ liệu, chạy lại không nhân bản,
  không mở rộng grant; restart/restore/rollback giữ đúng luật từ chối.

Các pha và bài kiểm trên chưa được thực hiện bởi ghi chú này. Ghi chú vòng
đời capability bổ sung tại [V29-PHIEN-VA-UY-QUYEN.md](V29-PHIEN-VA-UY-QUYEN.md).
