#!/usr/bin/env bash
# cong/chay-tat-ca.sh — chạy TẤT CẢ các cổng trước khi đẩy lên kho công khai.
#
# VÌ SAO KỊCH BẢN NÀY TỒN TẠI
#   Các cổng chạy riêng lẻ thì sớm muộn có cái bị quên. Ở đây có đúng một cửa ra, và cửa
#   ấy đóng nếu BẤT KỲ cổng nào hỏng. Số cổng khai ở CONG_MONG_DOI bên dưới, không khai ở
#   dòng chú thích này — một con số viết trong chú thích sẽ lạc hậu ngay lần thêm cổng sau.
#
# HAI QUYẾT ĐỊNH CÓ CHỦ Ý, GHI RA ĐỂ NGƯỜI SAU ĐỪNG "SỬA" NHẦM:
#
#   1. LUÔN chạy bài tự kiểm TRƯỚC khi quét thật, không phải chỉ khi được yêu cầu.
#      Một cổng luôn trả "sạch" thì nhìn y hệt một cổng hỏng. Trước khi tin câu "kho sạch",
#      phải bắt cổng chứng minh nó CẮN được chuỗi cố tình cài vào. Toàn bộ các bài tự kiểm
#      chạy hết dưới một giây — không có lý do gì để bỏ.
#
#   2. KHÔNG dùng `set -e`, và KHÔNG dùng `|| true` ở bất cứ đâu.
#      `set -e` sẽ thoát ngay ở cổng hỏng đầu tiên, giấu mất các cổng còn lại — người sửa
#      phải chạy lại nhiều lần để thấy hết. Còn `|| true` thì nuốt mã lỗi và biến cổng thành
#      đồ trang trí: nó vẫn chạy, vẫn in, và không bao giờ chặn được gì. Đây là họ lỗi
#      "hỏng mà không báo" đã gặp thật ở dự án này. Mã thoát được bắt tường minh từng cái.
#
#   3. Không dùng đường ống (pipe) để lấy mã thoát của cổng. Trong zsh, PIPESTATUS đánh
#      chỉ số từ 1 chứ không phải từ 0 như bash — đã đo sai vì chuyện này rồi. Chạy thẳng,
#      lấy $? ngay dòng sau, khỏi bàn.
#
# DÙNG:
#   cong/chay-tat-ca.sh                 # tự kiểm + quét toàn kho
#   cong/chay-tat-ca.sh --goc <thư mục> # quét một thư mục khác
#   cong/chay-tat-ca.sh --chi-tu-kiem   # chỉ chạy bài thử ngược của các cổng
#
# MÃ THOÁT: 0 = mọi cổng ĐẠT. 1 = có cổng HỎNG ⇒ KHÔNG ĐẨY LÊN.

set -u

# Bảng tổng kết viết bằng tiếng Việt, mà `printf %-22s` đệm theo BYTE chứ không theo ký tự:
# "ĐẠT" dài 3 ký tự nhưng 6 byte, nên mọi cột lệch đúng 3 ô. Đo thật ngày 25/09/2026 trên
# máy có LANG rỗng. Đặt locale UTF-8 thì ${#chuoi} mới đếm KÝ TỰ, rồi tự đệm bằng hàm o().
# Nếu máy không có locale ấy thì bảng lệch một chút — chấp nhận, KHÔNG được vì chuyện
# trình bày mà làm hỏng kịch bản.
if locale -a 2>/dev/null | grep -qx "en_US.UTF-8"; then
  export LC_ALL="en_US.UTF-8"
fi

o() {  # o <chuỗi> <bề rộng cột> — đệm phải theo số KÝ TỰ
  local chuoi="$1" be_rong="$2" thieu
  thieu=$(( be_rong - ${#chuoi} ))
  [ $thieu -lt 0 ] && thieu=0
  printf '%s%*s' "$chuoi" "$thieu" ""
}

THU_MUC_CONG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GOC_MAC_DINH="$(dirname "$THU_MUC_CONG")"
GOC="$GOC_MAC_DINH"
CHI_TU_KIEM=0

while [ $# -gt 0 ]; do
  case "$1" in
    --goc)
      if [ $# -lt 2 ]; then echo "HỎNG: --goc cần một đường dẫn." >&2; exit 1; fi
      GOC="$2"; shift 2 ;;
    --chi-tu-kiem) CHI_TU_KIEM=1; shift ;;
    -h|--help) sed -n '1,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "HỎNG: không hiểu tham số '$1'." >&2; exit 1 ;;
  esac
done

# ── Fail-closed 1: không có python3 thì KHÔNG được coi là sạch ────────────────
PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "HỎNG: không tìm thấy python3. Cổng không chạy được ⇒ KHÔNG kết luận kho sạch, và KHÔNG đẩy."
  exit 1
fi

# ── Danh sách cổng, khai tường minh ──────────────────────────────────────────
# Cố ý KHÔNG dùng glob *.py. Glob im lặng bỏ qua cổng bị xoá: kho mất một cổng mà bảng
# tổng kết vẫn "toàn ĐẠT". Khai tên ra thì thiếu tệp là HỎNG, thấy ngay.
CONG_MONG_DOI=(khong-bi-mat.py khong-ha-tang.py khong-du-lieu-cam.py khong-lo-hong.py \
                khong-danh-tinh.py khong-tham-chieu-ngoai.py khong-cua-hau.py)
# khong-danh-tinh.py thêm 26/09/2026: bốn cổng trên ĐẠT toàn kho, rồi một lượt soát
# TAY độc lập vẫn tìm ra họ tên thật của chủ dự án. Thứ soát tay tìm được phải trở
# thành cổng, nếu không lần sau nó lọt.
#
# khong-tham-chieu-ngoai.py thêm 26/09/2026, và nó chặn một họ lỗi KHÁC hẳn năm cổng trên:
# năm cổng kia chặn thứ LỌT RA (bí mật, hạ tầng, dữ liệu người khác, đường khai thác, danh
# tính). Cổng này chặn một LỜI KHAI SAI ở lại trong kho — tài liệu nói sai về nguồn gốc của
# chính mã trong kho, và nói sai về phạm vi ngôn ngữ của dự án. Không có gì rò rỉ, nhưng
# người đọc bị dẫn sai, mà kho này thì tồn tại để nói đúng chỗ khó.
#
# khong-cua-hau.py thêm 26/09/2026, và nó chặn họ lỗi THỨ BA: một CỬA HẬU ở lại trong kho.
# Số đo làm nó ra đời: máy chủ MCP đang chạy của BDSG (nằm ngoài kho này) lấy SSH vào máy
# chủ sản phẩm làm phương tiện, với một khoá root ghi cứng trong mã — mỗi công cụ là một
# lệnh tuỳ ý trên production. Kho này đang thành một hệ điều hành cho doanh nghiệp, nên
# khuôn ấy không được phép quay về qua một lần sao chép mã. Khác hai họ trên ở chỗ: không
# có gì rò ra, không có lời khai nào sai — nhưng nếu mã ấy được chạy thì thiệt hại là toàn
# quyền trên máy chủ, chứ không phải một dòng tài liệu đọc nhầm.

echo "════════════════════════════════════════════════════════════════════════════"
echo " CỔNG KIỂM TRƯỚC KHI ĐẨY — Open BDSG"
echo " Gốc quét : $GOC"
echo " Python   : $($PYTHON --version 2>&1)"
echo "════════════════════════════════════════════════════════════════════════════"

if [ ! -d "$GOC" ]; then
  echo "HỎNG: không thấy thư mục gốc '$GOC'."
  exit 1
fi

# ── Fail-closed 2: cổng chưa được nối vào thì cũng là hỏng ────────────────────
# Một tệp cổng nằm trong cong/ mà không có trong CONG_MONG_DOI sẽ KHÔNG BAO GIỜ chạy.
# Người viết nó tưởng đã bảo vệ được kho. Đó đúng là kiểu hỏng-mà-không-báo tệ nhất.
CONG_LAC=""
for TEP in "$THU_MUC_CONG"/*.py; do
  [ -e "$TEP" ] || continue
  TEN_TEP="$(basename "$TEP")"
  TRONG_DANH_SACH=0
  for MONG_DOI in "${CONG_MONG_DOI[@]}"; do
    if [ "$TEN_TEP" = "$MONG_DOI" ]; then TRONG_DANH_SACH=1; break; fi
  done
  if [ $TRONG_DANH_SACH -eq 0 ]; then CONG_LAC="$CONG_LAC $TEN_TEP"; fi
done

TEN_CONG=()
KQ_TU_KIEM=()
KQ_QUET=()
SO_HONG=0

for TEP_CONG in "${CONG_MONG_DOI[@]}"; do
  TEN="${TEP_CONG%.py}"
  DUONG_DAN="$THU_MUC_CONG/$TEP_CONG"
  TEN_CONG+=("$TEN")

  if [ ! -f "$DUONG_DAN" ]; then
    echo ""
    echo "──── $TEN ────"
    echo "HỎNG: thiếu tệp cổng $DUONG_DAN. Cổng vắng mặt KHÔNG phải là cổng đã đạt."
    KQ_TU_KIEM+=("THIẾU")
    KQ_QUET+=("THIẾU")
    SO_HONG=$((SO_HONG + 1))
    continue
  fi

  # Bước 1: bài thử ngược — cổng phải chứng minh nó cắn.
  echo ""
  echo "──── $TEN · tự kiểm ────"
  "$PYTHON" "$DUONG_DAN" --tu-kiem
  MA_TU_KIEM=$?
  if [ $MA_TU_KIEM -eq 0 ]; then KQ_TU_KIEM+=("ĐẠT"); else KQ_TU_KIEM+=("HỎNG($MA_TU_KIEM)"); fi

  if [ $MA_TU_KIEM -ne 0 ]; then
    # Cổng không tự chứng minh được thì kết quả quét của nó vô nghĩa: "sạch" hay "bẩn"
    # đều không đáng tin. Không chạy quét, và tính là hỏng.
    echo "    ⇒ BỎ bước quét: cổng chưa chứng minh được nó cắn thì kết quả quét không đáng tin."
    KQ_QUET+=("KHÔNG CHẠY")
    SO_HONG=$((SO_HONG + 1))
    continue
  fi

  if [ $CHI_TU_KIEM -eq 1 ]; then
    KQ_QUET+=("bỏ qua")
    continue
  fi

  # Bước 2: quét thật.
  echo ""
  echo "──── $TEN · quét kho ────"
  "$PYTHON" "$DUONG_DAN" --goc "$GOC"
  MA_QUET=$?
  if [ $MA_QUET -eq 0 ]; then
    KQ_QUET+=("ĐẠT")
  else
    KQ_QUET+=("HỎNG($MA_QUET)")
    SO_HONG=$((SO_HONG + 1))
  fi
done

# ── Bảng tổng kết ────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
printf " %s%s%s\n" "$(o "CỔNG" 26)" "$(o "TỰ KIỂM" 14)" "$(o "QUÉT KHO" 14)"
echo "────────────────────────────────────────────────────────────────────────────"
CHI_SO=0
while [ $CHI_SO -lt ${#TEN_CONG[@]} ]; do
  printf " %s%s%s\n" \
    "$(o "${TEN_CONG[$CHI_SO]}" 26)" "$(o "${KQ_TU_KIEM[$CHI_SO]}" 14)" "$(o "${KQ_QUET[$CHI_SO]}" 14)"
  CHI_SO=$((CHI_SO + 1))
done
echo "────────────────────────────────────────────────────────────────────────────"

if [ -n "$CONG_LAC" ]; then
  echo " HỎNG: có tệp cổng KHÔNG được nối vào kịch bản:$CONG_LAC"
  echo "       Cổng không được gọi thì không bảo vệ gì cả. Thêm tên vào CONG_MONG_DOI."
  SO_HONG=$((SO_HONG + 1))
fi

echo ""
echo " Cổng này chỉ chặn được thứ nó biết cách nhìn. Nó KHÔNG đọc ảnh chụp màn hình,"
echo " KHÔNG kiểm IPv6, KHÔNG mở tệp nhị phân và trọng số mô hình. Mọi cổng ĐẠT nghĩa là"
echo " 'không tìm thấy thứ đã biết cách tìm', không phải 'kho đã an toàn'."

if [ $SO_HONG -gt 0 ]; then
  echo ""
  echo " KẾT LUẬN: HỎNG ở $SO_HONG chỗ ⇒ KHÔNG ĐẨY LÊN."
  echo " Nhắc lại: đẩy lên là MỘT CHIỀU. GitHub, các bản fork và bộ nhớ đệm máy tìm kiếm"
  echo " đều giữ lại. Sửa trước khi đẩy tốn vài phút; sau khi đẩy thì không sửa được nữa."
  echo "════════════════════════════════════════════════════════════════════════════"
  exit 1
fi

echo ""
if [ $CHI_TU_KIEM -eq 1 ]; then
  echo " KẾT LUẬN: mọi cổng đều CHỨNG MINH ĐƯỢC là chúng cắn. Chưa quét kho (--chi-tu-kiem)."
else
  echo " KẾT LUẬN: mọi cổng ĐẠT trong phạm vi đã khai."
fi
echo "════════════════════════════════════════════════════════════════════════════"
exit 0
