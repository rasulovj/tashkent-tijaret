/* Orijinal Jinja şablonlarının (templates/bulten.html, announce.html, report.html) tarayıcı karşılıkları
 * ve PDF/PNG üretimi (html2canvas + jsPDF). Çıktılar Mac'teki panelinkiyle aynı düzendedir. */
(function () {
"use strict";
const { H } = TT;
let LBL = null;  // api/_labels.json: B (bülten), A/K/T/F (duyuru)

/* ------------------------------------------------------------------ küçük yardımcılar */
const fmtNum = (v, dec) => {  // Python: f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
  const s = Math.abs(v).toFixed(dec), [i, f] = s.split(".");
  return (v < 0 ? "-" : "") + i.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (f ? "," + f : "");
};
const fmtDot = (v, dec = 1) => fmtNum(v, dec).replace(/ /g, ".");  // rapor grafikleri: 1.234,5

function qrSvg(url) {
  if (!window.qrcode || !url) return "";
  const q = qrcode(0, "M"); q.addData(String(url)); q.make();
  const n = q.getModuleCount(), b = 1;
  let d = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c)) d += `M${c + b},${r + b}h1v1h-1z`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n + 2 * b} ${n + 2 * b}" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="${d}" fill="#000"/></svg>`;
}

function lineSvg(points, title, w = 520, h = 150, color = "#8B1A1A", decimals = 0) {
  if (!points || points.length < 2) return "";
  const pl = 46, pr = 12, pt = 26, pb = 22;
  const vals = points.map(p => p[1]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const padv = (hi - lo) * 0.15 || 1; lo -= padv; hi += padv;
  const x = i => pl + i * (w - pl - pr) / (points.length - 1);
  const y = v => pt + (hi - v) * (h - pt - pb) / (hi - lo);
  const f = v => fmtNum(v, decimals);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  let grid = "";
  for (let k = 0; k < 3; k++) {
    const gv = lo + (hi - lo) * (k + 0.5) / 3;
    grid += `<line x1="${pl}" x2="${w - pr}" y1="${y(gv).toFixed(1)}" y2="${y(gv).toFixed(1)}" stroke="#ddd" stroke-width="0.6"/><text x="${pl - 4}" y="${(y(gv) + 3).toFixed(1)}" text-anchor="end">${f(gv)}</text>`;
  }
  const d0 = points[0][0], d1 = points[points.length - 1][0], last = points[points.length - 1][1], li = points.length - 1;
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" class="chart">
<style>text{font:9px Helvetica,Arial,sans-serif;fill:#555} .t{font-weight:bold;fill:#222;font-size:10.5px}</style>
<text x="${pl}" y="13" class="t">${H(title)}</text>${grid}
<path d="${path}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round"/>
<circle cx="${x(li).toFixed(1)}" cy="${y(last).toFixed(1)}" r="2.6" fill="${color}"/>
<text x="${(x(li) - 4).toFixed(1)}" y="${(y(last) - 6).toFixed(1)}" text-anchor="end" fill="${color}">${f(last)}</text>
<text x="${pl}" y="${h - 6}">${d0.slice(8, 10)}.${d0.slice(5, 7)}</text>
<text x="${w - pr}" y="${h - 6}" text-anchor="end">${d1.slice(8, 10)}.${d1.slice(5, 7)}</text>
</svg>`;
}

/* ------------------------------------------------------------------ bülten (templates/bulten.html) */
function indicators(L, rates) {
  if (!rates || !rates.today || !rates.today.length) return [[], []];
  const order = { USD: 0, EUR: 1, RUB: 2, TRY: 3 };
  const rs = rates.today.map(r => ({ ...r, rate_fmt: fmtNum(r.rate, r.rate < 1000 ? 2 : 0), diff_fmt: fmtNum(Math.abs(r.diff), 2) }))
    .sort((a, b) => order[a.ccy] - order[b.ccy]);
  return [rs, [lineSvg(rates.USD, L.chart_usd), lineSvg(rates.TRY, L.chart_try, 520, 150, "#C0392B", 2)]];
}

const BULLETIN_CSS = L => `
  :root { --red: #8B1A1A; --orange: #C0392B; --box: #F8D9CC; }
  body { font: 11.3pt/1.42 "Times New Roman", Times, serif; color: #111; margin: 0; }
  header { display: flex; justify-content: space-between; align-items: flex-start; }
  .office { flex: 1; color: var(--red); font: bold italic 15pt Georgia, "Times New Roman", serif; line-height: 1.25; }
  .addr { flex: none; white-space: nowrap; text-align: right; font-size: 9pt; line-height: 1.35; margin-top: 26px; }
  .date { color: var(--red); font: bold italic 9.5pt Georgia, serif; margin: 6px 0 10px; }
  .headlines { border: 1px solid #c9a99b; margin-bottom: 14px; break-inside: avoid; }
  .headlines h2 { background: var(--box); color: var(--red); margin: 0; padding: 3px; text-align: center;
                  font: bold 12pt Calibri, "Segoe UI", Helvetica, sans-serif; }
  .headlines ul { list-style: none; margin: 0; padding: 4px 6px; }
  .headlines li { color: var(--orange); font: italic 10.3pt/1.32 Calibri, "Segoe UI", Helvetica, sans-serif; }
  .headlines li::before { content: "- "; }
  .indicators { border: 1px solid #c9a99b; margin-bottom: 16px; break-inside: avoid; }
  .indicators h3 { background: var(--box); color: var(--red); margin: 0; padding: 3px;
                   text-align: center; font: bold 10.5pt Calibri, Helvetica, sans-serif; }
  .tiles { display: flex; gap: 0; border-bottom: 1px solid #eee; }
  .tile { flex: 1; text-align: center; padding: 5px 2px; font-family: Helvetica, Arial, sans-serif; }
  .tile + .tile { border-left: 1px solid #eee; }
  .tile .c { font-size: 8pt; color: #666; }
  .tile .v { font-size: 12pt; font-weight: bold; }
  .tile .d { font-size: 7.5pt; }
  .up { color: #1e7a3c; } .down { color: #b3261e; }
  .charts { display: flex; padding: 4px 4px 0; }
  .charts > div { flex: 1; }
  .chart { width: 100%; height: auto; }
  .src-note { font: 7pt Helvetica, sans-serif; color: #777; padding: 0 8px 4px; }
  article { text-align: justify; margin-bottom: 12px; }
  article p { margin: 0 0 4px; text-indent: 1.25em; }
  article p:first-of-type { text-indent: 0; }
  article .hd { font-weight: bold; }
  article .src { font-style: italic; }
  article .src a { color: inherit; text-decoration: none; }
  article { overflow: hidden; }
  figure.photo { float: right; width: 40%; margin: 2px 0 6px 5mm; break-inside: avoid; }
  figure.photo img { width: 100%; max-height: 52mm; object-fit: cover; border-radius: 3px; border: 0; max-width: none; }
  figure.photo figcaption { font: italic 7.5pt Helvetica, Arial, sans-serif; color: #777; text-align: right; margin-top: 1px; }
  .videos { clear: both; display: flex; gap: 6mm; flex-wrap: wrap; margin: 2mm 0 1mm; }
  .vid { display: flex; gap: 3mm; align-items: center; text-decoration: none; color: #222; border: 1px solid #e2d6d0; border-radius: 4px; padding: 2mm 3mm 2mm 2mm; background: #fbf7f5; }
  .vid .qr svg { width: 17mm; height: 17mm; display: block; }
  .vid b { color: #8B1A1A; font: bold 9.5pt Helvetica, Arial, sans-serif; }
  .vid small { font: 7.5pt Helvetica, Arial, sans-serif; color: #666; }
  figure { margin: 8px auto 4px; text-align: center; break-inside: avoid; }
  figure img { max-width: 78%; max-height: 95mm; border: 1px solid #e2d6d0; }
  figcaption { font: italic 9pt Georgia, serif; color: #555; margin-top: 3px; }
  .warn { background: #fff3b0; outline: 1px dashed #d4a000; }`;

function bulletinHtml(drafts, issueDate, lang, review, rates) {
  const L = LBL.B[lang];
  const items = drafts.items;
  const [rs, charts] = indicators(L, rates);
  const img = f => TT.fileUrl("img:" + f);
  const art = (it, n) => {
    const paras = it.paragraphs.length ? it.paragraphs : [""];
    return `<article${review && (it.warnings || []).length ? ` class="warn" title="${H(it.warnings.join("; "))}"` : ""}>
  ${it.photo && it.photo.show && (it.photo.file || it.photo.src) ? `<figure class="photo"><img src="${H(it.photo.file ? img(it.photo.file) : it.photo.src)}" alt=""><figcaption>${H(L.photo)}: ${H(it.photo.credit)}</figcaption></figure>` : ""}
  ${paras.map((p, i) => `<p>${i === 0 ? `<b>${n} – </b><span class="hd">${H(it.headline)}</span><br>` : ""}${H(p)}${i === paras.length - 1 ? ` <span class="src">(${it.sources.map(s => `<a href="${H(s.url)}">${H(s.name)}</a>`).join(", ")})</span>` : ""}</p>`).join("\n  ")}
  ${it.videos && it.videos.length ? `<div class="videos">${it.videos.filter(v => v.url).map(v => `<a class="vid" href="${H(v.url)}"><span class="qr">${qrSvg(v.url)}</span><span><b>▶ ${H(v.title || L.video)}</b><br><small>${H(v.url)}</small></span></a>`).join("")}</div>` : ""}
  ${it.image ? `<figure><img src="${H(img(it.image))}" alt="">${it.image_caption ? `<figcaption>${H(it.image_caption)}</figcaption>` : ""}</figure>` : ""}
</article>`;
  };
  return `<!doctype html>
<html lang="${lang}"><head><meta charset="utf-8"><title>${H(L.doc_title)} – ${H(issueDate)}</title>
<style>${BULLETIN_CSS(L)}</style></head><body>
<header><div class="office">${H(L.office_1)}<br>${H(L.office_2)}</div><div class="addr">${L.address_html}</div></header>
<div class="date">${H(issueDate)}</div>
<section class="headlines"><h2>${H(L.headlines_title)}</h2><ul>${items.map(it => `<li>${H(it.headline)}</li>`).join("")}</ul></section>
${rs.length ? `<section class="indicators"><h3>${H(L.indicators_title)}</h3>
  <div class="tiles">${rs.map(r => `<div class="tile"><div class="c">1 ${r.ccy} / UZS</div><div class="v">${r.rate_fmt}</div>
    <div class="d ${r.diff > 0 ? "up" : "down"}">${r.diff > 0 ? "▲" : "▼"} ${r.diff_fmt}</div></div>`).join("")}</div>
  <div class="charts">${charts.map(c => `<div>${c}</div>`).join("")}</div>
  <div class="src-note">${H(L.rates_source)} (${H(rs[0].date)})</div></section>` : ""}
${items.map((it, i) => art(it, i + 1)).join("\n")}
</body></html>`;
}

/* ------------------------------------------------------------------ duyuru (templates/announce.html) */
const MONTHS_OK = s => /^\d{4}-\d{2}-\d{2}$/.test(s || "");
function parseDate(s) { if (!MONTHS_OK(s)) return null; const [y, m, d] = s.split("-").map(Number); return { y, m, d, iso: s }; }

function annHtml(a, fmt, photoUrl) {
  const [W, Hh] = LBL.F[fmt];
  const lang = a.lang || "tr", L = LBL.A[lang] || LBL.A.tr;
  const kind = LBL.K[a.kind] || LBL.K.duyuru;
  const K = { label: kind[lang] || kind.tr, color: kind.color };
  const T = LBL.T[a.theme || "bordo"] || LBL.T.bordo;
  const d1 = parseDate(a.date), d2 = parseDate(a.date_end);
  let dd = null;
  if (d1) dd = {
    day: !d2 || d2.iso === d1.iso ? d1.d : d2.m === d1.m ? `${d1.d}–${d2.d}` : d1.d,
    month: L.months[d1.m - 1], year: d1.y, end: d2 && d2.m !== d1.m ? `${d2.d} ${L.months[d2.m - 1]}` : "" };
  const dl = parseDate(a.deadline);
  const deadline = dl ? `${dl.d} ${L.months[dl.m - 1]} ${dl.y}` : a.deadline;
  const photo = a.photo ? photoUrl : null;
  let [photo_h, body_top, title_size, show_text] = { kare: [35, 44, 4.8, !photo], dikey: [36, 44, 5.4, true], yatay: [0, 13, 5.0, !photo], afis: [32, 41, 5.0, true] }[fmt];
  if (!photo && fmt !== "yatay") body_top = 12;
  if ((a.title || "").length > 70) title_size *= 0.8;
  show_text = show_text && !!a.text;
  const U = Math.min(W, Hh) / 100;
  const f = fmt === "yatay" ? "wide" : fmt === "afis" ? "poster" : fmt;
  const cel = a.kind === "kutlama" || a.kind === "anma";
  return `<!doctype html>
<html lang="${H(lang)}"><head><meta charset="utf-8"><style>
  @page { size: ${W}px ${Hh}px; margin: 0; }
  * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  html, body { margin: 0; width: ${W}px; height: ${Hh}px; overflow: hidden; }
  body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; background: ${T.bg}; color: ${T.ink}; position: relative; }
  :root { --u: ${U}px; }
  .band { position: absolute; left: 0; right: 0; top: 0; height: calc(var(--u) * 7.5); background: ${T.primary}; color: #fff;
          display: flex; align-items: center; padding: 0 calc(var(--u) * 5); font: bold italic calc(var(--u) * 2.4) Georgia, serif; letter-spacing: .03em; z-index: 3; }
  .band .r { margin-left: auto; font: 600 calc(var(--u) * 2) "Helvetica Neue", Arial; font-style: normal; opacity: .9; }
  .photo { position: absolute; left: 0; right: 0; top: calc(var(--u) * 7.5); height: ${photo_h}%; background: ${T.soft} center/cover no-repeat;
           ${photo ? `background-image: url('${photo}');` : ""} }
  .photo::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 45%, ${T.bg} 100%); }
  .body { position: absolute; left: calc(var(--u) * 5); right: calc(var(--u) * 5); top: ${body_top}%; bottom: calc(var(--u) * 9); display: flex; flex-direction: column; z-index: 2; }
  .chip { align-self: flex-start; background: ${K.color}; color: #fff; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
          font-size: calc(var(--u) * 2.1); padding: calc(var(--u) * .8) calc(var(--u) * 2); border-radius: calc(var(--u) * 3); margin-bottom: calc(var(--u) * 2); }
  .chip small { font-weight: 600; opacity: .85; margin-left: calc(var(--u) * 1); letter-spacing: .04em; }
  h1 { font: bold calc(var(--u) * ${title_size}) / 1.12 Georgia, "Times New Roman", serif; margin: 0 0 calc(var(--u) * 1.6); color: ${T.ink}; }
  .sub { font-size: calc(var(--u) * 2.9); line-height: 1.4; color: ${T.muted}; margin: 0 0 calc(var(--u) * 2.4); }
  .text { font-size: calc(var(--u) * 2.3); line-height: 1.5; color: ${T.ink}; margin: 0 0 calc(var(--u) * 2.4); white-space: pre-line; }
  .facts { display: grid; grid-template-columns: auto 1fr; gap: calc(var(--u) * 1.2) calc(var(--u) * 2.4); align-items: center; margin-top: auto; }
  .date { grid-row: span 3; background: ${T.primary}; color: #fff; border-radius: calc(var(--u) * 1.6); text-align: center; padding: calc(var(--u) * 1.4) calc(var(--u) * 2.4); min-width: calc(var(--u) * 15); }
  .date .d { font: 800 calc(var(--u) * 7) / 1 "Helvetica Neue", Arial; }
  .date .m { font: 700 calc(var(--u) * 2.2) "Helvetica Neue", Arial; text-transform: uppercase; letter-spacing: .08em; margin-top: calc(var(--u) * .6); }
  .date .y { font-size: calc(var(--u) * 1.8); opacity: .85; }
  .f { font-size: calc(var(--u) * 2.5); display: flex; gap: calc(var(--u) * 1.2); align-items: baseline; }
  .f b { color: ${T.primary}; min-width: calc(var(--u) * 3); }
  .deadline { display: inline-block; margin-top: calc(var(--u) * 1.6); background: ${T.accent}; color: #fff; font-weight: 700; font-size: calc(var(--u) * 2.2);
              padding: calc(var(--u) * .7) calc(var(--u) * 1.8); border-radius: calc(var(--u) * .8); }
  .qr { position: absolute; right: calc(var(--u) * 5); bottom: calc(var(--u) * 9.5); text-align: center; z-index: 3; }
  .qr svg { width: calc(var(--u) * 15); height: calc(var(--u) * 15); background: #fff; padding: calc(var(--u) * .8); border-radius: calc(var(--u) * 1.2); display: block; box-shadow: 0 2px 10px rgba(0,0,0,.12); }
  .qr span { display: block; font-size: calc(var(--u) * 1.6); color: ${T.muted}; margin-top: calc(var(--u) * .6); }
  .foot { position: absolute; left: 0; right: 0; bottom: 0; height: calc(var(--u) * 7); background: ${T.foot}; color: ${T.footInk};
          display: flex; align-items: center; padding: 0 calc(var(--u) * 5); font-size: calc(var(--u) * 1.9); gap: calc(var(--u) * 3); z-index: 3; }
  .foot .bar { width: calc(var(--u) * 6); height: calc(var(--u) * .7); background: ${T.accent}; border-radius: 9px; }
  .foot .r { margin-left: auto; }
  .cel { position: absolute; left: calc(var(--u) * 7); right: calc(var(--u) * 7); top: ${photo ? body_top + "%" : "calc(var(--u) * 9)"}; bottom: calc(var(--u) * 9);
         display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; z-index: 2; }
  .cel .cdate { font: 700 calc(var(--u) * 3) "Helvetica Neue", Arial; letter-spacing: .14em; text-transform: uppercase; color: ${T.primary}; margin-bottom: calc(var(--u) * 1.6); }
  .cel .cdate span { font-size: calc(var(--u) * 9); letter-spacing: 0; display: block; line-height: 1; margin-bottom: calc(var(--u) * .6); }
  .cel h1 { font-size: calc(var(--u) * ${title_size * 1.05}); }
  .cel .rule { width: calc(var(--u) * 14); height: calc(var(--u) * .6); background: ${T.accent}; border-radius: 9px; margin: calc(var(--u) * 1.6) 0 calc(var(--u) * 2.2); }
  .cel .greet { font: 600 calc(var(--u) * 3.4) / 1.35 Georgia, serif; color: ${T.ink}; margin: 0 0 calc(var(--u) * 1.8); }
  .cel .ctext { font-size: calc(var(--u) * 2.4); line-height: 1.5; color: ${T.muted}; margin: 0; }
  .cel.anma .greet { font-style: italic; font-weight: 400; }
  body.cel-bg { background: radial-gradient(circle at 50% 42%, ${T.soft} 0%, ${T.bg} 62%); }
  .cel::before, .cel::after { content: ""; position: absolute; left: 50%; transform: translateX(-50%); width: 72%; height: 1px; background: ${T.accent}; opacity: .35; }
  .cel::before { top: 0; } .cel::after { bottom: 0; }
  .cel.anma .cdate { color: ${T.ink}; }
  .wide .cel { right: 46%; }
  .wide.nophoto .cel { right: calc(var(--u) * 7); }
  .wide .photo { left: 56%; top: calc(var(--u) * 7.5); bottom: calc(var(--u) * 7); height: auto; }
  .wide .photo::after { background: linear-gradient(90deg, ${T.bg} 0%, rgba(0,0,0,0) 25%); }
  .wide .body { right: 46%; top: 13%; }
  .wide.nophoto .body { right: calc(var(--u) * 24); }
  .poster .text { font-size: calc(var(--u) * 2.2); }
  .poster .facts { margin-top: calc(var(--u) * 2); }
</style></head>
<body class="${f}${photo ? "" : " nophoto"}${cel && !photo ? " cel-bg" : ""}">
<div class="band">${H(L.office)}<span class="r">${H(K.label)}</span></div>
${photo || (f !== "wide" && !cel) ? '<div class="photo"></div>' : ""}
${cel ? `<div class="cel ${a.kind}">
  ${dd ? `<div class="cdate"><span>${dd.day}</span> ${H(dd.month)}</div>` : ""}
  <h1>${H(a.title || L.placeholder)}</h1>
  <div class="rule"></div>
  ${a.subtitle ? `<p class="greet">${H(a.subtitle)}</p>` : ""}
  ${a.text ? `<p class="ctext">${H(a.text)}</p>` : ""}
</div>` : `<div class="body">
  <span class="chip">${H(K.label)}${a.tag ? `<small>· ${H(a.tag)}</small>` : ""}</span>
  <h1>${H(a.title || L.placeholder)}</h1>
  ${a.subtitle ? `<p class="sub">${H(a.subtitle)}</p>` : ""}
  ${show_text ? `<p class="text">${H(a.text)}</p>` : ""}
  <div class="facts">
    ${dd ? `<div class="date"><div class="d">${dd.day}</div><div class="m">${H(dd.month)}</div><div class="y">${dd.year}${dd.end ? " – " + H(dd.end) : ""}</div></div>` : ""}
    ${a.time ? `<div class="f"><b>⏱</b>${H(a.time)}</div>` : ""}
    ${a.place ? `<div class="f"><b>⌖</b>${H(a.place)}</div>` : ""}
    ${a.contact ? `<div class="f"><b>✉</b>${H(a.contact)}</div>` : ""}
  </div>
  ${a.deadline ? `<div><span class="deadline">${H(L.deadline)}: ${H(deadline)}</span></div>` : ""}
</div>`}
${a.link && !cel ? `<div class="qr">${qrSvg(a.link)}<span>${H(L.scan)}</span></div>` : ""}
<div class="foot"><span class="bar"></span>${H(L.office_full)}<span class="r">${H(L.site)}</span></div>
</body></html>`;
}

function annCaption(a) {
  const L = LBL.A[a.lang || "tr"] || LBL.A.tr;
  const icon = { etkinlik: "📅", duyuru: "📢", ilan: "📌", haber: "📰", kutlama: "🇹🇷", anma: "🕊" }[a.kind] || "📢";
  if (a.kind === "kutlama" || a.kind === "anma") {
    const body = [`${icon} ${(a.title || "").trim()}`, ""].concat([a.subtitle, a.text].filter(Boolean).map(x => x.trim()));
    return body.concat(["", L.office_full]).join("\n").trim().slice(0, 1024);
  }
  const lines = [`${icon} ${(a.title || "").trim()}`];
  if (a.subtitle) lines.push(a.subtitle.trim());
  lines.push("");
  const d1 = parseDate(a.date);
  if (d1) {
    let when = `${d1.d} ${L.months[d1.m - 1]} ${d1.y}`;
    const d2 = parseDate(a.date_end);
    if (d2 && d2.iso !== d1.iso) when += ` – ${d2.d} ${L.months[d2.m - 1]} ${d2.y}`;
    lines.push(`🗓 ${when}` + (a.time ? ` · ${a.time}` : ""));
  }
  if (a.place) lines.push(`📍 ${a.place}`);
  const dl = parseDate(a.deadline);
  if (dl) lines.push(`⏳ ${L.deadline}: ${dl.d} ${L.months[dl.m - 1]} ${dl.y}`);
  if (a.text) lines.push("", a.text.trim());
  if (a.contact) lines.push("", `✉ ${a.contact}`);
  if (a.link) lines.push(`🔗 ${a.link}`);
  lines.push("", L.office_full);
  return lines.join("\n").trim().slice(0, 1024);
}

/* ------------------------------------------------------------------ rapor grafikleri (bot/reports/svg.py) */
const RED = "#8B1A1A", ORANGE = "#D9822B", SOFT = "#E9C9BE", GRID = "#e4dfda", INK = "#222", MUTED = "#666";
const FONT = "font-family:Helvetica,Arial,sans-serif";
function hbar(labels, values, unit = "", w = 620) {
  const rowh = 22, left = 130, right = 70, h = rowh * values.length + 16, mx = Math.max(...values) || 1;
  const out = [`<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" class="chart" style="${FONT}">`];
  values.forEach((v, i) => {
    const y = 6 + i * rowh, bw = (w - left - right) * v / mx;
    out.push(`<text x="${left - 8}" y="${y + 14}" text-anchor="end" font-size="11" fill="${INK}">${H(labels[i])}</text><rect x="${left}" y="${y + 3}" width="${bw.toFixed(1)}" height="${rowh - 8}" rx="3" fill="${i === 0 ? RED : i > 2 ? SOFT : ORANGE}"/><text x="${(left + bw + 6).toFixed(1)}" y="${y + 14}" font-size="10.5" fill="${MUTED}">${fmtDot(v)} ${H(unit)}</text>`);
  });
  return out.join("") + "</svg>";
}
function line(labels, values, title = "", unit = "", w = 620, h = 210) {
  const pl = 56, pr = 20, pt = 30, pb = 28;
  let lo = Math.min(...values), hi = Math.max(...values);
  const p = (hi - lo) * .2 || Math.abs(hi) * .1 || 1; lo -= p; hi += p;
  const X = i => pl + i * (w - pl - pr) / Math.max(values.length - 1, 1), Y = v => pt + (hi - v) * (h - pt - pb) / (hi - lo);
  const out = [`<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" class="chart" style="${FONT}">`,
    `<text x="${pl}" y="16" font-size="12" font-weight="bold" fill="${INK}">${H(title)}${unit ? " (" + H(unit) + ")" : ""}</text>`];
  for (let k = 0; k < 4; k++) { const v = lo + (hi - lo) * (k + .5) / 4;
    out.push(`<line x1="${pl}" x2="${w - pr}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" stroke="${GRID}"/><text x="${pl - 6}" y="${(Y(v) + 3).toFixed(1)}" text-anchor="end" font-size="9.5" fill="${MUTED}">${fmtDot(v)}</text>`); }
  out.push(`<polyline points="${values.map((v, i) => X(i).toFixed(1) + "," + Y(v).toFixed(1)).join(" ")}" fill="none" stroke="${RED}" stroke-width="2.4" stroke-linejoin="round"/>`);
  values.forEach((v, i) => out.push(`<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="3.2" fill="${RED}"/><text x="${X(i).toFixed(1)}" y="${(Y(v) - 8).toFixed(1)}" text-anchor="middle" font-size="9.5" fill="${INK}">${fmtDot(v)}</text><text x="${X(i).toFixed(1)}" y="${h - 8}" text-anchor="middle" font-size="10" fill="${MUTED}">${H(labels[i])}</text>`));
  return out.join("") + "</svg>";
}
function bars(labels, series, unit = "", w = 620, h = 220) {
  const pl = 50, pr = 16, pt = 34, pb = 26, names = Object.keys(series);
  const mx = Math.max(...names.map(n => Math.max(...series[n]))) || 1;
  const gw = (w - pl - pr) / labels.length, bw = gw * .7 / names.length, colors = [RED, ORANGE, SOFT];
  const out = [`<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" class="chart" style="${FONT}">`];
  names.forEach((n, k) => out.push(`<rect x="${pl + k * 90}" y="6" width="10" height="10" fill="${colors[k]}"/><text x="${pl + k * 90 + 14}" y="15" font-size="11" fill="${INK}">${H(n)}</text>`));
  out.push(`<text x="${w - pr}" y="15" text-anchor="end" font-size="10" fill="${MUTED}">${H(unit)}</text>`);
  labels.forEach((l, i) => {
    names.forEach((n, k) => { const v = series[n][i], bh = (h - pt - pb) * v / mx, x = pl + i * gw + gw * .15 + k * bw;
      out.push(`<rect x="${x.toFixed(1)}" y="${(h - pb - bh).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${bh.toFixed(1)}" fill="${colors[k]}" rx="2"/><text x="${(x + bw / 2).toFixed(1)}" y="${(h - pb - bh - 4).toFixed(1)}" text-anchor="middle" font-size="9" fill="${INK}">${fmtDot(v)}</text>`); });
    out.push(`<text x="${(pl + i * gw + gw / 2).toFixed(1)}" y="${h - 8}" text-anchor="middle" font-size="10.5" fill="${MUTED}">${H(l)}</text>`);
  });
  return out.join("") + `<line x1="${pl}" x2="${w - pr}" y1="${h - pb}" y2="${h - pb}" stroke="#bbb"/></svg>`;
}
function chartSvg(c) {
  if (!c) return "";
  try {
    if (c.type === "hbar") return hbar(c.labels, c.values, c.unit || "");
    if (c.type === "line") return line(c.labels, c.values, c.title || "", c.unit || "");
    if (c.type === "bars") return bars(c.labels, c.series, c.unit || "");
  } catch (e) {}
  return "";
}

/* ------------------------------------------------------------------ rapor (templates/report.html) */
function paragraphs(text) {
  return String(text || "").split(/\n\s*\n/).map(p => p.trim()).filter(Boolean).map(p => {
    const ls = p.split("\n"), its = ls.filter(l => l.startsWith("- ")).map(l => l.slice(2).trim());
    return its.length && its.length === ls.length ? { list: its } : { p };
  });
}
const REPORT_CSS = `
  :root { --red: #8B1A1A; --soft: #f6e7e2; --line: #d9cfca; }
  body { font: 11.5pt/1.5 "Times New Roman", Times, serif; color: #111; margin: 0; }
  .cover { height: 297mm; box-sizing: border-box; padding: 36mm 24mm 24mm; display: flex; flex-direction: column;
           background: linear-gradient(180deg, #fff 0%, #fff 62%, #f8efeb 100%); break-after: page; position: relative; }
  .cover .office { font: bold italic 15pt Georgia, serif; color: var(--red); letter-spacing: .02em; }
  .cover .bar { width: 60mm; height: 2.5mm; background: var(--red); margin: 10mm 0 18mm; }
  .cover h1 { font: bold 30pt/1.15 Georgia, serif; color: #1d1d1f; margin: 0; letter-spacing: .01em; }
  .cover h1 span { display: block; }
  .cover h1 span:first-child { color: var(--red); font-size: 36pt; margin-bottom: 4mm; }
  .cover .meta { margin-top: auto; font: 11pt Georgia, serif; color: #333; border-top: 1px solid var(--line); padding-top: 6mm; }
  .cover .meta b { color: var(--red); }
  .toc { break-after: page; }
  .toc h2 { font: bold 20pt Georgia, serif; color: var(--red); margin: 0 0 8mm; }
  .toc .row { display: flex; align-items: baseline; gap: 2mm; font-size: 11pt; margin: 1.6mm 0; }
  .toc .row.l1 { font-weight: bold; margin-top: 3.5mm; }
  .toc .row.l2 { padding-left: 6mm; } .toc .row.l3 { padding-left: 12mm; font-size: 10.5pt; }
  .toc .dots { flex: 1; border-bottom: 1px dotted #999; transform: translateY(-1mm); }
  h2.s1, h3.s2, h4.s3 { font-family: Georgia, serif; color: var(--red); break-after: avoid; }
  h2.s1 { font-size: 15pt; margin: 9mm 0 3mm; padding-bottom: 1.5mm; border-bottom: 1.5px solid var(--red); }
  h3.s2 { font-size: 12.5pt; margin: 6mm 0 2mm; }
  h4.s3 { font-size: 11.5pt; margin: 4mm 0 1.5mm; color: #5a1a1a; }
  p { margin: 0 0 2.5mm; text-align: justify; }
  ul { margin: 0 0 3mm; padding-left: 6mm; } li { margin-bottom: 1mm; text-align: justify; }
  .empty { color: #a35f00; background: #fff6e0; border: 1px dashed #e5c27a; padding: 2mm 3mm; font: italic 10pt Georgia, serif; }
  table { width: 100%; border-collapse: collapse; margin: 2mm 0 1.5mm; font: 9.5pt/1.3 Helvetica, Arial, sans-serif; break-inside: auto; }
  thead { display: table-header-group; }
  th { background: var(--red); color: #fff; font-weight: 600; padding: 1.8mm 2mm; text-align: center; border: 1px solid #7a1616; }
  td { padding: 1.4mm 2mm; border: 1px solid var(--line); text-align: right; }
  td:first-child, td.txt { text-align: left; }
  tr:nth-child(even) td { background: #fbf7f5; }
  tr.total td { font-weight: bold; background: var(--soft); }
  .note { font: italic 8.5pt Helvetica, Arial, sans-serif; color: #666; margin-bottom: 4mm; }
  .chart { width: 100%; height: auto; margin: 2mm 0 1mm; break-inside: avoid; }`;
const secNum = s => /^\d/.test(s.id) ? `${H(s.id)}${s.level === 1 ? "." : ""} ` : "";
function reportHtml(rep, { part = "all", pages = {} } = {}) {
  const today = (() => { const d = new Date(); return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`; })();
  const secs = rep.sections.map(s => ({ ...s, paras: paragraphs(s.text), chart_svg: s.data ? chartSvg(s.data.chart) : "" }));
  const cell = (c, i) => {
    if (c && typeof c === "object") return `<td class="txt"><a href="${H(c.url)}" style="color:#111;text-decoration:none">${H(c.text)}</a></td>`;
    const txt = i < 3 && typeof c !== "number" && !/^\d/.test(String(c)) && String(c)[0] !== "-";
    return `<td class="${txt ? "txt" : ""}">${H(c)}</td>`;
  };
  const cover = `<section class="cover">
  <div class="office">TAŞKENT TİCARET MÜŞAVİRLİĞİ</div><div class="bar"></div>
  <h1>${(rep.cover_lines || []).map(w => `<span>${H(w)}</span>`).join("")}</h1>
  <div class="meta">Tarih: <b>${today}</b><br>Raporu Hazırlayan: <b>Taşkent Ticaret Müşavirliği</b></div></section>`;
  const toc = `<section class="toc"><h2>İçindekiler</h2>
  ${secs.map(s => `<div class="row l${s.level}"><span>${secNum(s)}${H(s.title)}</span><span class="dots"></span><span data-pg="${H(s.id)}">${pages[s.id] || ""}</span></div>`).join("\n  ")}</section>`;
  const body = secs.map(s => {
    const tag = { 1: "h2", 2: "h3", 3: "h4" }[s.level] || "h4";
    let out = `<${tag} class="s${s.level}" id="${H(s.id)}" data-sec="${H(s.id)}">${secNum(s)}${H(s.title)}</${tag}>`;
    out += s.paras.map(p => p.list ? `<ul>${p.list.map(li => `<li>${H(li)}</li>`).join("")}</ul>` : `<p>${H(p.p)}</p>`).join("");
    if (s.data && s.data.rows && s.data.rows.length) {
      out += `<table><thead><tr>${(s.data.columns || []).map(c => `<th>${H(c)}</th>`).join("")}</tr></thead><tbody>${s.data.rows.map(r =>
        `<tr class="${r[1] === "TOPLAM" || r[2] === "TOPLAM (fasıl)" || r[0] === "Dış Ticaret Hacmi" ? "total" : ""}">${r.map(cell).join("")}</tr>`).join("")}</tbody></table>
        <div class="note">${H(s.data.note || "")}</div>${s.chart_svg}`;
    } else if (s.kind !== "heading" && !s.paras.length) out += `<div class="empty">Bu bölüm henüz doldurulmadı.</div>`;
    return out;
  }).join("\n");
  const auto = [...new Set(secs.map(s => s.data && s.data.note && (s.data.note.match(/Kaynak: [^.]+/) || [])[0]).filter(Boolean).map(x => x.replace(/^Kaynak: /, "")))];
  const refs = (rep.refs || []);
  const kay = auto.length || refs.length ? `<h2 class="s1" id="kaynakca" data-sec="kaynakca">Kaynakça</h2><ul>${auto.map(x => `<li>${H(x)}</li>`).join("")}${refs.map(r => `<li>${H(r.name)}${r.note ? " · " + H(r.note) : ""}${r.url ? ` · <span style="word-break:break-all">${H(r.url)}</span>` : ""}</li>`).join("")}</ul>` : "";
  const inner = part === "cover" ? cover : part === "body" ? toc + body + kay : cover + toc + body + kay;
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>${H(rep.title)}</title><style>${REPORT_CSS}</style></head><body>${inner}</body></html>`;
}

/* ------------------------------------------------------------------ çizim: gizli çerçeve + html2canvas */
async function frame(html, width, height) {
  const f = document.createElement("iframe");
  f.setAttribute("aria-hidden", "true");
  f.style.cssText = `position:fixed;left:-30000px;top:0;width:${width}px;height:${height || 1200}px;border:0;background:#fff`;
  document.body.appendChild(f);
  await new Promise(r => setTimeout(r, 0));
  const d = f.contentDocument;
  d.open(); d.write(html); d.close();
  await new Promise(r => { if (d.readyState === "complete") r(); else f.contentWindow.addEventListener("load", r, { once: true }); setTimeout(r, 8000); });
  await Promise.all([...d.images].map(im => im.complete ? 0 : new Promise(r => { im.onload = im.onerror = r; setTimeout(r, 8000); })));
  // CSS arka plan görselleri (duyuru fotoğrafı) yüklensin
  const bgs = [...d.querySelectorAll("*")].map(el => (f.contentWindow.getComputedStyle(el).backgroundImage.match(/url\("?([^")]+)"?\)/) || [])[1]).filter(Boolean);
  await Promise.all(bgs.map(u => new Promise(r => { const im = new Image(); im.onload = im.onerror = r; im.src = u; setTimeout(r, 8000); })));
  if (d.fonts && d.fonts.ready) await d.fonts.ready;
  return f;
}
async function snap(el, opts) {
  if (!window.html2canvas) TT.fail("Çizim kütüphanesi yüklenemedi.");
  return html2canvas(el, { backgroundColor: "#ffffff", useCORS: true, allowTaint: false, logging: false, ...opts });
}
const toBlob = (cv, type = "image/png", q) => new Promise(r => cv.toBlob(r, type, q));

async function htmlToPng(html, W, Hh) {
  const f = await frame(html, W, Hh);
  try { const cv = await snap(f.contentDocument.body, { width: W, height: Hh, windowWidth: W, windowHeight: Hh, scale: 1 }); return await toBlob(cv); }
  finally { f.remove(); }
}

// A4: 794 x 1123 px (96 dpi). Sayfa sonu adayları: blok öğelerin alt kenarı; bölünmez öğeler kesilmez.
const A4W = 794, A4H = 1123, SCALE = 2;
function breakPlan(doc, pageH) {
  const win = doc.defaultView, body = doc.body;
  const top = el => el.getBoundingClientRect().top + win.scrollY, bot = el => el.getBoundingClientRect().bottom + win.scrollY;
  const total = Math.ceil(body.scrollHeight);
  const atomic = [...doc.querySelectorAll("p, li, tr, figure, svg, img, h1, h2, h3, h4, .tile, .row, .vid, .empty, .note, .headlines h2, .src-note")]
    .map(el => [top(el), bot(el)]).filter(([a, b]) => b - a < pageH * 0.9);
  const cands = new Set();
  doc.querySelectorAll("p, li, tr, figure, article, section, header, .date, ul, table, .note, .empty, .row, .videos, .charts, .tiles, .src-note, svg.chart").forEach(el => cands.add(Math.round(bot(el))));
  doc.querySelectorAll("h2, h3, h4").forEach(el => cands.add(Math.round(top(el) - 1)));
  const forced = [];
  doc.querySelectorAll("*").forEach(el => {
    const cs = win.getComputedStyle(el);
    if (cs.breakAfter === "page" || cs.pageBreakAfter === "always") forced.push(Math.round(bot(el)));
    if (cs.breakBefore === "page" || cs.pageBreakBefore === "always") forced.push(Math.round(top(el)));
  });
  // başlıktan hemen sonra sayfa bitmesin (break-after: avoid)
  const headBots = [...doc.querySelectorAll("h2, h3, h4")].map(el => Math.round(bot(el)));
  const ok = y => !atomic.some(([a, b]) => a < y - 1 && b > y + 1) && !headBots.some(h => Math.abs(h - y) < 2);
  const list = [...cands].filter(ok).sort((a, b) => a - b);
  const pages = [];
  let start = 0;
  while (start < total - 2) {
    const lim = start + pageH;
    const fz = forced.filter(y => y > start + 4 && y <= lim).sort((a, b) => a - b)[0];
    let end;
    if (fz) end = fz;
    else if (lim >= total) end = total;
    else { const c = list.filter(y => y > start + pageH * 0.35 && y <= lim); end = c.length ? c[c.length - 1] : lim; }
    pages.push([start, end]);
    start = end;
    while (forced.includes(start) && false) break;
  }
  return pages;
}
function wrapLines(ctx, text, maxW) {
  const out = [];
  String(text).split("\n").forEach(par => {
    let line = "";
    par.split(/\s+/).forEach(w => { const t = line ? line + " " + w : w; if (ctx.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t; });
    out.push(line);
  });
  return out;
}
/* Akışlı belge -> A4 sayfa görüntüleri. margins (px): [üst, sağ, alt, sol]; deco(ctx, i, n) üst/alt bilgi çizer. */
async function flowPages(html, margins, deco, { before, progress } = {}) {
  const [mt, mr, mb, ml] = margins, cw = A4W - ml - mr, ch = A4H - mt - mb;
  const f = await frame(html, cw, A4H);
  try {
    const doc = f.contentDocument;
    const plan = breakPlan(doc, ch);
    if (before) await before(doc, plan);
    const out = [];
    for (let i = 0; i < plan.length; i++) {
      if (progress) progress(i + 1, plan.length);
      const [a, b] = plan[i];
      const cv = await snap(doc.body, { x: 0, y: a, width: cw, height: Math.max(1, b - a), windowWidth: cw, windowHeight: Math.max(A4H, doc.body.scrollHeight), scrollY: 0, scale: SCALE });
      const pg = document.createElement("canvas");
      pg.width = A4W * SCALE; pg.height = A4H * SCALE;
      const ctx = pg.getContext("2d");
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, pg.width, pg.height);
      ctx.drawImage(cv, ml * SCALE, mt * SCALE);
      ctx.save(); ctx.scale(SCALE, SCALE); deco(ctx, i, plan.length); ctx.restore();
      out.push(pg);
    }
    return { pages: out, plan };
  } finally { f.remove(); }
}
function pagesToPdf(canvases) {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
  canvases.forEach((cv, i) => {
    if (i) pdf.addPage();
    pdf.addImage(cv.toDataURL("image/jpeg", 0.86), "JPEG", 0, 0, 210, 297, undefined, "FAST");
  });
  return pdf.output("blob");
}
const MM = 96 / 25.4;

async function bulletinPdf(drafts, issueDate, lang, review, rates, progress) {
  const L = LBL.B[lang];
  const html = bulletinHtml(drafts, issueDate, lang, review, rates);
  const deco = (ctx, i, n) => {
    if (i > 0) { ctx.fillStyle = "#8B1A1A"; ctx.font = "italic 10.7px Georgia, serif"; ctx.textAlign = "right"; ctx.fillText(`${L.office_short} · ${issueDate}`, A4W - 20 * MM, 12 * MM); }
    ctx.fillStyle = "#222"; ctx.textAlign = "center"; ctx.font = "bold italic 10px Georgia, serif";
    const lines = wrapLines(ctx, L.note, A4W - 40 * MM).concat([`${L.page} ${i + 1}/${n}`.trim()]);
    const y0 = A4H - 24 * MM + 5 * MM;
    ctx.strokeStyle = "#222"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(20 * MM, y0 - 3 * MM); ctx.lineTo(A4W - 20 * MM, y0 - 3 * MM); ctx.stroke();
    lines.forEach((l, k) => ctx.fillText(l, A4W / 2, y0 + 1 * MM + k * 12));
  };
  const { pages } = await flowPages(html, [18 * MM, 20 * MM, 24 * MM, 20 * MM], deco, { progress });
  return { blob: pagesToPdf(pages), pages: pages.length };
}

async function reportPdf(rep, progress) {
  const coverF = await frame(reportHtml(rep, { part: "cover" }), A4W, A4H);
  let cover;
  try { cover = await snap(coverF.contentDocument.body, { width: A4W, height: A4H, windowWidth: A4W, windowHeight: A4H, scale: SCALE }); }
  finally { coverF.remove(); }
  const deco = (ctx, i) => {
    ctx.fillStyle = "#8B1A1A"; ctx.font = "bold italic 11.3px Georgia, serif"; ctx.textAlign = "left"; ctx.fillText("TAŞKENT TİCARET MÜŞAVİRLİĞİ", 22 * MM, 13 * MM);
    ctx.fillStyle = "#444"; ctx.font = "12px Georgia, serif"; ctx.textAlign = "center"; ctx.fillText(String(i + 2), A4W / 2, A4H - 10 * MM);
  };
  const before = (doc, plan) => {  // içindekiler sayfa numaraları
    const win = doc.defaultView;
    doc.querySelectorAll("[data-sec]").forEach(h => {
      const y = h.getBoundingClientRect().top + win.scrollY + 2;
      const idx = plan.findIndex(([a, b]) => y >= a && y < b);
      const cell = doc.querySelector(`[data-pg="${CSS.escape(h.dataset.sec)}"]`);
      if (cell && idx >= 0) cell.textContent = idx + 2;
    });
  };
  const { pages } = await flowPages(reportHtml(rep, { part: "body" }), [20 * MM, 20 * MM, 20 * MM, 22 * MM], deco, { before, progress });
  const pg = document.createElement("canvas"); pg.width = A4W * SCALE; pg.height = A4H * SCALE;
  pg.getContext("2d").drawImage(cover, 0, 0, pg.width, pg.height);
  const all = [pg].concat(pages);
  return { blob: pagesToPdf(all), pages: all.length };
}

async function annOutput(a, fmt, photoUrl) {
  const [W, Hh] = LBL.F[fmt];
  const png = await htmlToPng(annHtml(a, fmt, photoUrl), W, Hh);
  if (fmt !== "afis") return { blob: png, pages: 1 };
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
  const du = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(png); });
  pdf.addImage(du, "PNG", 0, 0, 210, 297, undefined, "FAST");
  return { blob: pdf.output("blob"), pages: 1 };
}

/* ------------------------------------------------------------------ PDF önizleme (pdf.js) */
let pdfjsReady = null;
function pdfjs() {
  if (!pdfjsReady) pdfjsReady = Promise.resolve().then(() => {
    if (!window.pdfjsLib) TT.fail("PDF kütüphanesi yüklenemedi.");
    pdfjsLib.GlobalWorkerOptions.workerSrc = "static/lib/pdf.worker.min.js";
    return pdfjsLib;
  });
  return pdfjsReady;
}
const pdfDocs = {};
async function pdfDoc(url) {
  if (!pdfDocs[url]) pdfDocs[url] = pdfjs().then(lib => lib.getDocument({ url, isEvalSupported: false }).promise);
  return pdfDocs[url];
}
async function pdfPageCount(blobOrUrl) {
  const lib = await pdfjs();
  const src = typeof blobOrUrl === "string" ? { url: blobOrUrl } : { data: new Uint8Array(await blobOrUrl.arrayBuffer()) };
  const d = await lib.getDocument({ ...src, isEvalSupported: false }).promise;
  const n = d.numPages; d.destroy(); return n;
}
const thumbCache = {};
async function pdfThumb(url, page, width) {
  const key = url + "|" + page + "|" + width;
  if (!thumbCache[key]) thumbCache[key] = (async () => {
    const d = await pdfDoc(url);
    const pg = await d.getPage(Math.min(page + 1, d.numPages));
    const vp0 = pg.getViewport({ scale: 1 }), vp = pg.getViewport({ scale: width / vp0.width });
    const cv = document.createElement("canvas"); cv.width = Math.round(vp.width); cv.height = Math.round(vp.height);
    await pg.render({ canvasContext: cv.getContext("2d"), viewport: vp }).promise;
    return cv.toDataURL("image/jpeg", 0.85);
  })();
  return thumbCache[key];
}
async function pdfText(blob) {  // rapor içe aktarma: satırlar + yazı boyutu
  const lib = await pdfjs();
  const d = await lib.getDocument({ data: new Uint8Array(await blob.arrayBuffer()), isEvalSupported: false }).promise;
  const pages = [];
  for (let i = 1; i <= d.numPages; i++) {
    const pg = await d.getPage(i), vp = pg.getViewport({ scale: 1 }), tc = await pg.getTextContent();
    const lines = [];
    tc.items.forEach(it => {
      if (!it.str.trim() && !it.hasEOL) return;
      const y = Math.round(vp.height - it.transform[5]), size = Math.round(Math.hypot(it.transform[2], it.transform[3]));
      const bold = /bold|black|heavy/i.test((tc.styles[it.fontName] || {}).fontFamily || "") || /bold/i.test(it.fontName);
      const last = lines[lines.length - 1];
      if (last && Math.abs(last.y - y) < 3) { last.text += (last.text.endsWith(" ") || it.str.startsWith(" ") ? "" : " ") + it.str; last.size = Math.max(last.size, size); }
      else lines.push({ y, text: it.str, size, bold });
    });
    pages.push({ height: vp.height, lines: lines.map(l => ({ ...l, text: l.text.replace(/\s+/g, " ").trim() })).filter(l => l.text) });
  }
  return pages;
}

/* ------------------------------------------------------------------ sunum slaytları (16:9) ve video */
const SW = 1600, SH = 900;
function photoUrl(it) {
  if (it.photo && it.photo.show !== false && (it.photo.file || it.photo.src)) return it.photo.file ? TT.fileUrl("img:" + it.photo.file) : it.photo.src;
  if (it.image) return TT.fileUrl("img:" + it.image);
  return null;
}
function slideHtml(d, i, issue, lang) {
  const L = LBL.B[lang];
  const css = `*{box-sizing:border-box;margin:0;padding:0} body{width:${SW}px;height:${SH}px;font-family:Georgia,"Times New Roman",serif;background:#fff;color:#222;position:relative;overflow:hidden}
  .top{position:absolute;left:0;right:0;top:0;height:92px;background:#8B1A1A;color:#fff;display:flex;align-items:center;padding:0 56px;font:600 22px Helvetica,Arial,sans-serif;letter-spacing:.3px}
  .top .sp{flex:1} .top img{height:46px;margin-right:18px;border-radius:3px}
  .bot{position:absolute;left:56px;right:56px;bottom:26px;font:16px Helvetica,Arial,sans-serif;color:#888;display:flex}
  .bot .sp{flex:1}
  .n{font:700 26px Helvetica,Arial,sans-serif;color:#8B1A1A;margin-bottom:14px}
  h1{font-size:46px;line-height:1.18;margin-bottom:24px;color:#1d1d1d}
  p{font-size:25px;line-height:1.5;color:#333}
  .src{margin-top:20px;font:italic 18px Helvetica,Arial,sans-serif;color:#8B1A1A}
  .ph{position:absolute;right:0;top:92px;bottom:0;width:42%;background:#eee center/cover no-repeat}
  .ph::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,#fff 0,rgba(255,255,255,0) 14%)}
  .tx{position:absolute;left:72px;top:150px;bottom:90px;overflow:hidden}`;
  const head = `<div class="top"><span>${H(L.office_1)} · ${H(L.office_2)}</span><span class="sp"></span><span>${H(issue)}</span></div>`;
  if (i === 0) {
    return `<!doctype html><html><head><meta charset="utf-8"><base href="${H(new URL("static/", location.href).href)}"><style>${css}
      .cv{position:absolute;inset:92px 0 0 0;display:flex;flex-direction:column;justify-content:center;padding:0 110px;background:linear-gradient(135deg,#fff 0,#fff 62%,#f7e9e9 100%)}
      .cv h1{font-size:68px;color:#8B1A1A} .cv .d{font:30px Helvetica,Arial,sans-serif;color:#555;margin-top:10px}
      .cv ol{margin-top:40px;font:22px Helvetica,Arial,sans-serif;color:#444;columns:2;column-gap:60px;padding-left:28px} .cv li{margin:0 0 8px}</style></head><body>${head}
      <div class="cv"><h1>${H(L.doc_title.replace(/_/g, " "))}</h1><div class="d">${H(issue)}</div>
      <ol>${d.items.slice(0, 12).map(it => `<li>${H(it.headline.replace(/\.$/, "").slice(0, 80))}</li>`).join("")}</ol></div>
      <div class="bot"><span>${H(L.office_short || "")}</span><span class="sp"></span><span>${d.items.length} haber</span></div></body></html>`;
  }
  const it = d.items[i - 1], ph = photoUrl(it);
  const para = (it.paragraphs[0] || "").length > 520 ? it.paragraphs[0].slice(0, 500).replace(/\s+\S*$/, "") + "…" : (it.paragraphs[0] || "");
  return `<!doctype html><html><head><meta charset="utf-8"><base href="${H(new URL("static/", location.href).href)}"><style>${css}</style></head><body>${head}
    ${ph ? `<div class="ph" style="background-image:url('${H(ph)}')"></div>` : ""}
    <div class="tx" style="right:${ph ? "46%" : "72px"}"><div class="n">${i} / ${d.items.length}</div><h1>${H(it.headline)}</h1><p>${H(para)}</p>
      <div class="src">${H(it.sources.map(s => s.name).join(", "))}</div></div>
    <div class="bot"><span>${H(L.office_short || "")}</span><span class="sp"></span><span>${i + 1}</span></div></body></html>`;
}
async function slidePng(d, i, issue, lang) { return htmlToPng(slideHtml(d, i, issue, lang), SW, SH); }
async function slidesPdf(pngs) {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ orientation: "landscape", unit: "px", format: [SW, SH], compress: true });
  for (let i = 0; i < pngs.length; i++) {
    if (i) pdf.addPage([SW, SH], "landscape");
    const url = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(pngs[i]); });
    pdf.addImage(url, "PNG", 0, 0, SW, SH, undefined, "FAST");
  }
  return pdf.output("blob");
}
// Video: slaytlar tuvalde sırayla gösterilir ve MediaRecorder ile WebM olarak kaydedilir (seslendirmesiz).
async function slidesVideo(pngs, seconds, progress) {
  if (!window.MediaRecorder) TT.fail("Bu tarayıcı video kaydını desteklemiyor (Chrome veya Edge kullanın).");
  const cv = document.createElement("canvas"); cv.width = 1920; cv.height = 1080;
  const ctx = cv.getContext("2d");
  const imgs = await Promise.all(pngs.map(b => createImageBitmap(b)));
  const stream = cv.captureStream(30);
  const mime = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"].find(m => MediaRecorder.isTypeSupported(m)) || "";
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 4e6 });
  const chunks = []; rec.ondataavailable = e => e.data.size && chunks.push(e.data);
  const done = new Promise(r => { rec.onstop = r; });
  const draw = (im, a) => { ctx.globalAlpha = a; ctx.drawImage(im, 0, 0, 1920, 1080); ctx.globalAlpha = 1; };
  draw(imgs[0], 1); rec.start(500);
  for (let i = 0; i < imgs.length; i++) {
    progress && progress(i, imgs.length);
    const t0 = performance.now(), dur = seconds * 1000;
    await new Promise(r => {
      const tick = () => {
        const t = performance.now() - t0;
        if (i > 0 && t < 500) { draw(imgs[i - 1], 1); draw(imgs[i], t / 500); } else draw(imgs[i], 1);
        if (t < dur) requestAnimationFrame(tick); else r();
      };
      requestAnimationFrame(tick);
    });
  }
  rec.stop(); await done;
  return new Blob(chunks, { type: "video/webm" });
}

Object.assign(TT, { setLabels: l => { LBL = l; }, labels: () => LBL, bulletinHtml, annHtml, annCaption, reportHtml, bulletinPdf, reportPdf, annOutput,
  htmlToPng, slidePng, slidesPdf, slidesVideo, pdfThumb, pdfPageCount, pdfText, qrSvg, lineSvg, fmtNum });
})();
