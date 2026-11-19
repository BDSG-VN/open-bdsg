# V29 — Cấu hình AI theo đơn vị và LiteLLM

Ngày đối chiếu: **17/11/2026**. Phạm vi: đọc source trong kho và tài liệu/mã
nguồn chính chủ LiteLLM; không đọc cấu hình riêng, gọi nhà cung cấp tính phí,
thay dịch vụ hay triển khai production. Đây là nghiên cứu và đề xuất; không
phải chứng nhận cách ly đơn vị đã hoàn thành. Source của các nhánh công việc
có thể tiếp tục thay đổi; tìm theo tên lớp/hàm thay vì số dòng.

## Kết luận chọn hướng

Giữ LiteLLM làm bộ chuyển giao thức loopback, còn BDSG kiểm quyền đơn vị,
danh mục được phép và ngân sách trước mỗi lần gửi. Không gọi `gateway_key`
hiện tại là khóa đơn vị: nó đang được đặt vào `master_key` dùng chung.
Alias riêng theo đơn vị/revision giúp định tuyến và phát hiện cấu hình cũ,
nhưng không tự tạo kiểm soát quyền tại proxy. Đây là kết luận từ
[`TrungTamAI.proxy_config/run`](../../he-dieu-hanh/trung_tam_ai.py) và
[launcher hiện tại](../../trien-khai/litellm/chay_litellm.py).

Nếu cần proxy tự chặn khóa của đơn vị này gọi mô hình đơn vị khác, cần một
phương án khác có kiểm chứng: Postgres + virtual key giới hạn model/team,
hoặc tiến trình proxy/chứng thư riêng. Chưa có cơ sở tuyên bố có lớp cách ly
đó trong cách chạy không DB hiện tại. Điều kiện Postgres đến từ
[Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys#setup) và
[Team Budgets](https://docs.litellm.ai/docs/proxy/team_budgets).

## Mã hiện tại trong Open BDSG

| Quan sát trong source ngày 17/11/2026 | Ý nghĩa đối với đơn vị |
|---|---|
| `TrungTamAI` đọc/ghi một `ai-models-private.json` và sinh một `litellm-config.json`; `catalogue()` không nhận phạm vi đơn vị. [`trung_tam_ai.py`](../../he-dieu-hanh/trung_tam_ai.py) | Không coi danh mục toàn cổng là danh mục đơn vị; không sao chép khóa cũ sang các đơn vị mới. |
| `_admin` kiểm vai `quan-tri` toàn cổng; `save` chưa kiểm membership hoặc quyền quản lý cấu hình tại đơn vị. [Cùng source](../../he-dieu-hanh/trung_tam_ai.py) | Cần tách quyền quản trị đơn vị khỏi chủ quản hệ thống theo [`GLOSSARY.md`](../../GLOSSARY.md). |
| `proxy_config` sinh alias `id-revision`, giữ `gateway_key` làm `general_settings.master_key`, tắt retries/fallbacks và không khai DB. [Cùng source](../../he-dieu-hanh/trung_tam_ai.py) | Một khóa có thể định tuyến mọi alias trong config; tên alias không phải chứng thư quyền. |
| `assert_ready` gọi `/v1/models` và kiểm tập alias mong đợi là tập con kết quả; không gọi mô hình upstream. [Cùng source](../../he-dieu-hanh/trung_tam_ai.py) | Chứng minh proxy đã công bố alias, chưa chứng minh khóa upstream hợp lệ, model hỗ trợ tools hay không bị vượt quyền đơn vị. |
| `run` chụp cấu hình, tạo adapter cục bộ; callback `model-reserve` giữ ngân sách trước `_request`. [`trung_tam_ai.py`](../../he-dieu-hanh/trung_tam_ai.py), [`MoHinhBDSG.run`](../../he-dieu-hanh/mo_hinh_bdsg.py) | Có điểm gắn kiểm tra ngay trước mỗi lần gửi; snapshot không đủ để phát hiện thu hồi sau khi tác vụ bắt đầu. |
| `CongViec.create/followup` còn dùng `self.model`; nhánh `units` hiện từ chối AI toàn cổng chưa có cấu hình riêng. [`cong_viec.py`](../../he-dieu-hanh/cong_viec.py) | Giữ từ chối này cho tới khi đi hết đường cấu hình, admission, worker và provider theo phạm vi. Không đổi `self.model` tạm thời theo request. |
| Docker publish chỉ `127.0.0.1:4000`, bind mount một tệp config chỉ đọc; không nhận đường dẫn cấu hình từ người dùng. [`chay_litellm.py`](../../trien-khai/litellm/chay_litellm.py) | Backend là ranh giới tin cậy; loopback không cách ly các tiến trình cùng máy và không thay quyền đơn vị. |
| File watcher dùng `PathChanged`; reload service thực hiện `systemctl restart`, không gọi API cập nhật model. [`bdsg-litellm.path`](../../trien-khai/litellm/bdsg-litellm.path), [`bdsg-litellm-reload.service`](../../trien-khai/litellm/bdsg-litellm-reload.service) | Lưu cấu hình khác với proxy đã nạp; cần trạng thái chờ nạp và báo lỗi rõ. Restart có thể gián đoạn lời gọi đang chạy. |

Kho có image ghim digest trong launcher và mô tả nguồn khóa tại
[`trien-khai/litellm/README.md`](../../trien-khai/litellm/README.md).
Không suy phiên bản từ `main` upstream và không đề xuất thay image trong
nghiên cứu này. Tài liệu online dưới đây phản ánh thời điểm đọc, không bảo
đảm mọi tùy chọn có trong image đã ghim.

## Khả năng LiteLLM được nguồn chính chủ xác nhận

1. **OSS có virtual keys, ngân sách và rate limits cơ bản.** Trang phân tầng
   [Enterprise](https://docs.litellm.ai/docs/enterprise) đặt các mục này trong
   lớp AI Gateway mã nguồn mở; SSO/SCIM, audit logs và vai quản trị phân cấp
   nằm trong lớp Enterprise. Không đồng nhất “self-host” với “mọi tính năng
   đều miễn phí”. [LICENSE](https://github.com/BerriAI/litellm/blob/main/LICENSE)
   phân biệt thư mục enterprise với phần MIT.
2. **Virtual key chuẩn cần Postgres**, `DATABASE_URL` và master key quản trị;
   `/key/generate` nhận danh sách `models`. Nguồn:
   [Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys#setup).
   Mã [`key_management_endpoints.py`](https://github.com/BerriAI/litellm/blob/main/litellm/proxy/management_endpoints/key_management_endpoints.py)
   cũng từ chối sinh khóa khi không có `prisma_client`. Không thể thay
   Postgres bằng SQLite nghiệp vụ của BDSG chỉ bằng đổi chuỗi kết nối.
3. **Ngân sách team chuẩn cần Postgres**; tạo team với `max_budget` và
   `budget_duration`, rồi gắn key vào `team_id`. Nguồn:
   [Team Budgets](https://docs.litellm.ai/docs/proxy/team_budgets).
   Mã quản lý team nằm tại
   [`team_endpoints.py`](https://github.com/BerriAI/litellm/blob/main/litellm/proxy/management_endpoints/team_endpoints.py).
   Chưa cài Postgres thì không tuyên bố quota hiện tại do LiteLLM team giữ.
4. **Danh sách model được phép khác với ngân sách riêng cho mỗi model.**
   Hạn chế model của key/team dùng tên model được cấu hình;
   [LLM Access](https://docs.litellm.ai/docs/proxy/access_management/llm)
   cảnh báo danh sách model rỗng trên key không thêm hạn chế.
   [Budgets, Rate Limits](https://docs.litellm.ai/docs/proxy/users) ghi
   `model_max_budget` của virtual key là Enterprise và ngân sách cần DB;
   cấu hình `max_budget` trên proxy không DB không phải bảo đảm chặn chi phí.
   Không đề xuất dùng tính năng ngân sách theo từng model dưới giả định OSS.
5. **Model từ file cần reload/restart**, còn model lưu DB hỗ trợ thay đổi cho
   yêu cầu mới mà không restart. File và DB có thể cùng nạp model, gây hai
   nguồn định nghĩa nếu quản lý cả hai. Nguồn:
   [Model Management](https://docs.litellm.ai/docs/proxy/model_management).
   Vì launcher của BDSG mount một file cố định, đường an toàn hiện tại là
   sinh lại toàn bộ file đó và để cơ chế restart đã có nạp; không hứa hot
   reload tức thì hay cập nhật riêng một đơn vị bằng API không DB.

## Đề xuất giao diện nhỏ, giữ luật bên trong mô-đun

Phần này là **thiết kế đề xuất cho BDSG**, không phải tính năng đã được
LiteLLM hoặc kho hiện tại cung cấp. Dùng một đầu mối giữ bốn việc gắn liền:
xác lập phạm vi, cấu hình/danh mục, giữ ngân sách và gọi provider có kiểm
quyền. Tên minh họa có thể là `AITheoDonVi` với các thao tác:

- `bind(actor, unit_reference)` trả đối tượng chỉ dùng cho phạm vi đã kiểm;
  tham chiếu từ task/worker phải được đối chiếu membership còn hiệu lực.
  Không tin `unit_id` tự khai từ chat, HTTP JSON hay header.
- `catalogue()` / `status()` chỉ trả metadata của đơn vị; `save()` yêu cầu
  quyền quản lý AI tại đơn vị, giữ khóa riêng, không cho sửa master key,
  endpoint loopback, image hoặc trần tài nguyên máy chủ.
- `admit(db, task, run, selection)` xác thực task/project/đơn vị cùng phạm
  vi, lựa chọn model trong danh mục và giữ suất tác vụ trong giao dịch.
- `run(binding, ...)` sử dụng adapter cục bộ bất biến. Ngay trước từng
  `_request`, kiểm lại đơn vị, quyền nguồn dữ liệu, cấu hình/revision đang
  có hiệu lực, dừng/thu hồi và giữ ngân sách; lỗi thì không gửi mạng.

Không rải `if unit_id` tại mọi caller hoặc đưa một boolean cho caller tự
ghép luật. Worker nhận binding riêng cho lượt chạy; không hoán đổi
`CongViec.self.model` dùng chung giữa các luồng. Actor và ngữ cảnh công cụ
vẫn đi qua nhân; có quyền quản lý khóa không đồng nghĩa quyền đọc mọi dự
án. Đây là cách áp dụng các định nghĩa phạm vi/quản trị trong
[`GLOSSARY.md`](../../GLOSSARY.md), tiếp nối ranh giới đã nêu trong
[`V29-KHONG-GIAN-DON-VI.md`](V29-KHONG-GIAN-DON-VI.md).

## Cấu hình tổng hợp, xoay khóa và giới hạn tải

Đề xuất tiếp tục **một config tổng hợp** cho launcher hiện có. Nguồn cấu
hình đơn vị lưu riêng, sau đó compiler chỉ xuất các model đang bật có
alias chứa mã đơn vị không có dữ liệu nhận dạng + model ID + revision.
Alias phải duy nhất toàn proxy; không có wildcard, fallback, chuyển nhà
cung cấp hoặc chọn model của đơn vị khác khi không tìm thấy. Key master
chỉ backend giữ; không trả qua catalogue/admin HTTP, không gửi vào prompt.
Đây vẫn là cách ly do BDSG thực thi, không phải kiểm quyền độc lập tại proxy.

Mỗi lần đổi danh mục sinh revision mới, ghi file tạm quyền riêng rồi
`fsync`/replace, kiểm toàn bộ config hợp lệ trước publish. Sau restart,
chỉ mở admission khi `/v1/models` có alias mong đợi cho cấu hình mới;
lỗi nạp phải chặn mới và báo trạng thái, không dùng alias revision cũ làm
fallback. Suy luận vận hành từ việc launcher bind mount một file và writer
replace file: cần kiểm trường hợp mount vẫn trỏ tệp cũ sau replace; giữ
restart container hiện có trong quy trình nạp, không chỉ đọc lại đường dẫn
bên trong container. Cơ chế mount tham khảo
[Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/);
chưa chạy phép thử inode/container trong nghiên cứu này.

Xoay/thu hồi khóa upstream phải đổi revision/credential generation; binding
cũ bị từ chối trước lần gửi tiếp theo. Tắt AI hoặc thu hồi membership cũng
chặn lượt tiếp theo; không hứa hủy một yêu cầu đã gửi nhà cung cấp hay xóa
dữ liệu họ đã nhận. Không giữ toàn bộ khóa upstream trong đối tượng worker
cũ rồi tiếp tục dùng sau khi thu hồi. Xoay master key là thao tác vận hành
toàn proxy cần điều phối backend và restart; không giao cho quản trị đơn vị.

Giới hạn cần áp dụng cho cả mỗi đơn vị và toàn máy: số model, tổng model,
kích thước file, số lần thay đổi/restart, hàng đợi và đồng thời. Danh mục
một đơn vị không được khiến compiler bỏ model đơn vị khác. Writer cấu hình
phải tuần tự hóa việc đọc–sửa–tổng hợp; kiểm quyền lại ngay trước commit.
Không tự restart production để kiểm tra trong bài thử.

## Sao lưu và tính nguyên tử là điều kiện đi cùng

Hiện [`sao_luu_he_thong.py`](../../he-dieu-hanh/sao_luu_he_thong.py) chỉ cho
phép tên cố định trong `DATA_FILES`/`ALLOWED`, bao gồm ba tên liên quan AI:
`model-private.json`, `ai-models-private.json`, `litellm-config.json`.
`verify()` bắt buộc cặp ai-settings/proxy cùng tồn tại và so sánh **đúng toàn
bộ** `TrungTamAI.proxy_config(legacy_settings)` với proxy JSON. Vì vậy chỉ
thêm config tổng hợp nhiều đơn vị sẽ làm verify cũ từ chối hoặc bỏ sót nguồn
cấu hình mới; không được nới bỏ kiểm này để “cho sao lưu qua”.

Đề xuất đưa registry đơn vị vào schema/bộ kiểm phiên bản mới, sao lưu nguồn
registry lẫn cấu hình tổng hợp và chứng minh chúng tái sinh đúng nhau. Giữ
khả năng đọc gói legacy có kiểm; không sao chép khóa legacy tự động sang
đơn vị khác. Snapshot phải giữ cùng revision của DB quota, cấu hình đơn vị
và file proxy dưới cùng khóa writer mà mọi writer thật sự tuân theo.

`BEGIN IMMEDIATE` hiện tại khóa SQLite; replace từng file không tạo giao
dịch nguyên tử xuyên DB và nhiều file. Do đó cần trạng thái publish hoặc
generation/manifest rõ, phát hiện crash giữa các lần ghi, giữ bản trước và
chặn gửi cho tới khi đối soát xong. Quay lại phải khôi phục một bộ nhất quán;
không chỉ lùi proxy về khóa/revision cũ trong khi backend đã thu hồi. Thử
backup/verify/restore vào thư mục mới bằng khóa giả trước khi mở AI đơn vị.

## Nghiệm thu đề xuất, không gọi API tính phí

- Hai đơn vị dùng cùng model ID vẫn tạo alias khác; danh mục/status của
  mỗi bên không lộ tên, giá, khóa hay revision riêng bên kia.
- Cùng danh tính tham gia hai đơn vị chạy đồng thời không đổi adapter,
  ngân sách hoặc task context của nhau; đo cả trường hợp được phép/bị từ chối.
- Thu hồi membership, quyền dự án, khóa hoặc cấu hình giữa các lượt chặn
  **lần gửi tiếp theo**; mock provider ghi số lần gọi, không cần khóa thật.
- Cấu hình chưa nạp, alias cũ, config lỗi hoặc restart lỗi đều chặn gửi;
  không có fallback sang model, khóa hay quy trình khác khi AI báo lỗi.
- Lưu đồng thời, vượt trần toàn máy, crash lúc publish, backup khi đổi
  config, gói thiếu/thừa file và restore legacy đều có kết quả rõ, không
  bỏ kiểm tính nhất quán để hoàn tất sao lưu.

Chưa đo hiệu năng, độ trễ reload hoặc kết nối upstream thật trong nghiên
cứu ngày 17/11/2026. Các điều kiện trên cần được chứng minh bằng kiểm thử
và đối chiếu image đã ghim trước khi tuyên bố AI đơn vị sẵn sàng production.
