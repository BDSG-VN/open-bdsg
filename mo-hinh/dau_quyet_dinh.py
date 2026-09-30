# -*- coding: utf-8 -*-
"""Đầu quyết định có kiểu — BDSG cho quyết định, không cho sinh văn.

===============================================================================
VÌ SAO CÓ TỆP NÀY
===============================================================================
Bản trọng số BDSG đã huấn luyện (26.878.464 tham số, 26/09/2026) học mục tiêu
**sinh văn**: đoán token kế tiếp. Với mục tiêu ấy, tỉ lệ tính-toán-tối-ưu
(Hoffmann và cộng sự 2022, arXiv:2203.15556) đòi ~20 token mỗi tham số, tức
**537.569.280 token**. Ngữ liệu thực có là **2.068.295 token** — thiếu **260 lần**.
Đó là lý do perplexity nhảy từ 19,9 (phần học) lên 102,5 (phần kiểm). Không có
mẹo kiến trúc nào bù được khoảng thiếu 260 lần dữ liệu cho mục tiêu sinh văn.

Tệp này đổi **mục tiêu**, không đổi **thân mô hình**: giữ nguyên embedding, các
`KhoiGiaiMa`, và RMSNorm cuối; thay đầu ra ngôn ngữ bằng các đầu phân loại có
kiểu. Ba lợi ích đo được, không phải phỏng đoán:

1. **Nhãn sinh được vô hạn.** Bộ luật tất định của BDSG
   (`LocalDecisionProvider`) trả quyết định kèm tên luật, đo được trung vị
   **20 ms** qua cổng HTTP nội bộ ngày 01/10/2026. Nhãn do luật sinh ra thì
   đúng theo định nghĩa, bằng tiếng Việt, và không giới hạn số lượng — nên bài
   toán "thiếu 260 lần" biến mất.
2. **Đầu ra rẻ.** Ba đầu (choice 8 lựa chọn · noul · score 5 mức) tốn **4.620**
   tham số trên thân 512 chiều — đếm thật bằng `parameters()`, không phải
   công thức. Bảng từ vựng 6.400 token của đầu ra ngôn ngữ
   không còn cần đến.
3. **Không sinh văn thì không bịa.** Đầu phân loại trả một trong N nhãn kèm
   xác suất; nó không thể phát minh ra một con số hay một cái tên không có
   trong tập nhãn. Đây là tính chất mà CLAUDE.md của dự án đòi ("không bịa số").

===============================================================================
HAI LỖI CỦA LAYA MÀ TỆP NÀY CHẶN NGAY TRONG MÃ
===============================================================================
Đo laya trên máy BDSG ngày 01/10/2026 (container `bdsg/thu-laya:1`, 6 lõi CPU)
phát hiện hai khiếm khuyết. Cả hai đều được chặn ở đây, không phải bằng tài
liệu mà bằng phép kiểm chạy được:

**(a) Nhiệt độ hiệu chuẩn ngoài khoảng.** laya tự in cảnh báo:
    "this checkpoint ships invalid temperatures or values outside [0.5, 5];
     using choice:11+=0.1005… -> 0.5. Treat confidence from the affected
     entries as uncalibrated."
Tức nó phát ra `confidence` mà chính nó nói là không tin được. Ở đây nhiệt độ
là tham số học được nhưng **bị kẹp cứng** vào [0,5 ; 5,0] trong `forward`, và
`kiem_hieu_chuan()` trả về danh sách đầu nào lệch. Trường
`hieu_chuan_dung` đi kèm **mọi** đáp án, nên người dùng không bao giờ nhận một
độ tin cậy mà không biết nó có hiệu chuẩn hay không.

**(b) Không nhận ra tiếng Việt.** Cả 4 tình huống tiếng Việt đều cho
`language: null`, `language_undecided: true`; laya rơi về checkpoint
`multilingual` như lưới an toàn, không phải vì hiểu tiếng Việt. Ở đây không có
bước đoán ngôn ngữ nào cả: tokenizer là bộ 6.400 token do BDSG luyện trên chính
ngữ liệu tiếng Việt của mình, nên không có gì để đoán sai.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

import torch
from torch import nn

from .cau_hinh import CauHinhBDSG
from .kien_truc import KhoiGiaiMa, RMSNorm, _dung_bang_rope

# Khoảng nhiệt độ hiệu chuẩn hợp lệ. Lấy đúng khoảng laya dùng, vì đây là
# khoảng mà phép chia logits/T còn giữ được thứ tự và không làm phân bố sụp về
# một điểm (T -> 0) hay phẳng hoàn toàn (T lớn).
NHIET_DO_MIN = 0.5
NHIET_DO_MAX = 5.0

LoaiDau = Literal["choice", "noul", "score"]


@dataclass
class KhaiDau:
    """Khai báo một câu hỏi mà mô hình phải trả lời.

    `ma` là mã câu hỏi, dùng làm khoá trong kết quả — trùng quy ước
    `ma_cau_hoi` mà API agent-brain đang trả về.
    """

    ma: str
    loai: LoaiDau
    #: Với `choice`: danh sách nhãn. Với `score`: nhãn của từng mức (0..n-1).
    #: Với `noul`: để trống — đầu ra là một xác suất trong [0, 1].
    nhan: List[str] = field(default_factory=list)

    def so_dau_ra(self) -> int:
        if self.loai == "noul":
            return 1
        if len(self.nhan) < 2:
            raise ValueError(
                f"câu hỏi '{self.ma}' loại {self.loai} cần ít nhất 2 nhãn, "
                f"đang có {len(self.nhan)}"
            )
        return len(self.nhan)


@dataclass
class DapAn:
    """Một đáp án có kiểu.

    `hieu_chuan_dung` LUÔN đi kèm. Đây là chỗ laya làm sai: nó phát
    `confidence` rồi cảnh báo ở stderr, nên người đọc kết quả không thấy.
    """

    ma: str
    loai: LoaiDau
    #: choice: nhãn được chọn · score: nhãn của mức gần kỳ vọng nhất · noul: None
    ket_qua: Optional[str]
    #: choice/score: phân bố xác suất theo nhãn · noul: {"co": p, "khong": 1-p}
    xac_suat: Dict[str, float]
    #: score: giá trị kỳ vọng Σ i·p_i · noul: xác suất · choice: None
    diem: Optional[float]
    do_tin_cay: float
    hieu_chuan_dung: bool
    nhiet_do: float


class BDSGChoQuyetDinh(nn.Module):
    """Thân giải mã của BDSG + các đầu phân loại có kiểu.

    Thân dùng lại nguyên `KhoiGiaiMa` và `RMSNorm` của `kien_truc.py`, nên một
    bản trọng số sinh văn đã huấn luyện có thể nạp vào đây làm điểm khởi đầu:
    chỉ các đầu là mới. Xem `nap_than_tu_ngon_ngu()`.
    """

    def __init__(self, cfg: CauHinhBDSG, khai: List[KhaiDau]) -> None:
        super().__init__()
        if not khai:
            raise ValueError("phải khai báo ít nhất một câu hỏi")
        ma_da_thay = set()
        for k in khai:
            if k.ma in ma_da_thay:
                raise ValueError(f"mã câu hỏi '{k.ma}' bị khai hai lần")
            ma_da_thay.add(k.ma)

        self.cfg = cfg
        self.khai = list(khai)

        # TEN PHAI TRUNG KHIT ban sinh van (`BDSGChoNgonNgu`): embed_tokens /
        # layers / norm. Dat ten khac se lam `nap_than_tu_ngon_ngu()` khop 0
        # tensor va IM LANG nap rong — thu nghiem bat duoc dung loi nay
        # 01/10/2026 truoc khi no vao kho.
        self.embed_tokens = nn.Embedding(cfg.vocab_size, cfg.hidden_size)
        self.layers = nn.ModuleList(
            KhoiGiaiMa(cfg, i) for i in range(cfg.num_hidden_layers)
        )
        self.norm = RMSNorm(cfg.hidden_size, eps=cfg.rms_norm_eps)
        # Bang RoPE: buffer khong ghi vao state_dict (persistent=False), dung
        # lai theo do dai can — cung cach ban sinh van lam.
        self.register_buffer("rope_cos", torch.empty(0), persistent=False)
        self.register_buffer("rope_sin", torch.empty(0), persistent=False)

        # Một Linear cho mỗi câu hỏi. KHÔNG dùng một Linear chung rồi cắt: cắt
        # làm gradient của các câu hỏi trộn vào nhau qua bias dùng chung, và
        # khi thêm/bớt một câu hỏi thì mọi trọng số cũ lệch chỉ số.
        self.dau = nn.ModuleDict(
            {k.ma: nn.Linear(cfg.hidden_size, k.so_dau_ra()) for k in self.khai}
        )
        # Nhiệt độ hiệu chuẩn: học được, một giá trị mỗi câu hỏi. Lưu dạng thô
        # rồi kẹp trong forward — kẹp bằng clamp chứ không bằng sigmoid tỉ lệ,
        # để một bản trọng số cũ có nhiệt độ ngoài khoảng vẫn chạy được và vẫn
        # bị `kiem_hieu_chuan()` chỉ ra.
        self.nhiet_do_tho = nn.ParameterDict(
            {k.ma: nn.Parameter(torch.ones(1)) for k in self.khai}
        )

        self.apply(self._khoi_tao)

    # ---------------------------------------------------------------- khởi tạo
    def _khoi_tao(self, mo_dun: nn.Module) -> None:
        if isinstance(mo_dun, nn.Linear):
            nn.init.normal_(mo_dun.weight, mean=0.0, std=self.cfg.initializer_range)
            if mo_dun.bias is not None:
                nn.init.zeros_(mo_dun.bias)
        elif isinstance(mo_dun, nn.Embedding):
            nn.init.normal_(mo_dun.weight, mean=0.0, std=self.cfg.initializer_range)

    # --------------------------------------------------------------- RoPE
    def _bao_dam_bang_rope(self, do_dai_can: int, device: torch.device) -> None:
        """Dung lai bang cos/sin khi bang hien co ngan hon do_dai_can.

        Giu bang o float32 ke ca sau `.half()`: goi `.half()` tren ca mo hinh
        se ep buffer sang fp16 va lam mat do chinh xac goc quay o vi tri lon.
        """
        if (
            self.rope_cos.numel() > 0
            and self.rope_cos.shape[0] >= do_dai_can
            and self.rope_cos.device == device
            and self.rope_cos.dtype == torch.float32
        ):
            return
        import math as _math
        do_dai = max(256, int(_math.ceil(do_dai_can / 256.0)) * 256)
        cos, sin = _dung_bang_rope(
            int(self.cfg.head_dim), do_dai, float(self.cfg.rope_theta), device
        )
        self.rope_cos = cos
        self.rope_sin = sin

    # ------------------------------------------------------------------- đếm
    def dem_tham_so(self, chi_hoc_duoc: bool = False) -> int:
        """Đếm THẬT từ `parameters()`, không theo công thức.

        Cùng quy ước với `BDSGChoNgonNgu.dem_tham_so` để hai con số so được
        với nhau.
        """
        return sum(
            p.numel()
            for p in self.parameters()
            if (p.requires_grad or not chi_hoc_duoc)
        )

    def dem_tham_so_dau(self) -> int:
        """Riêng phần đầu + nhiệt độ — phần mà thân sinh văn không có."""
        n = sum(p.numel() for p in self.dau.parameters())
        n += sum(p.numel() for p in self.nhiet_do_tho.parameters())
        return n

    # ------------------------------------------------------------ hiệu chuẩn
    def nhiet_do(self, ma: str) -> torch.Tensor:
        """Nhiệt độ ĐÃ kẹp. Mọi chỗ chia logits phải đi qua đây."""
        return self.nhiet_do_tho[ma].clamp(NHIET_DO_MIN, NHIET_DO_MAX)

    def kiem_hieu_chuan(self) -> List[Tuple[str, float]]:
        """Trả về [(mã câu hỏi, nhiệt độ thô)] cho mọi đầu lệch khỏi khoảng.

        Danh sách rỗng nghĩa là mọi độ tin cậy phát ra đều hiệu chuẩn được.
        Đây là phép kiểm mà laya thiếu: nó cảnh báo ở stderr rồi vẫn trả
        `confidence` như thường.
        """
        lech: List[Tuple[str, float]] = []
        for ma, p in self.nhiet_do_tho.items():
            t = float(p.detach().reshape(-1)[0])
            if not (NHIET_DO_MIN <= t <= NHIET_DO_MAX):
                lech.append((ma, t))
        return lech

    # -------------------------------------------------------------- lan truyền
    def than(
        self,
        ma_token: torch.Tensor,
        mat_na_dem: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Chạy thân, trả về vector một câu: (batch, hidden).

        Gộp theo **token cuối không phải đệm**. Thân là nhân quả, nên token
        cuối là token duy nhất nhìn thấy toàn bộ câu. Lấy trung bình cộng thay
        vào đó sẽ pha loãng phần cuối câu — chỗ mang ngân sách và thời hạn.
        """
        if ma_token.dim() != 2:
            raise ValueError(f"ma_token phải là (batch, do_dai), đang là {tuple(ma_token.shape)}")

        do_dai = int(ma_token.size(1))
        if do_dai > self.cfg.max_position_embeddings:
            raise ValueError(
                f"cau dai {do_dai} token vuot tran ngu canh "
                f"{self.cfg.max_position_embeddings}"
            )
        self._bao_dam_bang_rope(do_dai, ma_token.device)
        cos = self.rope_cos[:do_dai]
        sin = self.rope_sin[:do_dai]

        x = self.embed_tokens(ma_token)
        for lop in self.layers:
            ra = lop(x, cos, sin)
            x = ra[0] if isinstance(ra, tuple) else ra
        x = self.norm(x)

        if mat_na_dem is None:
            return x[:, -1, :]

        if mat_na_dem.shape != ma_token.shape:
            raise ValueError(
                f"mặt nạ {tuple(mat_na_dem.shape)} không khớp token {tuple(ma_token.shape)}"
            )
        # Chỉ số token cuối có mặt nạ = 1. Câu rỗng (mặt nạ toàn 0) lấy vị trí 0
        # thay vì -1, vì -1 sẽ lấy token đệm cuối cùng.
        so_that = mat_na_dem.long().sum(dim=1)
        vi_tri = (so_that - 1).clamp(min=0)
        return x[torch.arange(x.size(0), device=x.device), vi_tri, :]

    def forward(
        self,
        ma_token: torch.Tensor,
        mat_na_dem: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Trả logits ĐÃ chia nhiệt độ, theo từng mã câu hỏi."""
        v = self.than(ma_token, mat_na_dem)
        return {k.ma: self.dau[k.ma](v) / self.nhiet_do(k.ma) for k in self.khai}

    # ------------------------------------------------------------- suy diễn
    @torch.no_grad()
    def quyet_dinh(
        self,
        ma_token: torch.Tensor,
        mat_na_dem: Optional[torch.Tensor] = None,
    ) -> List[List[DapAn]]:
        """Một danh sách đáp án cho mỗi câu trong lô."""
        self.eval()
        logits = self.forward(ma_token, mat_na_dem)
        lech = dict(self.kiem_hieu_chuan())
        so_cau = ma_token.size(0)
        ket: List[List[DapAn]] = [[] for _ in range(so_cau)]

        for k in self.khai:
            lg = logits[k.ma]
            t = float(self.nhiet_do(k.ma).reshape(-1)[0])
            dung = k.ma not in lech

            if k.loai == "noul":
                p = torch.sigmoid(lg.reshape(-1))
                for i in range(so_cau):
                    pi = float(p[i])
                    ket[i].append(
                        DapAn(
                            ma=k.ma, loai="noul", ket_qua=None,
                            xac_suat={"co": pi, "khong": 1.0 - pi},
                            diem=pi,
                            # Xa 0,5 bao nhiêu thì chắc bấy nhiêu.
                            do_tin_cay=abs(pi - 0.5) * 2.0,
                            hieu_chuan_dung=dung, nhiet_do=t,
                        )
                    )
                continue

            p = torch.softmax(lg, dim=-1)
            for i in range(so_cau):
                pi = p[i]
                xs = {k.nhan[j]: float(pi[j]) for j in range(len(k.nhan))}
                if k.loai == "choice":
                    j = int(torch.argmax(pi))
                    ket[i].append(
                        DapAn(
                            ma=k.ma, loai="choice", ket_qua=k.nhan[j],
                            xac_suat=xs, diem=None,
                            do_tin_cay=float(pi[j]),
                            hieu_chuan_dung=dung, nhiet_do=t,
                        )
                    )
                else:  # score
                    muc = torch.arange(len(k.nhan), dtype=pi.dtype, device=pi.device)
                    ky_vong = float((pi * muc).sum())
                    gan = int(round(ky_vong))
                    gan = max(0, min(len(k.nhan) - 1, gan))
                    # Độ tin cậy của `score` KHÔNG phải xác suất mức cao nhất.
                    # Một phân bố dồn vào hai mức 0 và 4 có kỳ vọng 2 nhưng
                    # không hề "chắc mức 2". Dùng 1 - độ lệch chuẩn đã chuẩn hoá.
                    var = float((pi * (muc - ky_vong) ** 2).sum())
                    lech_max = (len(k.nhan) - 1) / 2.0
                    do_tin = 1.0 - min(1.0, (var ** 0.5) / lech_max) if lech_max > 0 else 1.0
                    ket[i].append(
                        DapAn(
                            ma=k.ma, loai="score", ket_qua=k.nhan[gan],
                            xac_suat=xs, diem=ky_vong,
                            do_tin_cay=do_tin,
                            hieu_chuan_dung=dung, nhiet_do=t,
                        )
                    )
        return ket

    # ---------------------------------------------------- nạp thân sinh văn
    def nap_than_tu_ngon_ngu(self, trang_thai: Dict[str, torch.Tensor]) -> Tuple[int, List[str]]:
        """Nạp thân từ một bản trọng số `BDSGChoNgonNgu`.

        Trả về (số tensor đã nạp, danh sách khoá bỏ qua). Các đầu KHÔNG được
        nạp — chúng là mới. Hàm này im lặng bỏ qua `dau_ngon_ngu`/`lm_head`
        thay vì nổ, nhưng nó BÁO LẠI danh sách bỏ qua để người gọi kiểm, chứ
        không nuốt.
        """
        cua_toi = self.state_dict()
        nap: Dict[str, torch.Tensor] = {}
        bo_qua: List[str] = []
        for k, v in trang_thai.items():
            if k in cua_toi and cua_toi[k].shape == v.shape:
                nap[k] = v
            else:
                bo_qua.append(k)
        cua_toi.update(nap)
        self.load_state_dict(cua_toi)
        return len(nap), bo_qua


def dung_mo_hinh_quyet_dinh(
    cfg: CauHinhBDSG,
    khai: Optional[List[KhaiDau]] = None,
) -> BDSGChoQuyetDinh:
    """Dựng mô hình với bộ câu hỏi mặc định của BDSG.

    Ba câu hỏi này là đúng ba câu thanh quyết định trên agent.bdsg.vn đang hỏi,
    nên nhãn huấn luyện lấy được ngay từ `LocalDecisionProvider` không cần
    thêm bước ánh xạ nào.
    """
    if khai is None:
        khai = [
            KhaiDau(
                ma="chang-uu-tien",
                loai="choice",
                nhan=["tu-van", "trien-khai", "kinh-doanh"],
            ),
            KhaiDau(ma="can-nguoi-duyet", loai="noul"),
            KhaiDau(
                ma="diem-kha-thi",
                loai="score",
                nhan=["rất thấp", "thấp", "vừa", "cao", "rất cao"],
            ),
        ]
    return BDSGChoQuyetDinh(cfg, khai)
