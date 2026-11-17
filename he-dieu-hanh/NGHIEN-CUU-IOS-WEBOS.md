# Nghiên cứu iOS cho WebOS Thanh Hoá

Ngày tra cứu: 17/11/2026. Phạm vi: tài liệu công khai chính thức của Apple, WebKit, MDN và W3C; đối chiếu với `GLOSSARY.md`, `he-dieu-hanh/README.md`, `THUC-THI-VA-MO-DUN.md` trong kho. Đây là nghiên cứu và đề xuất kiến trúc, không phải chứng nhận mọi tính năng đã triển khai. Chưa đo hiệu năng hoặc thử nghiệm thiết bị iOS thật trong nghiên cứu này.

## Kết luận và giới hạn mục tiêu

Nên học đầy đủ **các lớp trải nghiệm và hợp đồng vận hành liên quan**, rồi xây WebOS riêng cho Thanh Hoá. Không thể gọi một website là bản chuyển nguyên vẹn iOS: UIKit có scene, vòng đời và quyền do hệ thống iOS quản lý; website chạy trong ngữ cảnh, origin và chính sách của trình duyệt. Đây là kết luận thiết kế từ hai mô hình thực thi khác nhau, không phải tuyên bố đã phân tích toàn bộ mã nguồn iOS. Nguồn công khai được đọc không cung cấp toàn bộ nhân, driver và dịch vụ hệ thống iOS để chuyển sang website. [Apple: vòng đời ứng dụng](https://developer.apple.com/documentation/uikit/managing-your-app-s-life-cycle), [MDN: same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Same-origin_policy).

Mục tiêu nghiệm thu hợp lý là một không gian có Home, danh mục ứng dụng, chuyển phiên nhanh, giữ ngữ cảnh, tìm kiếm có quyền, vùng duyệt web và cài đặt chung. Không dùng nhãn “100% iOS”, không hứa chạy ứng dụng iOS, quyền hệ thống hoặc khả năng Safari từ một iframe.

## Những nguyên tắc có thể học

Apple mô tả iPhone có các phiên tương tác ngắn hoặc dài, người dùng thường chuyển giữa nhiều ứng dụng. HIG khuyên giảm điều khiển trên màn hình, làm tác vụ chính rõ ràng và thích ứng với cấu hình người dùng. Đó là cơ sở cho shell gọn và thao tác mở/chuyển/quay lại dễ nhận ra. [Apple: Designing for iOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ios).

| Lớp trải nghiệm | Bài học từ nguồn chính thức | Ánh xạ đề xuất cho Thanh Hoá |
|---|---|---|
| Home và launcher | iOS có widget, quick action và Spotlight; không chỉ có lưới icon. [Apple: Designing for iOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ios) | Home ưu tiên công việc đang làm, ứng dụng ghim, tìm kiếm; danh mục đầy đủ riêng. Dùng ngôn ngữ và nhận diện Thanh Hoá hiện có. |
| Điều hướng | Tab bar chuyển phần cấp cao và giữ trạng thái điều hướng từng phần; toolbar dành cho hành động. [Apple: Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Phân biệt chuyển app, điều hướng trong app và hành động của tài liệu. Nút Trang chủ luôn rõ; quay lại không đồng nghĩa đóng app. |
| Đa phiên | Mỗi scene có vòng đời riêng; hệ thống có thể ngắt scene để thu hồi tài nguyên. [Apple: vòng đời](https://developer.apple.com/documentation/uikit/managing-your-app-s-life-cycle) | App khác session. Session lưu route, bản nháp và ngữ cảnh; trạng thái nền không có nghĩa tiến trình chạy liên tục. |
| Tìm kiếm | Search cần một vị trí dễ nhận biết, phạm vi rõ; lịch sử tìm kiếm cần cách xoá. [Apple: Searching](https://developer.apple.com/design/human-interface-guidelines/searching) | Tìm app, phiên đang mở, công việc/tệp được phép; tách tìm web và nêu nhà cung cấp khi dùng. |
| Quyền | Chỉ xin dữ liệu cần thiết, đúng lúc người dùng dùng tính năng, giải thích mục đích. [Apple: Privacy](https://developer.apple.com/design/human-interface-guidelines/privacy) | Chọn app không cấp quyền MCP; hỏi/quản lý quyền ở thao tác cần quyền; nhân kiểm lại từng lần gọi. |
| Tiếp cận | HIG yêu cầu nhãn cho công nghệ hỗ trợ, dùng bàn phím, có cách thay cho gesture và giảm chuyển động. [Apple: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility) | Nút HTML có tên, focus thấy rõ, tab order hợp lý; đóng/chuyển bằng nút và bàn phím; hỗ trợ giảm chuyển động, phóng to chữ. |

## Ranh giới của trình duyệt riêng

“Trình duyệt Thanh Hoá” trong website là một ứng dụng quản lý địa chỉ, tab/phiên và các vùng nhúng được phép. Engine vẫn là engine của trình duyệt đang mở website. Không coi nó là engine mới.

| Cơ chế web đã xác minh | Hệ quả thiết kế |
|---|---|
| `frame-ancestors` xác định trang nào được phép nhúng tài liệu; không được cha tự sửa để vượt chặn. [W3C CSP3, mục frame-ancestors](https://www.w3.org/TR/CSP3/#directive-frame-ancestors), [MDN: frame-ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors) | Trang bên ngoài mặc định mở ngoài; chỉ nhúng địa chỉ đã được bên cung cấp hỗ trợ và xác minh. Không gỡ header qua proxy để giả khả năng tương thích. |
| Same-origin hạn chế tương tác script giữa origin khác nhau. [MDN: same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Same-origin_policy) | Shell không đọc DOM, cookie hoặc lấy URL sau mỗi lần điều hướng trong iframe trang ngoài. Thanh địa chỉ/lịch sử chỉ thể hiện điều shell thực sự biết. |
| Safari chặn cookie bên thứ ba mặc định; WebKit nêu Storage Access API có kiểm soát người dùng và OAuth cho tích hợp xác thực. [WebKit: Full Third-Party Cookie Blocking](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/) | Nhúng không tạo SSO. Đăng nhập có thể cần mở ngoài; kiểm từng nhà cung cấp, không hứa mọi app dùng chung phiên. |
| `postMessage` hỗ trợ giao tiếp hợp tác giữa cửa sổ khác origin; phải giới hạn `targetOrigin`, kiểm nguồn nhận. [MDN: postMessage](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage) | App đối tác cần hợp đồng rõ: origin, loại message, schema, quyền; kiểm `event.origin`, `event.source` và nội dung. Không truyền token chủ quản cho iframe. |
| iframe có `sandbox`, chính sách `allow` và `title`; cấp tính năng còn chịu Permissions Policy. [MDN: iframe](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe) | Sandbox theo từng app; không cấp camera/microphone/download/pop-up đại trà. Mọi iframe có tên đọc được. |
| Ẩn iframe bằng CSS không tự phát sinh sự kiện visibility; timer tab nền có thể bị hạn chế. [MDN: Page Visibility](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API) | Shell tự phát tín hiệu active/inactive cho app nội bộ; không coi `display:none` là đã dừng xử lý. Không dựa timer client cho công việc bền vững. |
| Service worker gắn với origin/phạm vi, cần secure context, không có DOM; vòng đời theo sự kiện, có thể bị kết thúc. [MDN: Service Worker](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API), [W3C: lifetime](https://www.w3.org/TR/service-workers/#service-worker-lifetime) | Dùng cho cache/offline có lựa chọn ở giai đoạn sau. Không dùng làm daemon hoặc công cụ kiểm soát mọi website. Công việc dài vẫn ở runtime máy chủ. |

Lưu ý: các bản CSP3 và Service Workers W3C đang đọc là tài liệu dự thảo hiện hành ngày tra cứu; kiểm khả năng thực tế trên trình duyệt mục tiêu trước khi dùng tính năng mới. Bài WebKit nêu mốc triển khai chính sách năm 2020; đây không phải phép đo lại mọi cấu hình Safari năm 2026.

## Hợp đồng kiến trúc đề xuất cho V27

Phần này là quyết định đề xuất của dự án, không phải API do Apple quy định.

### Shell và app registry

Shell sở hữu Trang chủ, launcher, vùng ứng dụng, danh sách phiên gần đây, tìm kiếm và cài đặt. Registry dùng một danh mục chuẩn thay vì tạo danh sách icon riêng tách khỏi `nen-tang/danh-muc.json`.

Mỗi bản khai app cần: `id`, tên, mô tả, nhóm, icon, loại chạy (`internal`, `external`, `embed-approved`), route/URL, origin cho phép, chính sách nhiều phiên, phiên bản schema trạng thái, khả năng tìm kiếm, quyền cần và cách xử lý khi không dùng được. App nội bộ mở trong shell; app ngoài có nhãn “Mở website”, không mang trạng thái “đã kết nối” chỉ vì có URL. Chỉ bật nhúng khi có bằng chứng cho từng app.

### Session và vòng đời

Mỗi session có `sessionId`, `appId`, chủ sở hữu, route hiện tại, thời điểm cập nhật, trạng thái UI được phép lưu và phiên bản schema. Quy trình: tạo → hoạt động → nền → khôi phục hoặc đóng. Có thể có lỗi/gián đoạn; không tự lặp thao tác ghi khi khôi phục.

Tách ba khái niệm: phiên đăng nhập máy chủ, phiên giao diện ứng dụng và lượt chạy tác vụ. Đóng phiên giao diện không tự đăng xuất, xoá tệp hay huỷ tác vụ máy chủ. Đăng xuất phải xoá trạng thái UI riêng trong bộ nhớ/lưu trữ của chủ thể cũ. Bản nháp chứa dữ liệu nghiệp vụ cần lưu qua API có quyền; không đưa token, bí mật hay dữ liệu khách hàng vào localStorage.

V27 nên hỗ trợ nhiều app nội bộ đang mở, mỗi app khôi phục route/ngữ cảnh riêng. Chính sách nhiều session cùng một app chỉ bật khi app đó quản lý bản nháp và xung đột rõ ràng. Không trình bày “nền” như đã đình chỉ tài nguyên nếu chỉ ẩn DOM.

### Search của hệ điều hành

Một ô tìm kiếm, các nhóm kết quả rõ: ứng dụng, phiên đang mở và dữ liệu nội bộ được phép. Mỗi kết quả có nguồn, loại và điểm mở chính xác. Tìm không dấu vẫn giữ văn bản tiếng Việt gốc. Kết quả riêng tư phải do máy chủ lọc theo danh tính; không tải toàn bộ dữ liệu rồi chỉ ẩn trên trình duyệt.

Tìm web là chế độ riêng. V27 có thể cho nhập từ khoá và mở nhà cung cấp đã chọn trong tab ngoài. Đây là tiện ích chuyển truy vấn, chưa phải máy tìm kiếm sở hữu chỉ mục. Không sinh kết quả giả, không lấy kết quả từ trang bên ngoài qua iframe. Lịch sử cá nhân nên mặc định tối thiểu, có thao tác xoá và không lộ sau đăng xuất.

### Browser và quyền

V27 cần thanh địa chỉ, mở tab trong phạm vi shell hỗ trợ, nút mở ngoài luôn có, thông tin miền đích và lỗi dễ hiểu. Chỉ nhận URL `https:` hợp lệ theo chính sách; chặn scheme thực thi mã và URL có thông tin đăng nhập. Trang ngoài chưa được hỗ trợ nhúng phải đi theo luồng mở ngoài rõ ràng. Không dùng sự kiện `load` của iframe làm bằng chứng đăng nhập hoặc tải thành công toàn bộ nội dung; không tự khẳng định biết lý do iframe trắng.

Mọi công cụ nghiệp vụ tiếp tục qua `nhan/` với danh tính xác thực, phạm vi được cấp, cổng ghi, hạn mức và nhật ký metadata. Quyền browser thiết bị, quyền đọc dữ liệu app, quyền MCP và quyền agent tự thao tác là những lớp khác nhau. Người dùng chọn mô-đun hoặc mở website không tự cấp bất kỳ lớp nào còn lại. Giữ cơ chế phê duyệt browser hiện có khi công cụ tự thao tác; không chuyển sự cho phép một lần thành quyền không giới hạn.

## Chặng sau V27

| Chặng đề xuất | Kết quả và điều kiện bắt đầu |
|---|---|
| Củng cố phiên | Lưu/khôi phục máy chủ, cách ly danh tính, kiểm xung đột bản nháp, giới hạn tài nguyên. Chỉ mở nhiều session cùng app sau kiểm chứng. |
| PWA/offline | Manifest, cài vào Home Screen và cache shell khi có mạng HTTPS; xác định danh sách asset và dữ liệu được cache, xoá cache khi đổi danh tính. Không tự cache API riêng. |
| Liên kết sâu và chia sẻ | URL ổn định vào app/tài liệu, đích mở kiểm quyền lại; không nhét dữ liệu nhạy cảm hoặc token trong URL. |
| Tích hợp app đối tác | Xác minh từng origin, CSP/cookie/OAuth, hợp đồng postMessage hoặc MCP; có trạng thái kiểm chứng và ngày kiểm. |
| Search có chỉ mục riêng | Chốt nguồn được phép, quyền khai thác, cập nhật/xoá chỉ mục, phân quyền truy hồi và ranking; đo chất lượng trên dữ liệu cho phép trước khi gọi là máy tìm kiếm riêng. |
| Browser nâng cao | Nếu cần duyệt mọi web, automation hoặc cách ly phiên thật: thiết kế dịch vụ browser từ xa/native riêng, quản lý tài nguyên và phê duyệt riêng; không ghép thêm iframe rồi quảng bá như Safari. |

## Tiêu chí kiểm tra trước khi gọi V27 hoàn tất

- Mở các app nội bộ, chuyển qua Home/danh sách phiên và quay lại vẫn giữ ngữ cảnh; đóng UI không xoá dữ liệu hoặc lặp tác vụ.
- Khôi phục sau refresh, lỗi schema hoặc hết hạn đăng nhập có hành vi rõ; người dùng tiếp theo không nhận dữ liệu phiên trước.
- Search chỉ trả nguồn được phép; mở kết quả đi đúng app/ngữ cảnh; trạng thái rỗng/lỗi và chế độ tìm web không gây hiểu nhầm.
- URL không hợp lệ bị từ chối; app ngoài có đường mở ngoài; nhúng bị chặn không hiển thị thành công giả; không tuyên bố SSO từ URL.
- Kiểm máy tính/điện thoại, bàn phím, screen reader, phóng to chữ và giảm chuyển động; dùng phong cách iOS do chủ quản chốt ngày 17/11/2026 trong `DESIGN.md` của dự án.
- Kiểm quyền cho cả được phép/bị từ chối; không lưu bí mật ở browser, HTML hay nhật ký; chạy kiểm tra phù hợp theo `AGENTS.md`.

Chưa có số đo hoặc kết quả nghiệm thu cho các đề xuất trong tài liệu này. Mỗi bản triển khai cần ghi riêng phần đã có, phần chưa có và bằng chứng kiểm tra theo ngày.
