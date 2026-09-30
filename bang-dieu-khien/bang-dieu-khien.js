/* Bảng điều khiển Open BDSG — dựng lưới lĩnh vực từ SỔ GHI và TRẠNG THÁI ĐO ĐƯỢC.
   Không con số nào, không nhãn trạng thái nào được ghi cứng trong tệp này. */
'use strict';

var NHAN = {
  'chay-duoc':   { lop: 'n-chay',    chu: 'chạy được' },
  'trang-trang': { lop: 'n-trang',   chu: 'trang trắng' },
  'mot-phan':    { lop: 'n-motphan', chu: 'một phần' },
  'hong':        { lop: 'n-hong',    chu: 'hỏng' },
  'chua-do':     { lop: 'n-chuado',  chu: 'chưa đo' }
};

function el(t, lop, chu) {
  var e = document.createElement(t);
  if (lop) e.className = lop;
  if (chu !== undefined) e.textContent = chu;
  return e;
}

function veO(lv, tt) {
  var mo = tt && tt.trang_thai === 'chay-duoc';
  var a = el('a', 'o');
  a.href = lv.duong_dan + '/';
  if (!mo) a.setAttribute('aria-disabled', 'true');

  var bt = el('div', 'bt', lv.bieu_tuong.chu);
  bt.style.background = lv.bieu_tuong.mau;
  a.appendChild(bt);
  a.appendChild(el('div', 'ten', lv.ten));

  var n = NHAN[(tt && tt.trang_thai) || 'chua-do'] || NHAN['chua-do'];
  var nhan = el('span', 'nhan ' + n.lop);
  nhan.appendChild(el('i'));
  nhan.appendChild(document.createTextNode(n.chu));
  a.appendChild(nhan);

  a.appendChild(el('div', 'tt', lv.tom_tat));
  if (tt && tt.canh_bao && tt.canh_bao.length) {
    a.appendChild(el('div', 'tt', '⚠ ' + tt.canh_bao[0]));
  }
  return a;
}

Promise.all([
  fetch('../cong/so-ghi-linh-vuc.json').then(function (r) { return r.json(); }),
  fetch('../cong/trang-thai-linh-vuc.json').then(function (r) { return r.json(); })
    .catch(function () { return { muc: [], do_luc: null, goc_da_goi: null }; })
]).then(function (kq) {
  var ds = kq[0], tt = kq[1];
  var theoMa = {};
  (tt.muc || []).forEach(function (m) { theoMa[m.ma] = m; });

  var noi = document.getElementById('noi-dung');
  noi.innerHTML = '';
  noi.appendChild(el('h2', null, 'Lĩnh vực (' + ds.length + ')'));
  var luoi = el('div', 'luoi');
  ds.forEach(function (lv) { luoi.appendChild(veO(lv, theoMa[lv.ma])); });
  noi.appendChild(luoi);

  var dem = {};
  ds.forEach(function (lv) {
    var t = (theoMa[lv.ma] && theoMa[lv.ma].trang_thai) || 'chua-do';
    dem[t] = (dem[t] || 0) + 1;
  });
  var tom = Object.keys(dem).sort().map(function (k) {
    return (NHAN[k] ? NHAN[k].chu : k) + ': ' + dem[k];
  }).join(' · ');

  document.getElementById('chan').textContent =
    'Sổ ghi: ' + ds.length + ' lĩnh vực, ' +
    ds.reduce(function (s, l) { return s + l.cong_cu.length; }, 0) + ' công cụ MCP đã khai. ' +
    'Trạng thái — ' + tom + '. ' +
    (tt.do_luc
      ? 'Đo lúc ' + tt.do_luc + (tt.goc_da_goi ? ' trên ' + tt.goc_da_goi : '') + '.'
      : 'Chưa chạy linh-vuc/do_trang_thai.py lần nào, nên mọi lĩnh vực hiện “chưa đo”.');
}).catch(function (e) {
  document.getElementById('noi-dung').textContent = 'Không nạp được sổ ghi: ' + e;
});
