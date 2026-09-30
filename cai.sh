#!/usr/bin/env bash
# cai.sh — cài Open BDSG và NÓI THẬT phần nào chạy được.
#
# Hai chế độ:
#   bash cai.sh --chi-kiem     chỉ đo môi trường, KHÔNG cài gì, không tạo tệp nào
#   bash cai.sh                cài phần mô hình vào venv rồi chạy mọi cổng nghiệm thu
#
# FAIL-CLOSED. Không có `|| true` ở bất kỳ đâu trong tệp này. Một bước hỏng là
# dừng, vì một bộ cài báo "xong" trên một hệ nửa vời còn tệ hơn một bộ cài báo lỗi:
# người ta sẽ tin nó rồi mất một buổi mới biết.

set -euo pipefail

GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$GOC"

CHI_KIEM=0
[ "${1:-}" = "--chi-kiem" ] && CHI_KIEM=1

PY_TOI_THIEU_HOA=3
PY_TOI_THIEU_PHU=8

x()  { printf '  %s\n' "$*"; }
tieu(){ printf '\n%s\n  %s\n%s\n' "══════════════════════════════════════════════════════════════════════" "$*" "══════════════════════════════════════════════════════════════════════"; }
dung(){ printf '\n  DỪNG: %s\n' "$*" >&2; exit 1; }

# ─────────────────────────────────────────────────────────── 1. Python
tieu "1/5 · Môi trường"

PY=""
for p in python3.12 python3.11 python3.10 python3.9 python3.8 python3; do
  command -v "$p" >/dev/null 2>&1 || continue
  # Doc phien ban bang chinh trinh thong dich, khong bang cat chuoi tu `-V`:
  # dinh dang cua `-V` khong phai hop dong on dinh.
  if "$p" -c "import sys;raise SystemExit(0 if sys.version_info[:2]>=($PY_TOI_THIEU_HOA,$PY_TOI_THIEU_PHU) else 1)" 2>/dev/null; then
    PY="$p"; break
  fi
done
[ -n "$PY" ] || dung "cần Python >= ${PY_TOI_THIEU_HOA}.${PY_TOI_THIEU_PHU}, không tìm thấy bản nào đạt."
x "Python   : $("$PY" -c 'import sys;print(sys.version.split()[0])')  ($PY)"
x "Hệ       : $(uname -s) $(uname -m)"
x "Thư mục  : $GOC"

CO_PIP=0
"$PY" -m pip --version >/dev/null 2>&1 && CO_PIP=1
x "pip      : $([ $CO_PIP -eq 1 ] && echo 'có' || echo 'KHÔNG — chỉ cài được phần lõi, và phần lõi không cần pip')"

CO_VENV=0
"$PY" -c 'import venv' >/dev/null 2>&1 && CO_VENV=1
x "venv     : $([ $CO_VENV -eq 1 ] && echo 'có' || echo 'KHÔNG')"

# ─────────────────────────────────────────────────── 2. Lõi: không cần cài
tieu "2/5 · Lõi — không cần cài gì"

x "requirements.txt cố ý rỗng: lõi chỉ dùng thư viện chuẩn của Python."
x "Đang kiểm điều đó thay vì tin lời khai…"
"$PY" - <<'PY'
import ast, importlib.util, sys, sysconfig
from pathlib import Path
LOI = ("nhan", "tac-nhan", "phuc-vu", "linh-vuc", "cong", "trinh-dieu-khien", "tri-nho")

# `sys.stdlib_module_names` CHI CO TU PYTHON 3.10. Ban dau viet
# `getattr(sys, "stdlib_module_names", ())` — tren Python 3.8 no tra tuple RONG,
# nen "khong gi la thu vien chuan" va bo kiem bao ca `json`, `os`, `sys` la thu
# vien ngoai. No TRA LOI SAI thay vi BAO LOI, dung tren phien ban can no nhat.
# Bat duoc 01/10/2026 khi chay that tren Python 3.8.10 cua mot hosting.
_TEN_CHUAN = set(getattr(sys, "stdlib_module_names", ()) or ())
_THU_MUC_CHUAN = sysconfig.get_paths().get("stdlib", "")

def la_thu_vien_chuan(ten):
    if _TEN_CHUAN:
        return ten in _TEN_CHUAN
    # Duong lui cho < 3.10: hoi chinh he thong nhap khau xem mo-dun nam o dau.
    if ten in sys.builtin_module_names:
        return True
    try:
        sp = importlib.util.find_spec(ten)
    except (ImportError, ValueError):
        return False
    if sp is None:
        return False
    if sp.origin in ("built-in", "frozen"):
        return True
    return bool(sp.origin) and _THU_MUC_CHUAN and sp.origin.startswith(_THU_MUC_CHUAN)
ngoai, tep = {}, 0
for thu in LOI:
    for p in Path(thu).rglob("*.py"):
        tep += 1
        try:
            cay = ast.parse(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  KHÔNG phân tích được {p}: {e}"); raise SystemExit(1)
        for n in ast.walk(cay):
            if isinstance(n, ast.Import):
                ten = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                ten = [] if n.level else [(n.module or "").split(".")[0]]
            else:
                continue
            for t in ten:
                if not t or la_thu_vien_chuan(t):
                    continue
                # Mo-dun cuc bo trong chinh kho, theo BA cach no co the duoc tim thay:
                #   (a) goi/thu muc o goc kho        vi du `nhan`
                #   (b) tep .py o goc kho
                #   (c) tep .py ANH EM cung thu muc  vi du phuc-vu/cau_hinh.py
                # Ban dau thieu (c) nen bo kiem bao 7 mo-dun anh em la "thu vien
                # ngoai" — bao gia, bat duoc 01/10/2026 ngay lan chay dau.
                if (Path(t).exists() or Path(t.replace("_", "-")).exists()
                        or Path(f"{t}.py").exists()
                        or (p.parent / f"{t}.py").exists()):
                    continue
                ngoai.setdefault(t, set()).add(str(p))
print(f"  đã đọc {tep} tệp .py trong lõi")
if ngoai:
    for t, ds in sorted(ngoai.items()):
        print(f"  THƯ VIỆN NGOÀI: {t}  ← {sorted(ds)[0]}")
    print("  → requirements.txt đang nói sai. Sửa tệp ấy trước khi phát hành.")
    raise SystemExit(1)
print("  ĐẠT: 0 thư viện ngoài. Lõi cài được cả ở nơi không có quyền cài gói.")
PY

# ───────────────────────────────────────────────── 3. Sổ ghi + cổng nghiệm thu
tieu "3/5 · Sổ ghi lĩnh vực và cổng nghiệm thu"

"$PY" linh-vuc/so_ghi.py
"$PY" linh-vuc/thu_so_ghi.py

if [ -f cong/danh-tinh.local ]; then
  bash cong/chay-tat-ca.sh
else
  x "BỎ QUA cổng nghiệm thu: thiếu cong/danh-tinh.local."
  x "Cổng khong-danh-tinh cố ý thoát khác 0 khi thiếu tệp ấy — 'không có danh"
  x "sách' không phải 'đã kiểm'. Tạo bằng:  cp cong/danh-tinh.mau cong/danh-tinh.local"
fi

# ───────────────────────────────────────────────────────── 4. Phần mô hình
tieu "4/5 · Phần mô hình (tuỳ chọn)"

if [ $CHI_KIEM -eq 1 ]; then
  x "--chi-kiem: không cài gì."
  if "$PY" -c 'import torch' >/dev/null 2>&1; then
    x "torch    : đã có ($("$PY" -c 'import torch;print(torch.__version__)'))"
  else
    x "torch    : chưa có. Cài bằng:"
    x "           $PY -m venv .venv && . .venv/bin/activate"
    x "           pip install -r requirements-mo-hinh.txt --index-url https://download.pytorch.org/whl/cpu"
  fi
else
  if "$PY" -c 'import torch' >/dev/null 2>&1; then
    x "torch đã có, không cài lại."
    "$PY" mo-hinh/con_so_thuc.py --ra cong/con-so-thuc.json
  elif [ $CO_PIP -eq 1 ] && [ $CO_VENV -eq 1 ]; then
    x "Tạo venv .venv và cài torch bản CPU…"
    "$PY" -m venv .venv
    ./.venv/bin/pip install --quiet --upgrade pip
    ./.venv/bin/pip install --quiet -r requirements-mo-hinh.txt \
        --index-url https://download.pytorch.org/whl/cpu
    x "torch    : $(./.venv/bin/python -c 'import torch;print(torch.__version__)')"
    ./.venv/bin/python mo-hinh/con_so_thuc.py --ra cong/con-so-thuc.json
  else
    x "BỎ QUA phần mô hình: thiếu pip hoặc venv."
    x "Lõi vẫn chạy. Phần mô hình chỉ cần khi muốn đếm tham số hoặc huấn luyện."
  fi
fi

# ───────────────────────────────────────────────────────── 5. Trạng thái
tieu "5/5 · Trạng thái từng lĩnh vực"

"$PY" linh-vuc/do_trang_thai.py "${@:2}"
x ""
x "Chưa truyền --goc thì mọi lĩnh vực hiện 'chua-do'. Đó là câu trả lời đúng:"
x "chưa gọi thử lần nào thì không được nói 'chạy được'. Sau khi triển khai, chạy:"
x "    $PY linh-vuc/do_trang_thai.py --goc https://<tên-miền-của-bạn>"

tieu "XONG"
x "Đã chạy tới cuối mà không bước nào hỏng."
x "Phần nào CHƯA chạy được, đọc CAI-DAT.md — tệp ấy ghi theo kết quả đo, không theo mong đợi."
