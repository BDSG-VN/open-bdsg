# TRIEN-KHAI — cấu hình vhost cho `web3.bdsg.vn`

Tệp này viết sẵn cho **người đang ngồi trên máy chủ**. Người viết tệp không chạy
lệnh nào trong đây — mọi lệnh dưới đây là để bạn chạy, sau khi đọc hết.

## 0. Trạng thái đã đo, đọc trước khi gõ gì

Đo **20:13 ngày 26/09/2026**, từ máy ngoài:

```
curl -sS -o /dev/null -w "%{http_code} %{remote_ip}\n" https://web3.bdsg.vn/
→ 200
curl -sSI --resolve web3.bdsg.vn:443:<IP-GOC> https://web3.bdsg.vn/ | head -5
→ HTTP/2 200 · content-length: 19979 · có đủ 4 header bảo mật
```

**Vhost đã có, chứng chỉ đã có, tệp đã nằm trong docroot.** Nghĩa là phần lớn
tệp này là **bản ghi lại thứ đang chạy**, không phải việc còn phải làm. Bạn cần
nó trong ba trường hợp: dựng lại sau sự cố, dựng trên máy khác, hoặc kiểm rằng
thứ đang chạy đúng bằng thứ đã duyệt.

Việc **còn lại thật sự** chỉ có mục 5: đẩy bản `index.html` mới (bản trong kho
lúc này là **20.523 byte**, máy chủ đang giữ bản **19.979 byte** — hai sửa đổi ở
mục 5.0).

## 1. Vì sao không có đường dẫn và địa chỉ IP thật trong tệp này

Kho này **công khai**. Cổng `cong/khong-ha-tang.py` chặn IPv4 công cộng và đường
dẫn vận hành dạng `/home/<người dùng>/…` trong mọi tệp văn bản của kho — đúng
lỗi ấy đã bị bắt một lần khi `trang-agent/README.md` viết thẳng docroot ra.

Nên tệp này dùng chỗ trống:

| Chỗ trống | Lấy ở đâu (trên máy chủ, không phải trong kho) |
|---|---|
| `<IP-GOC>` | Địa chỉ trong dòng `<VirtualHost …:80>` của **khối `agent.bdsg.vn`** nằm ngay trên khối này trong cùng tệp cấu hình |
| `<DOCROOT-WEB3>` | Cùng cây thư mục với docroot của `agent.bdsg.vn`, đổi `agent` → `web3` |
| `<TEP-CAU-HINH>` | Tệp Apache dùng chung đang khai các tên miền ứng dụng BDSG; tìm bằng `grep -rl "agent.bdsg.vn" /etc/httpd/conf/extra/` |
| `<THU-MUC-ACME>` | Thư mục acme.sh của `web3.bdsg.vn`, cùng khuôn với thư mục của `agent.bdsg.vn` |

Đừng thay chỗ trống rồi commit ngược lại kho. Nếu lỡ, cổng sẽ cắn:
`.venv/bin/python cong/khong-ha-tang.py` → mã thoát 1.

## 2. ⚠ Tệp cấu hình này dùng chung cho 56 tên miền

Một dòng sai trong tệp ấy làm **cả 56 tên miền** không nạp được cấu hình. Vì vậy
trình tự dưới đây **không được bỏ bước nào**, và không được đảo thứ tự:

```
1) sao lưu  →  2) apachectl configtest  →  3) CHỈ KHI "Syntax OK" mới graceful
```

**KHÔNG BAO GIỜ `apachectl restart`.** `restart` cắt mọi kết nối đang mở của cả
56 tên miền; `graceful` để tiến trình cũ phục vụ nốt rồi mới thay. Sự khác nhau
ấy là toàn bộ lý do quy tắc này tồn tại.

Hai điều nữa về `configtest`, cả hai đã gặp thật:

- Trên máy này `configtest` in sẵn **hai dòng cảnh báo** `AH00112: Warning:
  DocumentRoot […/video] does not exist`. Đó là **cảnh báo có từ trước**, không
  phải do bạn. Thứ duy nhất quyết định là dòng cuối có đúng chữ `Syntax OK`.
- `configtest` chỉ xét **cú pháp**. Nó không nói vhost có bắt đúng tên miền hay
  không. Phép đo ấy nằm ở mục 6.

## 3. Thư mục và chứng chỉ

```bash
# thư mục docroot, sở hữu bởi user DirectAdmin của bdsg.vn (KHÔNG phải root)
mkdir -p <DOCROOT-WEB3>
chown -R <USER-DA>:<USER-DA> <DOCROOT-WEB3>
chmod 755 <DOCROOT-WEB3>
```

Chứng chỉ xin **sau khi khối `:80` đã nạp** (khối `:80` mở sẵn lối
`/.well-known/acme-challenge/`), và xin **trước khi** nạp khối `:443` — vì khối
`:443` trỏ tới tệp chứng chỉ, chứng chỉ chưa có thì `configtest` trượt.

```bash
acme.sh --issue -d web3.bdsg.vn --webroot /var/www/html --keylength ec-256
```

Nếu tên miền đang đi qua Cloudflare ở chế độ proxy, mở lối
`/.well-known/acme-challenge/` hoặc tạm tắt proxy cho bản ghi này trong lúc xin.

## 4. Khối vhost

Lấy nguyên khuôn từ khối `agent.bdsg.vn` **thật** trong cùng tệp cấu hình, đổi
tên miền. Dán **ngay sau** khối `agent.bdsg.vn`, giữ nguyên thứ tự `:80` rồi
`:443`.

```apache
# ═════════════════════════════════════════════════════════════════════════
# web3.bdsg.vn — BDSG Web3, lop blockchain cua Open BDSG OS.
# Trang TINH, KHONG mot dong JavaScript (xem CSP script-src 'none' o khoi 443).
# TEP NAY DUNG CHUNG CHO 56 TEN MIEN: sao luu → apachectl configtest →
# CHI KHI DAT moi graceful. KHONG BAO GIO restart.
# ═════════════════════════════════════════════════════════════════════════
<VirtualHost <IP-GOC>:80>
  ServerName web3.bdsg.vn
  DocumentRoot "<DOCROOT-WEB3>"
  Alias /.well-known/acme-challenge/ /var/www/html/.well-known/acme-challenge/
  <Directory /var/www/html/.well-known/acme-challenge>
    Require all granted
  </Directory>
  <Directory "<DOCROOT-WEB3>">
    Options -Indexes +FollowSymLinks
    AllowOverride All
    Require all granted
  </Directory>
  ErrorLog  /var/log/httpd/domains/bdsg.vn.web3.error.log
  CustomLog /var/log/httpd/domains/bdsg.vn.web3.log combined
</VirtualHost>

<VirtualHost <IP-GOC>:443>
  ServerName web3.bdsg.vn
  DocumentRoot "<DOCROOT-WEB3>"

  SSLEngine on
  SSLCertificateFile    <THU-MUC-ACME>/fullchain.cer
  SSLCertificateKeyFile <THU-MUC-ACME>/web3.bdsg.vn.key

  Alias /.well-known/acme-challenge/ /var/www/html/.well-known/acme-challenge/
  <Directory /var/www/html/.well-known/acme-challenge>
    Require all granted
  </Directory>

  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  # script-src 'none': trang nay KHONG co mot dong JavaScript nao. Khai dung nhu
  # vay thi mot lan ai do chen script vao se hong NGAY, thay vi chay am tham.
  Header always set Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'none'; connect-src 'self'; frame-ancestors 'self' https://*.bdsg.vn; base-uri 'none'; form-action 'self'"

  <Directory "<DOCROOT-WEB3>">
    Options -Indexes +FollowSymLinks
    AllowOverride All
    Require all granted
  </Directory>
  ErrorLog  /var/log/httpd/domains/bdsg.vn.web3.error.log
  CustomLog /var/log/httpd/domains/bdsg.vn.web3.log combined
</VirtualHost>
```

### Từng dòng CSP khớp với đúng thứ trang cần

Đã đối chiếu với `index.html` — không có dòng nào thừa, không có dòng nào thiếu:

| Chỉ thị | Trang dùng gì | Vì sao khai đúng như vậy |
|---|---|---|
| `script-src 'none'` | trang có **0 thẻ `<script>`**, 0 thuộc tính `on*`, 0 URL `javascript:` | khai đúng sự thật thì một lần chèn script là hỏng NGAY, không chạy âm thầm |
| `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com` | CSS nằm **inline trong `<style>`** + biểu kiểu Google Fonts | bỏ `'unsafe-inline'` là trang mất sạch định dạng; đây là cái giá của CSS inline, ghi ra chứ không giấu |
| `font-src https://fonts.gstatic.com` | Google Fonts phát `.woff2` từ gstatic | không có `'self'` vì trang không tự phục vụ phông nào |
| `img-src 'self' data:` | trang **không có ảnh nào** | giữ để lỡ sau này thêm, và vẫn chặn ảnh từ máy chủ lạ |
| `connect-src 'self'` | trang **không gọi mạng** (không JS thì không fetch) | thắt luôn |
| `frame-ancestors 'self' https://*.bdsg.vn` | cho phép nhúng trong các tên miền BDSG | chống clickjacking từ ngoài |
| `base-uri 'none'` · `form-action 'self'` | trang **không có `<base>`**, **không có `<form>`** | chặn hai lối chuyển hướng cổ điển |

Nếu một ngày trang phải có JavaScript: sửa CSP **cùng lúc**, đừng nới trước cho
tiện. Một lời khai rộng tay hơn sự thật là một lời khai vô dụng.

## 5. Đẩy tệp

### 5.0 Việc còn lại: bản trong kho mới hơn bản trên máy chủ

Bản trên máy chủ (19.979 byte) là bản viết lúc 20:01. Bản trong kho hiện tại
(20.523 byte) sửa **hai chỗ**, cả hai đều cần đẩy:

1. **Sửa một khẳng định đã hết đúng.** Bản cũ viết "Chưa có gì chạy sau tên miền
   này… gốc trả HTTP 404". Sau khi vhost được nạp, câu ấy **sai**. Bản mới ghi
   đúng: 404 là phép đo cũ, 200 là phép đo 20:13, và đằng sau tên miền vẫn không
   có dịch vụ nào ngoài một tệp tĩnh.
2. **Sửa một lỗi nhìn thấy được trên điện thoại.** Thanh đầu `sticky` cao
   **101px** ở bề ngang 400px (nó xuống 2 dòng). Nút "Trang này chưa có gì ↓"
   nhảy tới `#chua-co-gi` thì nhãn mục và đỉnh `h2` chui xuống dưới thanh — đo
   được: nhãn ở `top=59px`, đáy thanh ở `101px`. Thêm
   `section[id]{scroll-margin-top:116px}` là hết.

### 5.1 Lệnh đẩy

```bash
# từ máy làm việc, đứng ở gốc kho open-bdsg-os
rsync -avz --checksum trang-web3/index.html <MAY-CHU>:<DOCROOT-WEB3>/index.html
ssh <MAY-CHU> 'chown <USER-DA>:<USER-DA> <DOCROOT-WEB3>/index.html && chmod 644 <DOCROOT-WEB3>/index.html'
```

Chỉ một tệp `index.html`. Không có bước đóng gói, không thư mục `assets`, không
tệp phụ nào.

## 6. Lệnh kiểm chứng sau khi deploy

**Mã 200 không chứng minh trang chạy** — ở dự án này đã có tên miền thiếu vhost
mà vẫn trả 200 của một tên miền khác. Nên phải kiểm đủ sáu phép dưới đây.

```bash
# 6.1 — vhost có thật sự được nạp, và nạp từ đúng dòng nào của tệp nào
apachectl -S 2>/dev/null | grep web3
# CHỜ: hai dòng, "port 80 namevhost web3.bdsg.vn" và "port 443 namevhost web3.bdsg.vn",
#      mỗi dòng kèm <TEP-CAU-HINH>:<số dòng>. Không thấy dòng nào = chưa graceful.

# 6.2 — đánh thẳng vào máy gốc, bỏ qua Cloudflare, để biết GỐC trả gì
curl -sS -o /dev/null -w "%{http_code}\n" --resolve web3.bdsg.vn:443:<IP-GOC> https://web3.bdsg.vn/
# CHỜ: 200.  KHÔNG dùng `curl https://127.0.0.1/` — nó trúng vhost mặc định,
#      tức là trang của một tên miền khác, và bạn sẽ kết luận nhầm.

# 6.3 — trang trả về có ĐÚNG là trang này không (đây mới là phép chống bắt lạc vhost)
curl -sS --resolve web3.bdsg.vn:443:<IP-GOC> https://web3.bdsg.vn/ | grep -c "<title>BDSG Web3"
# CHỜ: 1.  Nếu 0 thì đang rơi vào vhost của tên miền khác, dù mã vẫn 200.
#      Khớp tiền tố "<title>BDSG Web3" chứ KHÔNG khớp cả thẻ đóng: phần đuôi tiêu
#      đề còn được biên tập, và một phép kiểm tự đỏ mỗi lần sửa chữ là phép kiểm
#      sẽ bị bỏ qua.

# 6.4 — byte trả về khớp đúng tệp trong kho
curl -sS --resolve web3.bdsg.vn:443:<IP-GOC> https://web3.bdsg.vn/ | shasum -a 256
shasum -a 256 trang-web3/index.html
# CHỜ: hai mã băm bằng nhau.

# 6.5 — bốn header bảo mật có ra tới trình duyệt không
curl -sSI --resolve web3.bdsg.vn:443:<IP-GOC> https://web3.bdsg.vn/ \
  | grep -i -E "strict-transport-security|x-content-type-options|referrer-policy|content-security-policy" | wc -l
# CHỜ: 4.  Thiếu = mod_headers chưa bật, hoặc khối 443 chưa nạp.

# 6.6 — CSP có đúng script-src 'none' không (đây là lời khai, không phải trang trí)
curl -sSI --resolve web3.bdsg.vn:443:<IP-GOC> https://web3.bdsg.vn/ | grep -o "script-src 'none'"
# CHỜ: in ra "script-src 'none'".

# 6.7 — qua Cloudflare, như người dùng thật thấy
curl -sS -o /dev/null -w "%{http_code} %{remote_ip}\n" https://web3.bdsg.vn/
# CHỜ: 200, và IP thuộc dải Cloudflare (khác <IP-GOC>).

# 6.8 — http:// cổng 80. ĐÃ ĐO 26/09/2026: trả 200 và phục vụ trang TRẦN,
# KHÔNG chuyển hướng sang https. Khối :80 ở trên KHÔNG có Redirect — việc ép
# https hiện do Cloudflare làm hộ. Tắt proxy Cloudflare là http:// lộ trần.
curl -sSI -o /dev/null -w "%{http_code} %{redirect_url}\n" http://web3.bdsg.vn/
# ĐO ĐƯỢC HÔM NAY: "200" và redirect_url RỖNG.
# Muốn chặn tại gốc thì thêm vào khối :80 (sau Alias acme-challenge):
#   RewriteEngine On
#   RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
#   RewriteRule ^/?(.*)$ https://web3.bdsg.vn/$1 [R=301,L]
# Chưa thêm: sửa vhost dùng chung của 56 tên miền là việc phải có người duyệt.
```

Cuối cùng, mở bằng mắt ở bề ngang điện thoại và kiểm hai thứ máy không thấy:
bấm nút **"Trang này chưa có gì ↓"** — nhãn "CHƯA CÓ, NÓI THẲNG" phải hiện **dưới**
thanh đầu, không bị thanh che; và bảng "Cách rẻ hơn đã có sẵn" phải **cuộn ngang
trong khung của nó**, không kéo giãn cả trang.

## 7. Lùi lại

```bash
# trên máy chủ
cp <TEP-CAU-HINH> <TEP-CAU-HINH>.bak-web3-$(date +%Y%m%d-%H%M%S)   # làm TRƯỚC khi sửa
# nếu configtest trượt hoặc trang hỏng:
cp <TEP-CAU-HINH>.bak-web3-<dấu-thời-gian> <TEP-CAU-HINH>
apachectl configtest && apachectl graceful
```

Bản sao lưu đặt tên có tên miền và dấu thời gian, để sáu tháng sau còn biết bản
nào của việc nào. Thư mục cấu hình trên máy này đang có hàng chục tệp `.bak` —
tên mơ hồ là tên vô dụng.
