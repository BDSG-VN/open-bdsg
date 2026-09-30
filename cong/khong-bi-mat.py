#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cong/khong-bi-mat.py — CỔNG 1/4: chặn bí mật lọt vào kho công khai.

VÌ SAO CỔNG NÀY TỒN TẠI
  Kho "Open BDSG" là kho CÔNG KHAI. Đẩy lên là việc MỘT CHIỀU:
  GitHub giữ lịch sử, các bản fork giữ bản sao, bộ nhớ đệm máy tìm kiếm giữ nội dung.
  Xoá commit sau đó KHÔNG thu hồi được khoá đã lộ — chỉ có thu hồi (revoke) khoá mới có tác dụng.
  Cho nên cổng phải chặn TRƯỚC khi đẩy, không phải dọn sau khi đẩy.

PHẠM VI TỰ KHAI (cổng chỉ hứa đúng chừng này, không hứa hơn)
  CÓ quét: mọi tệp văn bản trong kho, theo từng dòng, bằng Python re.
  KHÔNG quét: nội dung tệp nhị phân (ảnh, font, trọng số .pth/.safetensors).
    ⇒ Bí mật bị nhét trong trọng số mô hình là thứ cổng này CHƯA ĐO và không phát hiện được.
    Tệp nhị phân có đuôi LẠ thì cổng báo hỏng, vì không chứng minh được nó sạch.
  KHÔNG có ngoại lệ nội dòng. Đây là cổng tuyệt đối: một khoá thật thì không có lý do nào
    đủ tốt để giữ lại trong kho công khai. (Hai cổng heuristic — khong-ha-tang, khong-lo-hong —
    mới cho phép miễn trừ nội dòng kèm lý do.)

BẪY ĐO ĐÃ GẶP THẬT (ghi lại để người sau không đo sai như cũ)
  1) `git grep` dùng POSIX ERE, KHÔNG hiểu `\\b`. Viết `\\bAKIA` cho git grep thì nó trả về
     0 kết quả và ta suýt kết luận "kho sạch". Cổng này viết bằng Python re, và có bài tự kiểm
     (--tu-kiem) chứng minh nó CẮN. Một cổng chưa bị thử ngược thì chưa phải là cổng.
  2) Một byte NUL làm `grep` im lặng coi cả tệp là nhị phân rồi bỏ qua, `file` báo "data".
     Cho nên ở đây tệp nhị phân không được im lặng bỏ qua: hoặc nằm trong danh sách đuôi
     nhị phân đã khai, hoặc bị báo hỏng.
  3) Chuỗi thử trong bài tự kiểm được GHÉP lúc chạy ("ghp_" + "A"*36) chứ không viết thẳng.
     Nếu viết thẳng, cổng sẽ tự bắt chính nó, và người ta sẽ tập thói quen thêm ngoại lệ
     cho cổng — mà mỗi ngoại lệ là một lỗ thủng.

MÃ THOÁT
  0 = không tìm thấy gì.  1 = tìm thấy vi phạm.  2 = cổng không tự chạy được (fail-closed:
  không đọc được tệp, không quét được ⇒ coi như HỎNG, tuyệt đối không coi như sạch).

Đo lần đầu: 25/09/2026. Python 3.9.6 (bản có sẵn trên máy dự án).
"""

import argparse
import os
import re
import sys
import tempfile

# ── Thư mục bỏ qua, kèm lý do từng cái ─────────────────────────────────────────
# Bỏ qua ở đây nghĩa là "không phải nội dung ta phát hành", KHÔNG phải "an toàn".
BO_QUA_THU_MUC = {
    ".git": "lịch sử git — lộ khoá trong lịch sử thì phải thu hồi khoá, không phải sửa cổng",
    ".venv": "môi trường ảo Python, không đẩy lên kho",
    "node_modules": "thư viện bên thứ ba, không đẩy lên kho",
    "__pycache__": "bộ đệm biên dịch",
    ".mypy_cache": "bộ đệm kiểm kiểu",
    ".pytest_cache": "bộ đệm chạy test",
    ".idea": "cấu hình IDE cá nhân",
    ".vscode": "cấu hình IDE cá nhân",
}

# ── Đuôi tệp nhị phân đã khai: được phép BỎ QUA nội dung ───────────────────────
# Mỗi đuôi ở đây là một lời hứa bị thu hẹp: cổng KHÔNG đọc bên trong chúng.
DUOI_NHI_PHAN_DA_KHAI = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".otf",
    ".pdf", ".zip", ".gz", ".bz2", ".xz", ".tar",
    ".parquet", ".arrow", ".npy", ".npz",
    ".safetensors", ".pth", ".bin", ".onnx", ".gguf",
    ".mp4", ".webm", ".mp3", ".wav",
}

# ── Tên tệp cấm theo TÊN (không cần đọc nội dung) ──────────────────────────────
TEN_TEP_CAM = {
    ".env": "tệp biến môi trường thật",
    ".env.local": "tệp biến môi trường thật",
    ".env.production": "tệp biến môi trường thật",
    ".env.prod": "tệp biến môi trường thật",
    ".netrc": "chứa mật khẩu đăng nhập máy chủ",
    ".pgpass": "chứa mật khẩu Postgres",
    "id_rsa": "khoá riêng SSH",
    "id_ed25519": "khoá riêng SSH",
    "id_ecdsa": "khoá riêng SSH",
    "credentials.json": "khoá dịch vụ (thường là Google service account)",
    "service-account.json": "khoá dịch vụ",
}
# Tệp mẫu thì được: chúng tồn tại để người dùng biết CẦN biến nào, không chứa giá trị thật.
DUOI_ENV_MAU = (".env.mau", ".env.example", ".env.template", ".env.sample", ".env.rong")
DUOI_KHOA_RIENG = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")

# ── Luật nội dung: (mã luật, biểu thức, vì sao) ────────────────────────────────
# Biểu thức viết bằng Python re. KHÔNG dùng cho git grep (xem BẪY ĐO 1).
LUAT = [
    ("khoa-openai",
     re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}"),
     "khoá OpenAI / LiteLLM. Cổng LiteLLM của dự án cấp khoá dạng này cho từng agent."),
    ("khoa-anthropic",
     re.compile(r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_\-]{20,}"),
     "khoá Anthropic."),
    ("token-github-cu",
     re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36}"),
     "token GitHub dạng cũ (ghp_/gho_/ghu_/ghs_/ghr_), đúng 36 ký tự sau tiền tố."),
    ("token-github-moi",
     re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{50,}"),
     "token GitHub fine-grained. Kho của dự án nằm trong tổ chức riêng tư BDSG-VN."),
    ("khoa-aws",
     re.compile(r"(?<![A-Za-z0-9])(AKIA|ASIA)[0-9A-Z]{16}"),
     "Access Key ID của AWS/S3-tương thích. Dự án dùng Cloudflare R2 qua giao thức S3."),
    ("khoa-pem",
     re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
     "khoá riêng PEM (RSA/EC/OPENSSH/PKCS8). Lộ là mất luôn danh tính máy chủ."),
    ("jwt",
     re.compile(r"(?<![A-Za-z0-9_\-])eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
     "JWT ba phần. Dự án ký SimpleJWT HS256 hạn 3 ngày — token hết hạn vẫn lộ cấu trúc "
     "và đôi khi lộ cả định danh người dùng ở phần payload."),
    ("chuoi-ket-noi-postgres",
     re.compile(r"postgres(?:ql)?://[^\s:/@]+:([^\s@/]+)@"),
     "chuỗi kết nối Postgres CÓ mật khẩu."),
    ("chuoi-ket-noi-mysql",
     re.compile(r"mysql://[^\s:/@]+:([^\s@/]+)@"),
     "chuỗi kết nối MySQL/MariaDB CÓ mật khẩu."),
    ("chuoi-ket-noi-mongo-redis",
     re.compile(r"(?:mongodb(?:\+srv)?|redis|amqp)://[^\s:/@]+:([^\s@/]+)@"),
     "chuỗi kết nối có mật khẩu nhúng."),
    ("khoa-slack",
     re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
     "token Slack."),
    ("khoa-google",
     re.compile(r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_\-]{35}"),
     "khoá API Google."),
]

# Mật khẩu "giả" hợp lệ trong tài liệu: chuỗi kết nối mẫu thì được phép tồn tại,
# vì tài liệu phải chỉ cho người ta biết CẦN điền gì vào đâu.
CHO_THAY_THE = re.compile(
    r"^(?:\$\{[^}]*\}|\$[A-Z_]+|<[^>]*>|\{\{[^}]*\}\}|x{3,}|\*{3,}|\.{3,}|"
    r"MAT_KHAU|MATKHAU|PASSWORD|PASS|CHANGEME|REDACTED|AN_DI|GIA_TRI|xxx)$",
    re.IGNORECASE,
)


def la_nhi_phan(duong_dan):
    """Đọc 8KB đầu, có byte NUL thì coi là nhị phân.

    Đây đúng là phép thử mà grep dùng — và cũng đúng là chỗ grep im lặng bỏ tệp.
    Ta không bỏ im lặng: hàm quét sẽ quyết định báo hỏng nếu đuôi tệp chưa được khai.
    """
    with open(duong_dan, "rb") as f:
        return b"\x00" in f.read(8192)


def duyet_tep(goc):
    """Trả về danh sách đường dẫn tuyệt đối cần xét, đã bỏ các thư mục đã khai."""
    ket_qua = []
    for thu_muc, cac_con, cac_tep in os.walk(goc):
        cac_con[:] = [c for c in cac_con if c not in BO_QUA_THU_MUC]
        for ten in cac_tep:
            ket_qua.append(os.path.join(thu_muc, ten))
    return sorted(ket_qua)


def quet_kho(goc):
    """Quét toàn kho. Trả về (danh_sach_vi_pham, danh_sach_loi_cong).

    vi_pham: (duong_dan_tuong_doi, so_dong, ma_luat, do_dai_khop)
      — CỐ Ý không trả về giá trị khớp. In ra giá trị là lộ bí mật lần thứ hai,
        lần này vào log CI, và log CI thường công khai hơn cả kho.
    loi_cong: những chỗ cổng KHÔNG chứng minh được là sạch ⇒ tính là hỏng.
    """
    vi_pham = []
    loi_cong = []

    for duong_dan in duyet_tep(goc):
        tuong_doi = os.path.relpath(duong_dan, goc)
        ten = os.path.basename(duong_dan)
        ten_thuong = ten.lower()
        _, duoi = os.path.splitext(ten_thuong)

        # 1. Cấm theo TÊN tệp
        if ten_thuong in TEN_TEP_CAM:
            vi_pham.append((tuong_doi, 0, "ten-tep-cam", 0))
            continue
        if ten_thuong.startswith(".env") and not ten_thuong.endswith(DUOI_ENV_MAU):
            vi_pham.append((tuong_doi, 0, "ten-tep-cam-env", 0))
            continue
        if duoi in DUOI_KHOA_RIENG:
            vi_pham.append((tuong_doi, 0, "duoi-khoa-rieng", 0))
            continue

        # 2. Tệp nhị phân
        try:
            if la_nhi_phan(duong_dan):
                if duoi in DUOI_NHI_PHAN_DA_KHAI:
                    continue  # đã khai phạm vi: cổng không đọc bên trong
                loi_cong.append(
                    (tuong_doi, "tệp nhị phân đuôi '%s' chưa khai — không chứng minh được là sạch" % (duoi or "(không có)"))
                )
                continue
        except OSError as loi:
            loi_cong.append((tuong_doi, "không đọc được: %s" % loi.strerror))
            continue

        # 3. Quét nội dung theo dòng
        try:
            with open(duong_dan, "r", encoding="utf-8", errors="replace") as f:
                for so_dong, dong in enumerate(f, start=1):
                    for ma, bieu_thuc, _ in LUAT:
                        for khop in bieu_thuc.finditer(dong):
                            # Chuỗi kết nối có nhóm bắt mật khẩu: bỏ qua nếu là chỗ-thay-thế
                            if khop.groups() and khop.group(1) is not None:
                                if CHO_THAY_THE.match(khop.group(1)):
                                    continue
                            vi_pham.append((tuong_doi, so_dong, ma, len(khop.group(0))))
        except OSError as loi:
            loi_cong.append((tuong_doi, "không đọc được: %s" % loi.strerror))

    return vi_pham, loi_cong


def in_bao_cao(goc, vi_pham, loi_cong):
    ly_do = dict((ma, mo_ta) for ma, _, mo_ta in LUAT)
    print("CỔNG khong-bi-mat — gốc quét: %s" % goc)
    if not vi_pham and not loi_cong:
        print("  ĐẠT: không tìm thấy khoá, khoá PEM, JWT, chuỗi kết nối có mật khẩu, hay tệp .env.")
        return
    if vi_pham:
        print("  HỎNG: %d vị trí. (Giá trị KHÔNG được in ra — in ra là lộ lần thứ hai, vào log.)" % len(vi_pham))
        for duong_dan, so_dong, ma, do_dai in vi_pham:
            vi_tri = "%s:%d" % (duong_dan, so_dong) if so_dong else duong_dan
            phu = "  khớp dài %d ký tự" % do_dai if do_dai else ""
            print("    %-52s [%s]%s" % (vi_tri, ma, phu))
            if ma in ly_do:
                print("        vì sao cấm: %s" % ly_do[ma])
    if loi_cong:
        print("  HỎNG (cổng không tự chứng minh được — fail-closed): %d tệp." % len(loi_cong))
        for duong_dan, ghi_chu in loi_cong:
            print("    %-52s %s" % (duong_dan, ghi_chu))
        print("    Cách xử đúng: thêm đuôi vào DUOI_NHI_PHAN_DA_KHAI KÈM lý do, hoặc bỏ tệp ra khỏi kho.")
    if vi_pham:
        print("  NHỚ: nếu đây là khoá THẬT, sửa cổng hay xoá commit đều vô ích. Phải THU HỒI khoá.")


def tu_kiem():
    """Bài thử ngược: chứng minh cổng CẮN, và chứng minh nó không cắn bừa.

    Vì sao bắt buộc: một cổng luôn trả 'sạch' thì không phân biệt được với một cổng hỏng.
    Chuỗi thử được ghép lúc chạy để chính tệp này không chứa mẫu thật.
    """
    mau = {
        "khoa-openai": "KHOA = '" + "sk-" + "a" * 40 + "'",
        "token-github-cu": "TOKEN = '" + "ghp_" + "A" * 36 + "'",
        "token-github-moi": "PAT = '" + "github_pat_" + "B" * 60 + "'",
        "khoa-aws": "AWS = '" + "AKIA" + "C" * 16 + "'",
        "khoa-pem": "-----BEGIN" + " RSA PRIVATE KEY-----",
        "jwt": "T = '" + "eyJ" + "a" * 20 + "." + "eyJ" + "b" * 20 + "." + "c" * 20 + "'",
        "chuoi-ket-noi-postgres": "DSN = 'postgres" + "ql://nguoidung:matkhauthat@may-chu/csdl'",
    }
    sach = (
        "# Dòng sạch: tài liệu hướng dẫn, phải KHÔNG bị bắt.\n"
        "DSN = 'postgres" + "ql://nguoidung:${MAT_KHAU}@may-chu/csdl'\n"
        "GHI_CHU = 'mã mô hình công khai: bdsg-ai-v1'\n"
    )
    hong = []
    with tempfile.TemporaryDirectory() as tam:
        for ma, noi_dung in mau.items():
            with open(os.path.join(tam, "cai_%s.txt" % ma.replace("-", "_")), "w", encoding="utf-8") as f:
                f.write(noi_dung + "\n")
        with open(os.path.join(tam, "sach.txt"), "w", encoding="utf-8") as f:
            f.write(sach)
        # Tệp nhị phân đuôi lạ: phải bị tính là lỗi cổng, không được im lặng bỏ qua.
        with open(os.path.join(tam, "la.dat"), "wb") as f:
            f.write(b"abc\x00def")

        vi_pham, loi_cong = quet_kho(tam)
        da_bat = set(v[2] for v in vi_pham)
        for ma in mau:
            if ma not in da_bat:
                hong.append("KHÔNG bắt được mẫu '%s' — cổng thủng ở luật này." % ma)
        if any(v[0] == "sach.txt" for v in vi_pham):
            hong.append("Bắt nhầm dòng sạch (chỗ-thay-thế ${MAT_KHAU}) — cổng cắn bừa.")
        if not any(t == "la.dat" for t, _ in loi_cong):
            hong.append("Tệp nhị phân đuôi lạ bị bỏ qua im lặng — đúng cái bẫy byte NUL.")

    print("TỰ KIỂM khong-bi-mat: %d mẫu cài, %d luật nội dung." % (len(mau), len(LUAT)))
    if hong:
        for d in hong:
            print("  HỎNG: %s" % d)
        return 1
    print("  ĐẠT: cổng bắt đủ mẫu cài, không bắt nhầm dòng sạch, không bỏ qua nhị phân lạ.")
    return 0


def main():
    bo_phan_tich = argparse.ArgumentParser(description="Cổng 1/4: chặn bí mật lọt vào kho công khai.")
    bo_phan_tich.add_argument("--goc", default=None, help="thư mục gốc cần quét (mặc định: thư mục cha của cong/)")
    bo_phan_tich.add_argument("--tu-kiem", action="store_true", help="chạy bài thử ngược, chứng minh cổng cắn")
    tham_so = bo_phan_tich.parse_args()

    if tham_so.tu_kiem:
        return tu_kiem()

    goc = tham_so.goc or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(goc):
        print("HỎNG: không thấy thư mục gốc '%s'." % goc)
        return 2

    try:
        vi_pham, loi_cong = quet_kho(goc)
    except Exception as loi:  # fail-closed: cổng vỡ thì KHÔNG được coi là kho sạch
        print("HỎNG: cổng tự vỡ khi quét (%s: %s). Coi như KHÔNG đạt." % (type(loi).__name__, loi))
        return 2

    in_bao_cao(goc, vi_pham, loi_cong)
    if vi_pham:
        return 1
    if loi_cong:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
