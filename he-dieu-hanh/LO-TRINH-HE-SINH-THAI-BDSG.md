# Lộ trình hệ sinh thái BDSG OS

Ngày lập đề xuất: **17/11/2026**. Phạm vi: thực thể Thanh Hoá.
Các mốc và chỉ tiêu dưới đây là **đề xuất chưa nghiệm thu**, không phải cam
kết đã phát hành hoặc số đo vận hành. Thứ tự phiên bản thể hiện quan hệ phụ
thuộc; chưa ấn định ngày hoàn thành khi chưa biết năng lực đội ngũ và ngân sách.

## Mục tiêu để chủ quản duyệt

Xây BDSG OS thành không gian làm việc thống nhất bằng tiếng Việt, nơi người
dùng Thanh Hoá mở ứng dụng, giao việc cho AI, làm tài liệu và sử dụng dữ liệu
đúng quyền trên nhiều thiết bị. Bắt đầu từ máy chủ vật lý Thanh Hoá, hoàn
thiện phần mềm và vận hành trước, rồi từng bước mở nền tảng ứng dụng và thiết
bị BDSG. Học sự liền mạch của một hệ sinh thái như Apple, phát triển bản sắc
và hợp đồng mở riêng của BDSG; mỗi phiên bản phải tạo được giá trị sử dụng
và có bằng chứng nghiệm thu.

Thành công được đánh giá bằng công việc hoàn thành, dữ liệu được bảo vệ,
khả năng khôi phục và mức sử dụng thật. Số dòng mã, số icon, độ giống iOS
hoặc danh sách khả năng trên giấy không phải cổng nghiệm thu. Thanh Hoá là
nơi ưu tiên kiểm chứng; lộ trình này không mở rộng thành hệ thống 34 tỉnh.

## Điểm xuất phát và bằng chứng

Nguồn hiện trạng là [V26](V26-HOAN-THIEN-VAN-HANH.md),
[hợp đồng thực thi](THUC-THI-VA-MO-DUN.md), [README](README.md) và
[nghiên cứu iOS/WebOS](NGHIEN-CUU-IOS-WEBOS.md). V26 ghi bằng chứng kiểm
cục bộ cho tác vụ, Office và điều khiển đồng bộ; đồng thời ghi rõ các đầu
nối còn thiếu hợp đồng/quyền và sao lưu ngoài máy còn phải hoàn thiện.
Không suy từ bài kiểm tổng hợp thành nghiệp vụ production đã chạy thật.

V27 đang được phát triển: shell nhiều ứng dụng, phiên giao diện, tìm kiếm
danh mục và vùng trình duyệt. Chi tiết trình duyệt được ghi riêng tại
[V27 — trình duyệt](V27-TRINH-DUYET.md). Trạng thái hoàn tất của toàn bộ
V27 phải dựa vào biên bản ghép và nghiệm thu, không dựa vào lộ trình này.

Máy chủ vật lý Thanh Hoá là điểm xuất phát do chủ quản xác định. **TH01**
là mã nút đề xuất để quản lý, chưa phải kết quả phát hiện thiết bị hoặc
chứng nhận máy đã được cài BDSG OS. CPU, GPU, RAM, đĩa, mạng, nguồn dự phòng,
phiên bản Ubuntu, tải thực tế và sức chứa đều **chưa đo trong tài liệu này**.
Không chọn cấu hình AI hoặc mua phần cứng từ thông số phỏng đoán.

## Các lớp của BDSG OS

| Lớp | Trách nhiệm và hợp đồng cần giữ |
|---|---|
| Máy chủ vật lý và Ubuntu host | Linux kernel, driver, filesystem, mạng, quản lý tiến trình và cập nhật host do Ubuntu đảm nhiệm. BDSG không nhận đây là nhân phần cứng tự viết. Vòng đời host có kế hoạch bảo trì riêng. |
| Nhân nghiệp vụ BDSG và control plane | `nhan/` kiểm danh tính, quyền, hạn mức, nhật ký; `he-dieu-hanh/` giữ tác vụ, dữ liệu, điều phối và trạng thái. Mọi công cụ nghiệp vụ tiếp tục qua nhân. Tài khoản chủ quản web khác tài khoản quản trị host. |
| Nền tảng ứng dụng | Registry, lifecycle, phiên, liên kết sâu, tìm kiếm có quyền, tệp và thông báo. API cho ứng dụng, MCP cho công cụ và SDK hỗ trợ tích hợp dùng cùng chính sách quyền; không tạo đường vòng kiểm soát. |
| Trải nghiệm nhiều thiết bị | Web trước; sau đó PWA và các ứng dụng native khi có nhu cầu kiểm chứng. Trình duyệt thiết bị vẫn cung cấp engine web. Khôi phục ngữ cảnh không đồng nghĩa di chuyển một tiến trình hệ điều hành. |
| Cổng thiết bị và firmware về sau | Cổng nhận dạng, đăng ký/thu hồi, telemetry, lệnh được cho phép và cập nhật thiết bị. Firmware thuộc từng loại thiết bị, cần quyền từ nhà sản xuất và phép thử riêng; chưa có trong V27. |

Thiết kế mô-đun theo nguyên tắc của kỹ năng `codebase-design`: hợp đồng nhỏ,
che phần xử lý phức tạp, kiểm qua cùng giao diện mà bên gọi sử dụng. Mỗi
hợp đồng cần nêu danh tính, dữ liệu vào/ra, lỗi, hạn mức, thứ tự thao tác,
idempotency và tương thích phiên bản. Không thêm lớp trung gian chỉ để tăng
quy mô mã. Chỉ tách adapter khi có khác biệt thực tế cần thay thế hoặc kiểm.

## Máy chủ đầu tiên: kế hoạch TH01

Đầu tiên lập hồ sơ tài sản **riêng ngoài Git/web**: người chịu trách nhiệm,
cấu hình đã đo, tình trạng đĩa, dung lượng, nguồn/mạng, bảo hành và khả năng
khôi phục. Kho công khai chỉ giữ schema và bằng chứng đã khử thông tin riêng.
Kiểm kê qua quy trình được chủ quản cho phép, không tự truy cập host từ tài
liệu này. Ubuntu tiếp tục là lớp vận hành host; ứng dụng BDSG chạy bằng tài
khoản dịch vụ ít quyền, giới hạn tài nguyên và đường ghi rõ ràng.

Thứ tự đưa TH01 vào vận hành: kiểm kê → đường sao lưu ngoài máy → thử restore
ở môi trường tách biệt → dựng staging → đo tải → canary → nghiệm thu production.
Tách kho bí mật, dữ liệu tác vụ/tệp, log và bản phát hành; mọi đường truy cập
đều có chủ thể và dấu vết. Máy đơn vẫn có điểm lỗi đơn; chỉ xem xét nút dự
phòng sau khi đo chi phí gián đoạn và diễn tập khôi phục.

Ứng dụng **Máy chủ** trong BDSG về sau chỉ hiển thị cho quản trị viên các
chỉ số đọc đã cho phép: tải, đĩa, trạng thái dịch vụ, tuổi bản sao lưu và
phiên bản bản phát hành. Collector phải lọc dữ liệu trước khi trả API,
không trả biến môi trường, đường dẫn riêng hay nội dung log nhạy cảm.
Không cung cấp root shell/terminal thực thi lệnh từ web. Thao tác quản trị
host tiếp tục qua kênh vận hành riêng; muốn bổ sung thao tác ghi phải có
thiết kế quyền, danh sách lệnh hữu hạn và cổng nghiệm thu mới.

## Các phiên bản đề xuất

Mỗi phiên bản phải công bố: phạm vi đã giao, phần còn thiếu, chủ sở hữu,
ngày và môi trường kiểm, dữ liệu thử, kết quả quyền cho phép/từ chối, đường
rollback và trở ngại ngoài dự án. Không gắn nhãn hoàn tất cho cả phiên bản
chỉ vì một giao diện hoặc adapter đã có mã.

| Mốc | Sản phẩm bàn giao | Cổng nghiệm thu | Phụ thuộc và trở ngại |
|---|---|---|---|
| **V27 — không gian ứng dụng** | Home, registry thống nhất, mở/chuyển/đóng app, ngữ cảnh từng phiên; tìm danh mục; trình duyệt quản lý địa chỉ/tab và mở website ngoài; cài đặt tiếp cận. | Mở nhiều app nội bộ rồi quay lại đúng ngữ cảnh; refresh/đăng xuất không lộ người trước; URL sai bị chặn; liên kết ngoài có nhãn đúng; kiểm desktop/điện thoại, bàn phím và công nghệ hỗ trợ. Không tuyên bố có engine trình duyệt mới, chỉ mục web hay SSO. | Nền V26; schema phiên và hợp đồng điều hướng. Thiết bị iOS/Android thật cần kiểm riêng. Nhúng đối tác chỉ mở sau kiểm CSP/cookie/quyền. |
| **V28 — TH01 và khôi phục được** | Hồ sơ triển khai, staging, telemetry quản trị chỉ đọc, cảnh báo, sao lưu ngoài máy, runbook sự cố, quản lý bản phát hành và diễn tập restore. | Khôi phục tác vụ/tệp/quyền trên môi trường sạch; kiểm checksum và quyền sau restore; rollback bản lỗi không xoá dữ liệu; đo RPO/RTO thật; diễn tập mất dịch vụ và thông báo sự cố. | Cần kiểm kê TH01 được phép, nơi sao lưu, tài khoản vận hành, ngân sách/lịch bảo trì. Mất máy đơn chưa thể hứa không gián đoạn. |
| **V29 — danh tính và dữ liệu tổ chức** | Mô hình tenant/tổ chức, thành viên/vai trò, thu hồi phiên/thiết bị, MFA cho chủ quản nếu đáp ứng điều kiện; schema lưu dữ liệu có phạm vi tenant; quy trình xuất/xoá/lưu giữ. | Test truy cập chéo tenant qua API, tệp, tìm kiếm, tác vụ và backup đều bị từ chối; migration từ dữ liệu cũ có đối soát; quyền bị thu hồi có hiệu lực với lần gọi sau; xuất dữ liệu đọc lại được. | Chốt mô hình tổ chức Thanh Hoá và chủ sở hữu dữ liệu; chọn cơ chế MFA/khôi phục tài khoản; thiết kế migration. Không gọi quyền theo người hiện có là cách ly tenant hoàn chỉnh. |
| **V30 — nền tảng app API/MCP/SDK** | App manifest có phiên bản, hợp đồng quyền, API được tài liệu hoá, SDK mẫu, môi trường phát triển bằng dữ liệu tổng hợp, quy trình đăng ký/ngừng app và kiểm tương thích. | App mẫu đọc được dữ liệu đã cấp, bị chặn dữ liệu ngoài phạm vi; thu hồi token/app chặn công cụ; hạn mức/audit dùng chung nhân; kiểm nâng/hạ phiên bản và thông báo thay đổi phá vỡ tương thích. | V29; chọn hợp đồng dựa trên app nội bộ và một tích hợp được phép. Cần endpoint/chứng thư, người phụ trách và hợp đồng dữ liệu của đối tác. Registry không tự biến thành chợ ứng dụng đã có nhà phát triển. |
| **V31 — công việc liên ứng dụng tin cậy** | Quy trình nghiệp vụ ưu tiên do người dùng Thanh Hoá chọn; checkpoint, chống lặp thao tác, đối soát kết quả chưa rõ, thông báo, dữ liệu xuất có nguồn gốc. Mỗi đầu nối có hồ sơ nghiệm thu riêng. | Hoàn thành quy trình bằng tài khoản thử thật được phép; thử timeout, retry, thu hồi quyền và dừng giữa chừng; thao tác ghi có phê duyệt tương ứng và không lặp; kết quả không chắc phải chờ đối soát. | V28–V30; cần sandbox/hợp đồng/quyền từng nền tảng. OAuth, webhook, nghiệp vụ ghi và đối soát là công việc phát triển riêng, không chỉ nhập khoá. |
| **V32 — liền mạch nhiều thiết bị** | PWA, cache shell được liệt kê, liên kết sâu có quyền, bản nháp phía máy chủ, thông báo theo lựa chọn; chính sách xung đột và xuất dữ liệu. | Chuyển thiết bị khôi phục đúng bản nháp; offline báo đúng phạm vi; reconnect không ghi đè âm thầm hoặc lặp lệnh; đăng xuất/thu hồi xoá dữ liệu cache riêng; kiểm screen reader và thiết bị thật. | V29–V31; HTTPS và khả năng trình duyệt/OS mục tiêu. Cần ma trận thiết bị hỗ trợ và ngân sách QA; push/chạy nền tuỳ nền tảng, không hứa luôn chạy. |
| **V33 — cổng thiết bị thử nghiệm** | Chọn một loại thiết bị có nhu cầu thật, giao thức kết nối, danh tính từng thiết bị, gateway cách ly, telemetry, allowlist lệnh; nguyên mẫu firmware chỉ khi có quyền và công cụ phù hợp. | Ghép/thu hồi thiết bị, chống phát lại và lệnh trái quyền; mất mạng có trạng thái an toàn; cập nhật có xác minh, phát hiện lỗi và phục hồi; không nối trực tiếp thiết bị vào dữ liệu tenant. | V28–V32; chọn phần cứng có hỗ trợ, tài liệu/SDK và quyền firmware. Cần bàn thử, người phụ trách an toàn và yêu cầu sử dụng thực tế. Chưa gọi nguyên mẫu là phần cứng BDSG thương mại. |
| **V34 — hệ sinh thái có thể vận hành lâu dài** | Chu kỳ hỗ trợ/LTS, chính sách cập nhật và kết thúc hỗ trợ, chứng nhận app/thiết bị theo phép thử, kênh phát hành, hỗ trợ người dùng và kế hoạch kinh doanh phần cứng có dự toán. | Tổ chức Thanh Hoá sử dụng ổn định trong đợt pilot đã định; đạt chỉ tiêu được chốt bằng phép đo; diễn tập restore/thu hồi/cập nhật lỗi; hồ sơ tương thích, hỗ trợ, chi phí và xuất dữ liệu đầy đủ. | Tất cả cổng trước; ngân sách và đội vận hành. Thiết kế công nghiệp, sản xuất, chuỗi cung ứng, chứng nhận và bảo hành cần chương trình riêng; chỉ quyết định sau pilot và dự toán, chưa được tuyên bố đã có. |

Các hạng mục độc lập có thể nghiên cứu sớm, nhưng không vượt cổng an toàn
hoặc công bố chức năng chưa đạt. Ưu tiên nguồn lực theo thứ tự: V27 dùng
được → V28 giữ được dữ liệu → V29 đúng quyền → V30–V31 có nghiệp vụ thật →
V32 nhiều thiết bị → V33–V34 thiết bị và hệ sinh thái.

## Cổng chung cho mọi bản phát hành

- **Danh tính và dữ liệu:** máy chủ xác thực lại chủ thể và quyền từng lần
  gọi; scope gắn tenant/chủ sở hữu, không tin ID từ client. Kiểm cả truy cập
  được phép và bị từ chối. Dữ liệu khách hàng, bí mật và bản sao lưu không
  vào Git, web tĩnh, log, cache trình duyệt hay gói SDK mẫu.
- **Cập nhật và rollback:** mã nguồn gốc rõ, phụ thuộc được kiểm và inventory
  được lưu; tách cập nhật Ubuntu, BDSG app và firmware. Có staging, backup
  trước migration, canary, health gate và release trước. Migration mất dữ
  liệu hoặc không đảo ngược phải có kế hoạch restore/đối soát riêng; đổi
  symlink không tự đảo ngược schema. Không tự động quay lại bản có lỗ hổng
  đã biết; nếu chưa có bản an toàn thì cô lập chức năng và xử lý sự cố.
- **Bí mật và kết nối:** dùng chứng thư theo chủ thể, phạm vi nhỏ, có thời
  hạn/thu hồi; xoay khoá và kiểm không lộ qua kết quả công cụ. Không dùng
  phiên ChatGPT/Codex thay API key, không coi website link là SSO/MCP.
- **AI và hành động:** phân biệt quy trình kịch bản với mô hình API thật;
  không giả kết quả, không âm thầm đổi provider. Ghi nguồn/usage phù hợp,
  có ngân sách và cơ chế dừng; kết quả bên ngoài không được mở rộng quyền.
- **Tiếp cận:** tên nút/nhãn rõ, focus thấy được, thao tác bằng bàn phím,
  screen reader, phóng to chữ, giảm chuyển động và giao diện điện thoại.
  Mọi thao tác gesture chính có nút thay thế; trạng thái lỗi có đường sửa.
- **Quyền rời hệ thống:** xuất dữ liệu nghiệp vụ bằng định dạng phổ biến
  có manifest, schema và tệp liên quan theo quyền; đọc lại được ở môi trường
  độc lập. Có quy trình lưu giữ/xoá và xử lý bản sao lưu; không xoá lịch sử
  bắt buộc chỉ vì đóng app hoặc ngừng sử dụng thiết bị.

## Chỉ tiêu hướng tới — đề xuất, chưa đo

Các ngưỡng sau được đề xuất ngày **17/11/2026** để chủ quản xem xét trong
pilot Thanh Hoá. Cần chốt bộ quy trình, tập người dùng, cấu hình đo, ngân
sách và thời gian quan sát trước khi dùng làm điều kiện phát hành. Không
ghi các ngưỡng này thành số liệu hiện tại trên giao diện.

| Chỉ tiêu đề xuất | Cách đo và cổng áp dụng |
|---|---|
| Người dùng pilot hoàn thành tối thiểu **80%** quy trình trọng tâm đã chọn mà không phải nhờ đội phát triển thao tác hộ | Quan sát tác vụ với sự đồng ý, ghi mẫu số và lý do không hoàn tất; mục tiêu V31/V34. Chưa có baseline. |
| Tối thiểu **60%** người dùng đã kích hoạt quay lại dùng hằng tuần trong **4 tuần** pilot liên tiếp | Đếm hoạt động nghiệp vụ có ý nghĩa theo danh tính tổng hợp; loại phiên test, mở trang đơn thuần và bot. Mục tiêu V34; chưa đo. |
| Sẵn sàng **99,5%** trong cửa sổ **30 ngày** pilot | Probe từ ngoài host cho đăng nhập/API cốt lõi, định nghĩa rõ cửa sổ bảo trì và cách công bố; không lấy uptime tiến trình thay thành công nghiệp vụ. Mục tiêu V28/V34; chưa đo. |
| RPO không quá **24 giờ**, RTO không quá **4 giờ** cho phạm vi dữ liệu đã chốt | Diễn tập mất host, khôi phục từ nơi sao lưu ngoài máy, tính cả bí mật/quyền và kiểm dữ liệu; V28. Chưa đo, phải điều chỉnh theo nhu cầu nghiệp vụ trước production. |
| p95 mở/chuyển app nội bộ đã tải không quá **1 giây** trên cấu hình pilot được công bố | Đo client trên desktop/điện thoại và điều kiện mạng ghi rõ; thời gian provider AI tách riêng. Mục tiêu V27/V32; chưa đo. |
| Không chấp nhận lỗi truy cập chéo tenant hoặc lộ bí mật trong bộ kiểm phát hành | Đây là tiêu chí chặn V29 trở đi, không phải cam kết không bao giờ có sự cố. Công bố phạm vi kiểm, ngày kiểm và khắc phục trước phát hành. |

## Liên thông và phần cứng về lâu dài

API có phiên bản, MCP với quyền cụ thể, OAuth khi được hỗ trợ, định dạng
tệp phổ biến và xuất dữ liệu là cách giữ hệ sinh thái mở. Không khoá người
dùng vào thiết bị BDSG để đọc dữ liệu của họ. SDK chỉ hỗ trợ hợp đồng đã có;
không phát token quản trị cho app. Mỗi app/thiết bị có danh sách khả năng
đã kiểm, phiên bản tương thích và thời hạn hỗ trợ riêng.

Nghiên cứu Apple dùng để học cách tổ chức trải nghiệm và vòng đời. Không
sao chép tài sản nhận diện, icon, phông có hạn chế, mã nguồn độc quyền hoặc
tự nhận là bản iOS/Safari. Không hứa chạy ứng dụng iOS hoặc thay kernel
Ubuntu bằng BDSG chỉ vì giao diện có Home và app switcher.

Sau V34, quyết định sản phẩm phần cứng chỉ được mở khi có nhu cầu sử dụng
đã đo, cấu hình tham chiếu kiểm được, dự toán sở hữu/vận hành, nhà cung cấp,
ngân sách thử nghiệm và kế hoạch hỗ trợ. Có thể bắt đầu bằng thiết bị phổ
thông đã được kiểm tương thích; đó chưa phải thiết kế hay sản xuất phần
cứng BDSG. Bo mạch, firmware độc quyền, thiết kế công nghiệp và sản xuất
đại trà là chương trình khác với việc phát triển webOS.

## Việc tiếp theo có thể thực hiện ngay

Hoàn tất V27 và công bố bằng chứng trong phạm vi shell/app/browser. Chuẩn
bị ticket V28 theo quy trình `.scratch/thanhhoa/`: mẫu kiểm kê TH01 không
chứa dữ liệu thật, đặc tả telemetry chỉ đọc, kế hoạch backup ngoài máy và
kịch bản restore. Chốt các quy trình kinh doanh ưu tiên với người dùng
Thanh Hoá để đo baseline trước khi tăng số ứng dụng hoặc mua thiết bị.

Tài liệu này không cấp quyền truy cập máy chủ, không thay đổi cấu hình,
không triển khai production và không đặt mua phần cứng. Các công việc ấy
cần phạm vi vận hành và dữ liệu kiểm chứng cụ thể khi thực hiện.
