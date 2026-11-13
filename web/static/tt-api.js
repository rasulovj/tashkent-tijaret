/* Panelin /api/... uçları (bot/panel.py karşılığı) — tarayıcıda. */
(function () {
"use strict";
const { Store, Blobs, H, clone, nowIso, todayIso, dslug, asciiSlug, fail, LANGS } = TT;
const B = {};          // anlık görüntü (api/*.json)
const repCache = {};   // anlık görüntüdeki rapor belgeleri
let H0 = null, A0 = null;

/* ------------------------------------------------------------------ başlangıç */
async function getJson(name, dflt) {
  try { const r = await fetch(`veri/${name}.json`, { cache: "no-cache" }); if (!r.ok) return dflt; return await r.json(); } catch (e) { return dflt; }
}
async function init() {
  const names = ["state", "feed", "inst", "reports", "report-types", "ann-list", "rates", "_labels", "_ozel", "_regions", "_drafts-en", "_drafts-uz", "_drafts-ru", "_robot"];
  const vals = await Promise.all(names.map(n => getJson(n, null)));
  names.forEach((n, i) => { B[n] = vals[i]; });
  TT.setLabels(B._labels);
  B.state.drafts.items.forEach(it => { delete it.warnings; delete it.n; });
  H0 = await TT.contentHash(B.state.drafts);
  A0 = await TT.approvalHash(B.state.drafts);
  await Store.init();
  await Blobs.init();
}

/* ------------------------------------------------------------------ okuma yardımcıları */
const who = b => ((b && b.who) || TT.lsGet("who") || "editör").slice(0, 40);
function meta() {
  const m = Store.get("tt/meta");
  if (m) return clone(m);
  const tr = {};
  Object.entries(B.state.translations).forEach(([l, v]) => { if (v === "güncel") tr[l] = H0; else if (v === "eski") tr[l] = "eski"; });
  return { translations: tr, approved: B.state.approved ? { ...B.state.approved, hash: A0 } : null, history: B.state.history || [] };
}
async function saveMeta(m) { m.history = (m.history || []).slice(-300); await Store.set("tt/meta", m); }
async function log(w, action, m) { m = m || meta(); m.history.push({ at: nowIso(), who: w, action }); await saveMeta(m); }
function drafts() { const d = Store.get("tt/drafts"); return clone(d || B.state.drafts); }
function langDrafts(lang) {
  const tr = drafts();
  if (lang === "tr") return tr;
  const d = clone(Store.get("tt/drafts_" + lang) || B["_drafts-" + lang] || null);
  if (d) d.items.forEach((a, i) => { const b = tr.items[i] || {}; ["image", "image_caption", "photo", "videos"].forEach(k => { a[k] = b[k]; }); });
  return d;
}
const candidates = () => B.state.candidates.concat(fcands());
function fcands() { return (Store.get("tt/fcands") || {}).list || []; }
function fileDocs() { return Store.list("files"); }
function fileDoc(ref) { return Store.get("files/" + dslug(ref)); }
function fileUrl(ref) {
  const d = fileDoc(ref);
  if (d && d.blob) return Blobs.url(d.blob);
  if (ref.startsWith("img:")) return "d/img/" + ref.slice(4);
  return "d/file/" + dslug(ref);
}
TT.fileUrl = fileUrl;
async function putFile(ref, name, blob, extra = {}) {
  const key = await Blobs.put(blob, TT.mimeOf(name));
  const doc = { ref, name, size_kb: Math.round(blob.size / 1024), modified: nowIso(), blob: key, ...extra };
  await Store.set("files/" + dslug(ref), doc);
  return doc;
}
function pdfFiles() {
  const map = {};
  B.state.files.forEach(f => { map[f.ref] = { ...f }; });
  fileDocs().filter(d => d.group).forEach(d => { map[d.ref] = { name: d.name, ref: d.ref, group: d.group, pages: d.pages || 1, size_kb: d.size_kb, modified: d.modified, editor: !!d.editor }; });
  return Object.values(map).sort((a, b) => (b.modified || "").localeCompare(a.modified || ""));
}
function images() {
  const s = new Set(B.state.images);
  fileDocs().filter(d => d.ref.startsWith("img:") && /\.png$/i.test(d.ref)).forEach(d => s.add(d.ref.slice(4)));
  return [...s].sort();
}
function feedItems() {  // anlık görüntü + robotun topladıkları
  const seen = new Set(), out = [];
  Store.list("feed").forEach(r => { if (!seen.has(r.url)) { seen.add(r.url); out.push(r); } });
  B.feed.forEach(r => { if (!seen.has(r.url)) { seen.add(r.url); out.push(r); } });
  return out.sort((a, b) => (b.published || "").localeCompare(a.published || ""));
}
function sourceCfg() {
  const s = Store.get("tt/sources");
  if (s) return clone(s);
  const computed = ["total", "week", "candidates", "in_bulletin", "last_published", "site"];
  return { sources: B.state.sources.map(x => Object.fromEntries(Object.entries(x).filter(([k]) => !computed.includes(k)))),
           autoscan: { enabled: B.state.autoscan.enabled !== false, minutes: B.state.autoscan.minutes || 60 } };
}
const inWeek = iso => iso && (Date.now() - new Date(iso).getTime()) <= 7 * 864e5;

/* "X'in 12 Kasım 2026 tarihli haberine göre," gibi gereksiz kaynak girişlerini kendiliğinden siler */
function cleanLead(p) {
  const s = String(p || "").replace(/^.{0,90}?\b\d{1,2}\s+\S+\s+\d{4}\s+tarihli\s+(?:haber(?:in)?(?:ine|e)?|yazısına|açıklamasına)\s+göre,?\s*/i, "")
    .replace(/^Haberin başlığında,?\s*/i, "")
    .replace(/\s*[^.]*(?:kaynak metinde|haberde|metinde) (?:yer )?(?:almamaktadır|bulunmamaktadır|verilmemiştir|yoktur)[^.]*\.?/gi, "").trim();
  return s ? s.charAt(0).toLocaleUpperCase("tr") + s.slice(1) : s;
}
/* ------------------------------------------------------------------ rakam doğrulama (bot/verify.py) */
const NUM = /\d+(?:[.,]\d+)*/g;
function variants(n) {
  const out = new Set([n, n.replace(/[.,]/g, c => c === "," ? "." : ","), n.replace(/,/g, "."), n.replace(/\./g, ","), n.replace(/[.,]/g, "")]);
  if (/^\d{1,3}(\.\d{3})+$/.test(n)) out.add(n.replace(/\./g, " "));
  return out;
}
function check(d) {
  const by = Object.fromEntries(candidates().map(c => [c.cid, c]));
  d.items.forEach(it => {
    // haberin yayın tarihi (gün, ay, yıl) de kaynağın parçası sayılır
    const src = (it.candidate_ids || []).filter(c => by[c]).map(c => by[c].title + " " + by[c].text + " " + (by[c].published || "")).join(" ") + " " + (it.source_text || "");
    const norm = src.replace(/(?<=\d)\s(?=\d{3})/g, "");
    const text = it.headline + " " + it.paragraphs.join(" ");
    const missing = [...new Set(text.match(NUM) || [])].sort().filter(n => {
      if (n.replace(/\D/g, "").length < 2 && !n.includes(",")) return false;
      return ![...variants(n)].some(v => src.includes(v) || norm.includes(v));
    });
    it.warnings = missing.map(m => `'${m}' kaynak metinde bulunamadı`);
  });
  return d;
}

/* ------------------------------------------------------------------ durum (Issue.state) */
async function settingsStatus() {
  return { anthropic: await TT.aiAvailable(), azure: false, azure_region: "", voices: {}, vercel: false, vercel_project: "taskentticaret", vercel_url: null,
           web: Store.mode === "db" ? "claude" : "yerel" };
}
function sources(feed) {
  const cfg = sourceCfg().sources, cands = candidates();
  const used = new Set(drafts().items.flatMap(it => it.sources.map(s => s.name)));
  return cfg.map(s => {
    const rows = feed.filter(it => it.source === s.name);
    return { ...s, total: rows.length, week: rows.filter(r => inWeek(r.published)).length,
             candidates: cands.filter(c => c.source === s.name).length, in_bulletin: used.has(s.name),
             last_published: rows.reduce((m, r) => (r.published > (m || "") ? r.published : m), null),
             site: String(s.url || "").replace(/^(https?:\/\/[^/]+).*/, "$1") };
  });
}
/* sayı = bugünün tarihi (Taşkent) */
function todayIssue() {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Tashkent", day: "2-digit", month: "2-digit", year: "numeric" }).formatToParts(new Date()).map(x => [x.type, x.value]));
  return `${p.day}.${p.month}.${p.year}`;
}
async function state() {
  B.state.issue = todayIssue();
  const d = check(drafts()), m = meta(), h = await TT.contentHash(d), ah = await TT.approvalHash(d);
  const feed = feedItems(), robot = Store.get("tt/robot") || {}, cfg = sourceCfg();
  const fetched = Store.list("feed").map(r => r.fetched_at).filter(Boolean).sort().pop();
  return {
    issue: B.state.issue, drafts: d, candidates: candidates(), hash: h,
    approved: m.approved && m.approved.hash === ah ? m.approved : null,
    translations: Object.fromEntries(LANGS.slice(1).map(l => [l, m.translations[l] === h ? "güncel" : (l in m.translations ? "eski" : "yok")])),
    files: pdfFiles(), videos: media().videos.concat(B.state.videos || []), decks: media().decks.concat(B.state.decks || []),
    photos: cfg.photos !== false, auto: autoState(),
    autoscan: { ...cfg.autoscan, last: robot.last || null, next: robot.next || null, added: robot.added ?? null, running: !!robot.running },
    settings: await settingsStatus(), inbox_new: Store.list("gelen").filter(x => x.status === "yeni").length,
    slides: media().slides || [], images: images(), api: await TT.aiAvailable(), history: m.history.slice(-30),
    stats: { raw_total: feed.length, raw_week: feed.filter(r => inWeek(r.published)).length,
             last_fetch: [B.state.stats.last_fetch, fetched].filter(Boolean).sort().pop() || null },
    sources: sources(feed),
  };
}
function feedRows() {
  const cands = Object.fromEntries(candidates().map(c => [c.url, c.cid]));
  const used = new Set(drafts().items.flatMap(it => it.candidate_ids || []));
  const usedUrls = new Set(drafts().items.flatMap(it => it.sources.map(s => s.url)));
  const tr = trCache();
  return feedItems().map(it => {
    const cid = cands[it.url], c = tr[it.id] || {};
    const title_tr = it.lang === "tr" ? null : (it.title_tr || c.t || null), summary_tr = it.lang === "tr" ? null : (it.summary_tr || c.s || null);
    return { ...it, summary: (it.summary || "").slice(0, 300), title_tr, summary_tr: summary_tr && summary_tr.slice(0, 400),
             tr_warn: it.lang === "tr" ? [] : (c.warn || numDiff(it.title + " " + (it.summary || ""), (title_tr || "") + " " + (summary_tr || ""), !summary_tr)),
             status: usedUrls.has(it.url) || (cid && used.has(cid)) ? "bülten" : cid ? "aday" : "", cid: cid || null };
  });
}

/* ------------------------------------------------------------------ arama */
const STOP = new Set(["ve", "ile", "için", "bir", "olan", "veya", "gibi", "the", "and", "for", "with", "of", "in", "и", "в", "на", "для", "с", "по"]);
const trLower = s => String(s).replace(/I/g, "ı").replace(/İ/g, "i").toLowerCase();
const qCache = {};
async function search(q) {
  const variantsQ = { tr: q.trim() };
  if (await TT.aiAvailable()) {
    try {
      qCache[q] = qCache[q] || await TT.ai(`Şu Türkçe arama ifadesini İngilizce, Rusça ve Özbekçeye (Latin) çevir. Yalnızca {"en":"...","ru":"...","uz":"..."} biçiminde JSON ver.\nİfade: ${q}`, { json: true, tier: "quick" });
      Object.assign(variantsQ, qCache[q]);
    } catch (e) {}
  }
  const toks = t => (trLower(t).match(/[0-9a-zçğıöşüа-яё]+/g) || []).filter(w => w.length >= 3 && !STOP.has(w)).map(w => w.slice(0, 5));
  const tokens = Object.fromEntries(Object.entries(variantsQ).map(([l, v]) => [l, toks(v)]));
  const scored = [];
  feedRows().forEach(it => {
    const text = trLower(it.title + " " + (it.title_tr || "") + " " + (it.summary || "") + " " + (it.summary_tr || ""));
    let best = 0;
    Object.values(tokens).forEach(tk => {
      if (!tk.length) return;
      const hits = tk.filter(w => text.includes(w)).length;
      if (hits === tk.length) best = Math.max(best, hits + 1);
      else if (hits >= Math.max(1, Math.round(tk.length * 0.6))) best = Math.max(best, hits - 0.5);
    });
    if (best) scored.push([best, it.published, it]);
  });
  scored.sort((a, b) => b[0] - a[0] || (b[1] || "").localeCompare(a[1] || ""));
  return { query: variantsQ, provider: (await TT.aiAvailable()) ? "claude" : "yerel", total: scored.length, results: scored.slice(0, 60).map(x => x[2]) };
}

/* ------------------------------------------------------------------ bülten işlemleri */
async function saveItems(items, w) {
  items.forEach(it => { delete it.warnings; delete it.n; it.paragraphs = it.paragraphs.map(p => p.trim()).filter(Boolean); });
  await Store.set("tt/drafts", { items });
  await log(w, `kaydedildi (${items.length} haber)`);
}
const progressToast = (pre) => (i, n) => { if (window.toast) window.toast(`${pre} · sayfa ${i}/${n}`); };
async function renderBulletin(lang, review) {
  const L = TT.labels().B[lang];
  const d = lang === "tr" ? check(drafts()) : langDrafts(lang);
  if (!d) fail(`${lang.toUpperCase()} çevirisi yok; önce çeviri yapın.`);
  let name = `${L.doc_title}-${B.state.issue}${review ? "-EDITOR" : ""}.pdf`;
  if (!review) { const used = new Set(fileDocs().map(x => x.ref)); for (let k = 2; used.has("issue:" + name); k++) name = `${L.doc_title}-${B.state.issue}-${k}.pdf`; }
  const { blob, pages } = await TT.bulletinPdf(d, B.state.issue, lang, review, B.rates, progressToast(`${lang.toUpperCase()} PDF hazırlanıyor`));
  await putFile("issue:" + name, name, blob, { group: "bülten", pages, editor: !!review });
  return name;
}
/* ------------------------------------------------------------------ otomatik bülten */
const AUTO_DEF = { enabled: false, days: [1, 2, 3, 4, 5], time: "10:00", count: 10, profile: null, examples: [], history: [] };
function autoCfg() { return { ...AUTO_DEF, ...clone(Store.get("tt/auto") || {}) }; }
const AUTO_STOP = new Set(["özbekistan", "özbek", "ülke", "yılı", "yılın", "ayında", "milyon", "milyar", "dolar", "olarak", "üzerinde", "kadar", "arasında", "tarafından", "yeni", "ilgili", "sonra", "önce", "daha", "olan", "için", "ile", "gibi", "bir", "ve", "veya", "bu", "da", "de", "en", "çok"]);
const autoToks = t => (trLower(t).match(/[a-zçğıöşü]{4,}/g) || []).filter(w => !AUTO_STOP.has(w)).map(w => w.slice(0, 6));
const AUTO_CATS = { makro: /büyüme|enflasyon|gsyh|merkez bank|faiz|bütçe|ekonomi/, ticaret: /ihracat|ithalat|ticaret|gümrük|fuar/, "yatırım": /yatırım|fabrika|tesis|proje|sanayi bölgesi/,
  enerji: /enerji|elektrik|doğalgaz|petrol|güneş|santral/, lojistik: /demiryolu|lojistik|kargo|havalimanı|ulaşım|transit/, mevzuat: /karar|kanun|yönetmelik|kararname|düzenleme/,
  finans: /banka|kredi|tahvil|borsa|eurobond|sigorta|finans/, "türkiye": /türk|türkiye|ankara|istanbul/ };
const autoCat = t => (Object.entries(AUTO_CATS).find(([, re]) => re.test(trLower(t))) || ["diğer"])[0];
async function autoLearn(files, w) {
  const cfg = autoCfg(), texts = [];
  for (const f of files) {
    const pages = await TT.pdfText(TT.dataUrlToBlob(f.data));
    texts.push({ name: f.name, text: pages.map(pg => pg.lines.map(l => l.text).join("\n")).join("\n").slice(0, 14000) });
  }
  if (!texts.length) fail("PDF seçin.");
  if (window.toast) window.toast(`Claude ${texts.length} örnek bülteni inceliyor…`);
  const prof = await TT.ai(`Aşağıda bir Türk ticaret müşavirliğinin daha önce yayımladığı ekonomi bültenleri var. Editörün HANGİ haberleri seçtiğini anlamak için incele.
Şu JSON'u döndür: {"count": bülten başına ortalama haber sayısı (tam sayı), "categories": {"makro":0-1 arası pay, "ticaret":..., "yatırım":..., "enerji":..., "lojistik":..., "mevzuat":..., "finans":..., "türkiye":..., "diğer":...},
"keywords": [{"k": "Türkçe anahtar kelime veya konu (tek kelime ya da kısa ifade)", "w": 1-3 önem}] (en fazla 40), "sources": [bültende en çok geçen kaynak adları], "turkey_focus": Türkiye ile ilgili haberler öne çıkıyor mu (true/false),
"notes": "seçim ölçütünü 2-3 cümleyle anlat", "headlines": [örnek başlıklar, en fazla 30]}
${texts.map(x => `<bulten ad="${x.name}">\n${x.text}\n</bulten>`).join("\n")}`, { json: true });
  if (!prof || !Array.isArray(prof.keywords)) fail("Örnekler okunamadı; başka bir PDF deneyin.");
  cfg.profile = { ...prof, learned_at: nowIso(), from: texts.map(x => x.name) };
  cfg.count = Math.max(3, Math.min(25, parseInt(prof.count, 10) || cfg.count));
  cfg.examples = [...new Set([...(cfg.examples || []), ...texts.map(x => x.name)])].slice(-20);
  await Store.set("tt/auto", cfg); await log(w, `otomatik bülten ölçütü ${texts.length} örnekten öğrenildi`);
  return cfg;
}
async function feedRead(id) {  // habere tıklayınca: Türkçe tam metin (bir kez çevrilir, saklanır)
  const r = feedRows().find(x => x.id === id); if (!r) fail("Haber bulunamadı.");
  const raw = feedItems().find(x => x.id === id) || {}, c = trCache()[id] || {}, body = String(raw.text || r.summary || "").trim();
  let full = r.lang === "tr" ? body : (raw.text_tr || c.f || ""), warn = raw.text_tr ? numDiff(body, raw.text_tr) : (c.fw || []);
  if (r.lang !== "tr" && !full && body && await TT.aiAvailable()) {
    const out = await TT.ai(`Aşağıdaki haber metnini Türkçeye çevir. Yalnızca çevir; bilgi ekleme, çıkarma, yorum yapma. Bütün rakamları, yüzdeleri, tarihleri, para birimlerini, kişi ve kurum adlarını kaynaktaki gibi koru (ondalık ayırıcı virgül). Paragrafları boş satırla ayır. "X sitesinin bildirdiğine göre" gibi kaynak cümlesi ekleme.
${TT.GLOSSARY}
Biçim: {"f":"Türkçe metin"}

${r.title}

${body.slice(0, 7000)}`, { json: true, tier: "default" });
    full = String(out.f || "").trim(); warn = numDiff(body.slice(0, 7000), full);
    const fresh = Store.get("tt/ceviri") || { map: {} }; fresh.map[id] = { ...(fresh.map[id] || {}), f: full, fw: warn };
    await Store.set("tt/ceviri", fresh);
  }
  return { id, lang: r.lang, title: r.title_tr || r.title, orig_title: r.title, text: full || r.summary_tr || (r.lang === "tr" ? r.summary : "") || "", orig: r.lang === "tr" ? "" : body,
    url: r.url, thumb: r.thumb, publisher: r.publisher || r.source, published: r.published, warn, status: r.status, short: !raw.text_full && body.length < 500 };
}
function autoState() { const a = autoCfg(); return { enabled: a.enabled, days: a.days, time: a.time, count: a.count, profile: a.profile, history_n: (a.history || []).length, last_run: a.last_run || null }; }
function autoRecord(items) {  // onaylanan her bülten, seçim ölçütüne örnek olur
  const cfg = autoCfg();
  cfg.history = [{ at: nowIso(), items: items.map(it => ({ h: it.headline, c: it.category, s: ((it.sources || [])[0] || {}).name || "" })) }, ...(cfg.history || [])].slice(0, 30);
  return Store.set("tt/auto", cfg);
}
async function autoPick(count) {
  const cfg = autoCfg(), prof = cfg.profile || {};
  count = Math.max(1, Math.min(25, +count || cfg.count || 10));
  const inDraft = new Set(drafts().items.flatMap(it => it.candidate_ids || []));
  const used = new Set((cfg.history || []).flatMap(h => h.items.map(x => trLower(x.h).slice(0, 40))));
  const last = (meta().approved || {}).at, now = Date.now();
  const since = Math.max(now - 10 * 864e5, Math.min(now - 2 * 864e5, last ? Date.parse(last) : now - 7 * 864e5));
  // anahtar kelime ağırlıkları: öğrenilen ölçüt + onaylanan bültenlerin başlıkları
  const kw = {};
  if (!prof.keywords) "ihracat ithalat ticaret yatırım büyüme enflasyon merkez bankası kredi enerji doğalgaz demiryolu lojistik fabrika sanayi türk türkiye fuar ihale gümrük".split(" ").forEach(k => autoToks(k).forEach(t => kw[t] = 1));
  (prof.keywords || []).forEach(x => autoToks(x.k).forEach(t => kw[t] = (kw[t] || 0) + (+x.w || 1)));
  (prof.headlines || []).concat((cfg.history || []).flatMap(h => h.items.map(x => x.h))).forEach(hd => autoToks(hd).forEach(t => kw[t] = (kw[t] || 0) + 0.3));
  const catW = { ...(prof.categories || {}) }, srcW = {};
  (cfg.history || []).forEach(h => h.items.forEach(x => { catW[x.c] = (catW[x.c] || 0) + 0.05; srcW[x.s] = (srcW[x.s] || 0) + 1; }));
  (prof.sources || []).forEach(s => srcW[s] = (srcW[s] || 0) + 2);
  const sMax = Math.max(1, ...Object.values(srcW));
  const fresh0 = feedRows().filter(r => r.status !== "bülten" && !inDraft.has("f-" + r.id) && !used.has(trLower(r.title_tr || r.title).slice(0, 40)));
  let pool = fresh0.filter(r => r.published && Date.parse(r.published) >= since);
  if (pool.length < count) pool = fresh0.slice(0, Math.max(count * 4, 40));  // yeni haber azsa en yenilerden seç
  const scored = pool.map(r => {
    const t = (r.title_tr || r.title) + " " + (r.summary_tr || r.summary || ""), toks = new Set(autoToks(t)), cat = autoCat(t);
    let sc = 0; toks.forEach(x => sc += Math.min(3, kw[x] || 0));
    sc = Math.min(sc, 12) / 12 * 3 + (catW[cat] || 0.1) * 2 + (srcW[r.publisher || r.source] || 0) / sMax
       + Math.max(0, 1 - (now - Date.parse(r.published || 0)) / (now - since)) * 0.8 + (r.thumb ? 0.15 : 0) + (prof.turkey_focus && cat === "türkiye" ? 0.8 : 0);
    if ((r.tr_warn || []).length) sc -= 1;
    if (!/\.uz\b|uzbek|o.zbek|узбек|ўзбек/i.test(r.url + " " + r.title) && !/özbek|taşkent|semerkant|buhara|navoi|fergana|harezm|andican|namangan|karakalpak/i.test(t)) sc -= 2.5;  // Özbekistan ile ilgisi yoksa geri
    if (/iade|dolandırıcı|tutukla|mahkeme|cinayet|kaza|futbol|spor|maç|turnuva|konser|festival|kanser|hastal|terör|güvenlik tehdit|hava durumu|deprem|yangın|eğitim ve bilim/.test(trLower(r.title_tr || r.title))) sc -= 2;  // ekonomi dışı
    return { r, sc, cat, toks };
  }).sort((a, b) => b.sc - a.sc);
  const pick = [], perCat = {}, cap = Math.max(2, Math.ceil(count / 3));
  const sim = (a, b) => { let n = 0; a.forEach(x => b.has(x) && n++); return n / Math.max(1, Math.min(a.size, b.size)); };
  for (const x of scored) {
    if (pick.length >= count * 2) break;
    if ((perCat[x.cat] || 0) >= cap * 2) continue;
    if (pick.some(y => sim(x.toks, y.toks) > 0.5)) continue;
    pick.push(x); perCat[x.cat] = (perCat[x.cat] || 0) + 1;
  }
  let ids = pick.slice(0, count).map(x => x.r.id);
  // Claude ölçüte göre son seçimi yapar (yoksa puan sırası kalır)
  if (pick.length > count && await TT.aiAvailable()) {
    try {
      const out = await TT.ai(`Bir ekonomi bülteni için ${count} haber seçeceksin. Seçim ölçütü: ${prof.notes || "Özbekistan ekonomisi, ticaret ve yatırım; Türkiye ile ilişkiler öne çıkar; asayiş, spor, magazin yok; aynı konuyu iki kez alma."}
Adaylar (id | kategori | başlık | özet):\n${pick.map(x => `${x.r.id} | ${x.cat} | ${x.r.title_tr || x.r.title} | ${String(x.r.summary_tr || x.r.summary || "").slice(0, 160)}`).join("\n")}
Önem sırasına göre tam ${count} id döndür: {"ids":["..."]}`, { json: true, tier: "quick" });
      const ok = (out.ids || []).filter(id => pick.some(x => x.r.id === id));
      if (ok.length >= Math.min(count, pick.length) - 1) ids = ok.slice(0, count);
    } catch (e) {}
  }
  if (!ids.length) fail("Seçilecek yeni haber yok. Önce “⟳ Şimdi tara” ile kaynakları tarayın.");
  return { ids, pool: pool.length };
}
async function approve(w) {
  const st = await state();
  const blockers = st.drafts.items.flatMap((it, i) => (it.warnings || []).map(x => `${i + 1}. haber: ${x}`));
  if (blockers.length) fail("Rakam uyarıları çözülmeden onaylanamaz:\n" + blockers.join("\n"));
  B.state.issue = todayIssue();
  const files = [];
  for (const l of LANGS) {
    if (l !== "tr" && st.translations[l] !== "güncel") continue;
    files.push(await renderBulletin(l, false));
  }
  const m = meta();
  m.approved = { hash: await TT.approvalHash(drafts()), by: w, files, at: nowIso() };
  try { await autoRecord(drafts().items); } catch (e) {}
  await log(w, "onaylandı: " + files.join(", "), m);
}
async function translate(lang, w) {
  const names = { en: "İngilizce", ru: "Rusça", uz: "Özbekçe (Latin alfabesi)" };
  const d = drafts();
  const src = { items: d.items.map(it => ({ headline: it.headline, paragraphs: it.paragraphs, category: it.category, candidate_ids: it.candidate_ids || [], sources: it.sources })) };
  if (window.toast) window.toast(`${names[lang]} çeviri Claude ile yapılıyor…`);
  const out = await TT.ai(`Türkçe ekonomi bülteni metinlerini ${names[lang]} diline resmi ve doğru biçimde çevir. Rakam, tarih ve kaynakları aynen koru; ekleme yapma. Haber sayısı ve sırası aynı kalsın.\n${TT.GLOSSARY}\n\nÇıktı biçimi: ${TT.ITEM_SHAPE}\n\n<bulten>\n${JSON.stringify(src)}\n</bulten>`, { json: true });
  if (!out || !Array.isArray(out.items) || out.items.length !== d.items.length) fail("Çeviri eksik döndü; yeniden deneyin.");
  // doğruluk denetimi: her haberde rakamlar Türkçe metinle birebir aynı olmalı; tutmayanlar bir kez Claude'a düzelttirilir
  const txt = it => it.headline + " " + (it.paragraphs || []).join(" ");
  const bad = () => out.items.map((it, i) => [i, numDiff(txt(d.items[i]), txt(it))]).filter(([, w]) => w.length);
  let wrong = bad();
  if (wrong.length) {
    const fix = await TT.ai(`Aşağıdaki ${names[lang]} çevirilerde rakamlar Türkçe asılla tutmuyor. Her haberi Türkçe aslına sadık kalarak yeniden çevir; bütün rakam, yüzde, tarih ve tutarlar asıldakiyle aynı olsun.\n${TT.GLOSSARY}\nBiçim: {"items":[{"i":0,"headline":"...","paragraphs":["..."]}]}\n\n${JSON.stringify(wrong.map(([i, w]) => ({ i, sorun: w, asil: { headline: d.items[i].headline, paragraphs: d.items[i].paragraphs } })))}`, { json: true });
    (fix.items || []).forEach(x => { if (out.items[x.i] && x.headline) { out.items[x.i].headline = x.headline; out.items[x.i].paragraphs = x.paragraphs; } });
    wrong = bad();
  }
  if (wrong.length) fail(`${names[lang]} çeviride rakamlar asılla tutmuyor, kaydedilmedi:\n` + wrong.map(([i, w]) => `${i + 1}. haber: ${w.join(", ")}`).join("\n"));
  await Store.set("tt/drafts_" + lang, { items: out.items });
  const m = meta();
  m.translations[lang] = await TT.contentHash(d);
  await log(w, `${lang.toUpperCase()} çevirisi güncellendi`, m);
}
async function writeItem(cid) {
  const c = candidates().find(x => x.cid === cid) || fail("Aday bulunamadı.");
  const body = `<aday id="${c.cid}" kaynak="${c.source}" dil="${c.lang}" tarih="${c.published}" url="${c.url}">\nBAŞLIK: ${c.title}\n${c.text}\n</aday>`;
  const out = await TT.ai(`${TT.STYLE_GUIDE}\n\nBu haftanın aday haberleri aşağıda. En önemli 1 haberi seç, önem sırasına diz ve bülten metnini yaz. Aynı olayı anlatan adayları tek haberde birleştir.\n\n${body}\nBu adayı mutlaka yaz (1 haber).\n\nÇıktı biçimi: ${TT.ITEM_SHAPE}`, { json: true });
  const it = (out.items || [])[0] || fail("Claude haber döndürmedi.");
  it.candidate_ids = it.candidate_ids && it.candidate_ids.length ? it.candidate_ids : [cid];
  return it;
}

/* ------------------------------------------------------------------ kaynaklar */
async function sourcesUpdate(b, w) {
  const cfg = sourceCfg();
  if (b.autoscan) cfg.autoscan = { ...cfg.autoscan, enabled: !!b.autoscan.enabled,
    times: Array.isArray(b.autoscan.times) ? b.autoscan.times.filter(x => /^\d\d:\d\d$/.test(x)).sort() : (cfg.autoscan.times || []), minutes: +b.autoscan.minutes || cfg.autoscan.minutes || 60 };
  if ("photos" in b) cfg.photos = !!b.photos;
  if (b.toggle) cfg.sources.forEach(s => { if (s.name === b.toggle) s.enabled = !(s.enabled !== false); });
  if (b.remove) cfg.sources = cfg.sources.filter(s => s.name !== b.remove);
  if (b.add) {
    const a = b.add, name = (a.name || "").trim();
    if (!name || cfg.sources.some(s => s.name === name)) fail("Kaynak adı boş ya da zaten var.");
    let src;
    if (a.kind === "telegram") {
      const h = String(a.url || "").trim().replace(/^(https?:\/\/)?t\.me\/(s\/)?|^@/, "").replace(/\/+$/, "");
      if (!h) fail("Telegram kanal adresi gerekli.");
      src = { name, group: "Telegram", lang: a.lang || "uz", kind: "telegram", handle: h, url: `https://t.me/s/${h}` };
    } else {
      let u = String(a.url || "").trim(); if (u && !/^https?:\/\//.test(u)) u = "https://" + u;
      if (!/^https?:\/\/[^/\s]+\.[^/\s]+/.test(u)) fail("Geçerli bir site adresi girin (ör. kun.uz).");
      src = { name, group: a.group || "Diğer", lang: a.lang || "tr", url: u, added_by_user: true };
    }
    if (a.institution) src.institution = a.institution;
    if (a.only_uz) src.filter = ["özbek", "taşkent", "semerkant", "buhara", "fergana", "mirziyoyev", "uzbek"];
    cfg.sources.push(src);
  }
  await Store.set("tt/sources", cfg);
  await log(w, "kaynak ayarları değiştirildi");
}

/* ------------------------------------------------------------------ haber toplama robotu */
async function scan(w) {
  const cfg = sourceCfg();
  // 1) Vercel / kendi sunucusu: api/topla (RSS + Telegram okuyucu)
  if (Store.mode !== "db") {
    let r;
    try { r = await fetch("api/topla", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sources: cfg.sources.filter(s => s.enabled !== false) }) }); } catch (e) { r = null; }
    if (!r || !r.ok || !(r.headers.get("content-type") || "").includes("json")) fail("Bu sunucuda haber toplama servisi (api/topla) yok. Vercel paketini kullanın ya da paneli claude.ai bağlantısından açın.");
    const j = await r.json();
    const known = new Set(feedItems().map(x => x.url));
    let added = 0;
    for (const it of j.items || []) {
      if (known.has(it.url)) continue;
      known.add(it.url); added++;
      await Store.set("feed/" + it.id, it);
    }
    await Store.set("tt/robot", { last: nowIso(), added, running: false });
    await log(w, `kaynaklar tarandı: ${added} yeni haber`);
    return { added };
  }
  // 2) claude.ai: zamanlanmış haber robotunu hemen çalıştır
  const robot = Store.get("tt/robot") || B._robot || {};
  if (!robot.trigger_id) fail("Haber robotu henüz kurulmadı.");
  const mcp = await TT.cap("mcp");
  if (!mcp) fail("Robotu buradan başlatmak için bağlayıcı izni gerekiyor; robot yine de 3 saatte bir kendiliğinden çalışır.");
  try { await mcp.callTool("Claude Code Remote", "fire_trigger", { trigger_id: robot.trigger_id }); }
  catch (e) {
    if (e && (e.code === "not_granted" || e.code === "approval_required")) fail("Robotu başlatma izni verilmedi. Robot 3 saatte bir kendiliğinden çalışmaya devam eder.");
    fail("Robot başlatılamadı: " + (e.message || e.code || e) + " · Robot 3 saatte bir kendiliğinden çalışır.");
  }
  await Store.set("tt/robot", { ...robot, running: true, requested: nowIso(), by: w });
  await log(w, "haber toplama robotu çalıştırıldı");
  return { added: 0, message: "Haber robotu çalıştırıldı · yeni haberler birkaç dakika içinde akışa düşer" };
}

/* ------------------------------------------------------------------ temsilcilikler */
function instMsgs() { return clone((Store.get("tt/inst") || {}).msgs || []); }
function institutions() {
  const base = clone(B.inst);
  const cfg = sourceCfg().sources;
  const insts = base.institutions;
  const feed = base.feed.filter(f => !f.manual);
  const seen = new Set(feed.map(f => f.url));
  Store.list("feed").filter(r => r.institution && !seen.has(r.url)).forEach(r => feed.push({ id: r.id, inst: r.institution, source: r.source, publisher: r.publisher,
    title: r.title_tr || r.title, summary: (r.text || r.summary || "").slice(0, 600), url: r.url, date: r.published, thumb: r.thumb, manual: false }));
  instMsgs().forEach(m => feed.push({ ...m, inst: m.institution, source: "Elle eklendi", date: m.date + "T12:00:00+05:00", summary: m.text || "", url: m.link, manual: true }));
  feed.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  const month = Date.now() - 30 * 864e5;
  insts.forEach(ins => {
    ins.sources = cfg.filter(x => x.institution === ins.key).map(x => ({ name: x.name, kind: x.kind || "rss", url: x.url, enabled: x.enabled !== false }));
    const mine = feed.filter(f => f.inst === ins.key);
    ins.total = mine.length; ins.month = mine.filter(f => new Date(f.date).getTime() >= month).length; ins.last = mine[0] ? mine[0].date : null;
  });
  return { institutions: insts, feed: feed.slice(0, 300) };
}
const instName = k => ((B.inst.institutions.find(i => i.key === k)) || { name: k || "Birim" }).name;
async function addToBulletin(item, w, action) {
  const d = drafts(); d.items.push(item);
  await Store.set("tt/drafts", { items: d.items });
  await log(w, action);
  return d.items.length;
}

/* ------------------------------------------------------------------ duyurular (bot/announce.py) */
const ANN_FIELDS = ["kind", "lang", "theme", "title", "subtitle", "text", "date", "date_end", "time", "place", "deadline", "link", "contact", "tag", "photo", "status"];
function annBase(id) { return (B["ann-list"] || []).find(a => a.id === id); }
function annLoad(id) {
  const o = Store.get("ann/" + id);
  if (o) return o.deleted ? null : clone(o);
  const b = annBase(id);
  if (!b) return null;
  const a = clone(b); delete a.outputs; delete a.caption; return a;
}
function annIds() {
  const ids = new Set((B["ann-list"] || []).map(a => a.id));
  Store.list("ann").forEach(a => ids.add(a.id));
  return [...ids];
}
function annOutputs(id) {
  const map = {};
  const b = annBase(id), o = Store.get("ann/" + id);
  if (b && !(o && o.outputs_reset)) b.outputs.forEach(x => { map[x.name] = x; });
  fileDocs().filter(d => d.ref.startsWith(`ann:${id}/`) && /\.(png|pdf)$/i.test(d.name) && !/^foto/.test(d.name)).forEach(d => { map[d.name] = { name: d.name, ref: d.ref }; });
  return Object.values(map).sort((a, b) => a.name.localeCompare(b.name));
}
async function annSave(a) { a.updated = nowIso(); await Store.set("ann/" + a.id, a); return a; }
async function annNew(kind = "etkinlik", lang = "tr") {
  return annSave({ id: TT.newId(), kind, lang, theme: "bordo", title: "", subtitle: "", text: "", date: "", date_end: "", time: "", place: "", deadline: "", link: "",
                   contact: "", tag: "", photo: null, status: "taslak", created: nowIso() });
}
async function annUpdate(id, vals) {
  const a = annLoad(id) || fail("Kayıt bulunamadı.");
  ANN_FIELDS.forEach(k => { if (k in vals) a[k] = vals[k]; });
  return annSave(a);
}
function annList() {
  const today = todayIso();
  const out = annIds().map(annLoad).filter(Boolean).map(a => ({ ...a, outputs: annOutputs(a.id), caption: TT.annCaption(a) }));
  return out.sort((a, b) => {
    const ka = [(a.date || "") >= today ? 0 : 1, a.date || "9999", a.updated || ""], kb = [(b.date || "") >= today ? 0 : 1, b.date || "9999", b.updated || ""];
    return ka[0] - kb[0] || ka[1].localeCompare(kb[1]) || ka[2].localeCompare(kb[2]);
  });
}
const annPhotoRef = a => a.photo ? `ann:${a.id}/${a.photo}` : null;
function annPhotoUrl(a) { const r = annPhotoRef(a); return r ? fileUrl(r) : null; }
function specialDays(lang = "tr", within = null) {
  const now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const out = [];
  (B._ozel || []).forEach(d => {
    let nxt = null;
    if (d.month) { nxt = new Date(today.getFullYear(), d.month - 1, d.day); if (nxt < today) nxt = new Date(today.getFullYear() + 1, d.month - 1, d.day); }
    const year = nxt ? nxt.getFullYear() : today.getFullYear(), n = d.base ? year - d.base : null;
    const t = d[lang] || d.tr, fill = x => String(x || "").replace(/\{n\}/g, n || "").replace(/\{year\}/g, year);
    const iso = nxt ? `${nxt.getFullYear()}-${String(nxt.getMonth() + 1).padStart(2, "0")}-${String(nxt.getDate()).padStart(2, "0")}` : null;
    const item = { key: d.key, kind: d.kind, country: d.country, date: iso, days_left: nxt ? Math.round((nxt - today) / 864e5) : null, n,
                   title: fill(t.title), greeting: fill(t.greeting), text: fill(t.text) };
    if (within == null || (item.days_left != null && item.days_left <= within)) out.push(item);
  });
  return out.sort((a, b) => (a.days_left == null) - (b.days_left == null) || (a.days_left || 0) - (b.days_left || 0));
}
async function fromSpecial(key, lang) {
  const d = specialDays(lang).find(x => x.key === key) || fail("Özel gün bulunamadı.");
  const a = await annNew(d.kind, lang);
  return annUpdate(a.id, { title: d.title, subtitle: d.greeting, text: d.text, date: d.date || "", theme: d.kind === "anma" ? "anma" : "bayram", tag: "" });
}
function annStem(a) { return asciiSlug(a.title || "duyuru").slice(0, 40).replace(/-+$/, "") || "duyuru"; }
async function annProduce(id, fmts) {
  const a = annLoad(id) || fail("Kayıt bulunamadı.");
  const photo = annPhotoUrl(a);
  for (const f of fmts) {
    if (window.toast) window.toast(`Tasarım hazırlanıyor: ${f}`);
    const { blob } = await TT.annOutput(a, f, photo);
    const name = `${annStem(a)}-${f}.${f === "afis" ? "pdf" : "png"}`;
    await putFile(`ann:${id}/${name}`, name, blob);
  }
  return annOutputs(id);
}
async function annPhoto(b) {
  const a = annLoad(b.id) || fail("Kayıt bulunamadı.");
  if (b.from_ref) {
    const r = await fetch(fileUrl(b.from_ref)); const blob = await r.blob();
    const ext = (b.from_ref.match(/\.\w+$/) || [".png"])[0].toLowerCase();
    await putFile(`ann:${a.id}/foto${ext}`, `foto${ext}`, blob);
    a.photo = `foto${ext}`;
  } else if (b.data) {
    const ext = ((b.name || "x.jpg").match(/\.\w+$/) || [".jpg"])[0].toLowerCase();
    if (![".jpg", ".jpeg", ".png", ".webp"].includes(ext)) fail("Yalnızca JPG, PNG veya WEBP görsel yüklenebilir.");
    await putFile(`ann:${a.id}/foto${ext}`, `foto${ext}`, TT.dataUrlToBlob(b.data));
    a.photo = `foto${ext}`;
  } else a.photo = null;
  return annSave(a);
}
async function annTranslate(id, lang) {
  const a = annLoad(id) || fail("Kayıt bulunamadı.");
  const keys = ["title", "subtitle", "text", "place", "tag"].filter(k => a[k]);
  const names = { tr: "Türkçe", uz: "Özbekçe (Latin alfabesi)", en: "İngilizce", ru: "Rusça" };
  const src = Object.fromEntries(keys.map(k => [k, a[k]]));
  const out = keys.length ? await TT.ai(`Aşağıdaki duyuru alanlarını ${names[a.lang] || "Türkçe"} dilinden ${names[lang]} diline resmi üslupla çevir. Aynı anahtarlarla JSON nesnesi döndür.\n${JSON.stringify(src)}`, { json: true }) : {};
  const b = await annNew(a.kind, lang);
  const vals = {};
  ["title", "subtitle", "text", "place", "tag"].forEach(k => { vals[k] = (out && out[k]) || a[k] || ""; });
  ["date", "date_end", "time", "deadline", "link", "contact", "theme"].forEach(k => { vals[k] = a[k]; });
  if (a.photo) {
    const d = fileDoc(annPhotoRef(a));
    if (d) await Store.set("files/" + dslug(`ann:${b.id}/${a.photo}`), { ...d, ref: `ann:${b.id}/${a.photo}` });
    else { const blob = await (await fetch(fileUrl(annPhotoRef(a)))).blob(); await putFile(`ann:${b.id}/${a.photo}`, a.photo, blob); }
    vals.photo = a.photo;
  }
  return annUpdate(b.id, vals);
}

/* ------------------------------------------------------------------ raporlar (bot/reports/builder.py) */
async function repLoad(id) {
  const o = Store.get("rep/" + id);
  if (o) return clone(o);
  if (!repCache[id]) { repCache[id] = await getJson("report-" + dslug(id), null); }
  if (!repCache[id]) fail("Rapor bulunamadı.");
  return clone(repCache[id]);
}
function repLog(r, w, action) { (r.history = r.history || []).push({ at: nowIso(), who: w, action }); }
async function repSave(r) { r.updated = nowIso(); await Store.set("rep/" + r.id, r); return r; }
function repPdfs(id) {
  const s = new Set(((B.reports || []).find(x => x.id === id) || { pdfs: [] }).pdfs);
  fileDocs().filter(d => d.ref.startsWith(`report:${id}/`) && d.name.endsWith(".pdf")).forEach(d => s.add(d.name));
  return [...s].sort();
}
async function repList() {
  const ids = new Set((B.reports || []).map(r => r.id));
  Store.list("rep").forEach(r => ids.add(r.id));
  const out = [];
  for (const id of [...ids].sort()) {
    const o = Store.get("rep/" + id), b = (B.reports || []).find(x => x.id === id);
    if (!o && b) { out.push({ ...b, pdfs: repPdfs(id) }); continue; }
    const secs = o.sections.filter(s => s.kind !== "heading");
    out.push({ id, title: o.title, type: o.type, type_name: o.type_name, updated: o.updated, total: secs.length,
               filled: secs.filter(s => s.status !== "boş").length, approved: secs.filter(s => s.status === "onaylandı").length, pdfs: repPdfs(id) });
  }
  return out;
}
function repFill(text, p) {
  const up = s => String(s).replace(/i/g, "İ").replace(/ı/g, "I").toUpperCase();
  return String(text).replace(/\{ulke\}/g, p.ulke ?? "").replace(/\{ULKE\}/g, up(p.ulke ?? "")).replace(/\{sektor\}/g, p.sektor ?? "")
    .replace(/\{SEKTOR\}/g, up(p.sektor ?? "")).replace(/\{yil\}/g, p.yil ?? "").replace(/\{sehir\}/g, p.sehir ?? "")
    .replace(/\{SEHIR\}/g, up(p.sehir ?? "")).replace(/\{odak\}/g, p.odak || "—")
    .replace(/\{([a-z]+)\}/g, (m, k) => k in p ? String(p[k]) : m).replace(/\{([A-Z]+)\}/g, (m, k) => k.toLowerCase() in p ? up(p[k.toLowerCase()]) : m);
}
async function repCreate(typeKey, raw, w) {
  const t = (B["report-types"] || {})[typeKey] || fail("Rapor türü bulunamadı.");
  const p = {};
  t.params.forEach(s => { let v = raw[s.key] ?? s.default; if (Number.isInteger(s.default)) v = parseInt(v, 10); p[s.key] = v; });
  if ("hs" in p) p.hs = String(p.hs).split(",").map(x => x.trim()).filter(Boolean);
  if ("sehir" in p && B._regions && B._regions[p.sehir]) { p.region_en = B._regions[p.sehir].en; p.kw = B._regions[p.sehir].kw; }
  if (p.odak) p.odak_kw = p.odak.replace(/,/g, " ").split(/\s+/).filter(x => x.length > 3).map(x => x.toLowerCase());
  const id = asciiSlug(`${typeKey}-${p.ulke || ""}-${p.sehir || ""}-${p.sektor || ""}-${p.odak || ""}-${p.konu || p.ay || p.donem || p.etkinlik || ""}-${p.yil || ""}`);
  if (Store.get("rep/" + id) || (B.reports || []).some(r => r.id === id)) fail("Bu rapor zaten var; soldaki listeden açabilirsiniz.");
  const rep = { id, type: typeKey, type_name: t.name, title: t.cover.map(x => repFill(x, p)).join(" "), params: p, cover_lines: t.cover.map(x => repFill(x, p)),
                created: nowIso(), history: [],
                sections: t.sections.filter(s => !(s.id === "odak" && !p.odak)).map(s => ({ ...s, title: repFill(s.title, p), text: "", status: "boş" })) };
  repLog(rep, w, "rapor oluşturuldu");
  return repSave(rep);
}
async function repImport(rep, blob, w) {  // önceki yılın PDF'i: başlıkları eşleştirip metni bölümlere dağıtır
  const norm = s => String(s).replace(/İ/g, "i").replace(/I/g, "ı").toLowerCase().replace(/[^0-9a-zçğıöşü]+/g, "");
  const strip = s => String(s).replace(/^\s*\d+(\.\d+)*\.?\s*[-–]?\s*/, "");
  const pages = await TT.pdfText(blob);
  const sizes = {};
  pages.forEach(pg => pg.lines.forEach(l => { sizes[l.size] = (sizes[l.size] || 0) + l.text.length; }));
  const bodySize = +Object.entries(sizes).sort((a, b) => b[1] - a[1])[0]?.[0] || 12;
  const targets = rep.sections.map((s, i) => [i, norm(strip(s.title))]);
  const body = rep.sections.map(() => []);
  let cur = null, pos = 0, found = 0, buf = [];
  const flush = () => {
    if (cur == null || !buf.length) { buf = []; return; }
    let para = buf.join(" ").replace(/-\s(?=[a-zçğıöşü])/g, "").replace(/\s+/g, " ").trim();
    buf = [];
    if (/^[•●▪➢-]\s*/.test(para)) para = "- " + para.replace(/^[•●▪➢-]\s*/, "");
    const letters = para.replace(/[^\p{L}]/gu, ""), digits = (para.match(/\d/g) || []).length;
    if (digits > 0.25 * para.length || (letters && para.length < 300 && (letters.match(/\p{Lu}/gu) || []).length > 0.6 * letters.length)) return;
    if (para.length >= 25 || para.endsWith(":")) body[cur].push(para);
  };
  pages.forEach(pg => {
    let lastY = null;
    pg.lines.forEach(l => {
      if (l.text.includes(".....") || /^[\d.\s]+$/.test(l.text) || l.text.toUpperCase().startsWith("TAŞKENT TİCARET MÜŞAVİRLİĞİ")) return;
      if ((l.y < 45 || l.y > pg.height - 35) && l.text.length < 60) return;
      const headLike = l.size >= bodySize + 0.8 || (l.bold && /^\d+(\.\d+)*\.?(\s|$)/.test(l.text)) || (l.bold && l.text.length > 4 && l.text === l.text.toUpperCase());
      let hit = null;
      if (headLike) {
        const head = norm(strip(l.text));
        for (let j = pos; j < Math.min(pos + 6, targets.length); j++) { const nt = targets[j][1], n = Math.min(nt.length, 18); if (n >= 5 && head.startsWith(nt.slice(0, n))) { hit = j; break; } }
      }
      if (hit != null) { flush(); cur = targets[hit][0]; pos = hit + 1; found++; lastY = l.y; return; }
      if (lastY != null && l.y - lastY > l.size * 1.9) flush();
      buf.push(l.text); lastY = l.y;
    });
    flush(); lastY = null;
  });
  let n = 0;
  rep.sections.forEach((s, i) => { if (body[i].length && s.kind !== "heading") { s.text = body[i].join("\n\n"); s.imported = true; if (s.status === "boş") s.status = "önceki rapordan"; n++; } });
  repLog(rep, w, `önceki rapordan içe aktarıldı (${n} bölüm, ${found} başlık eşleşti)`);
  return repSave(rep);
}
async function repAi(rep, sid, w) {
  const sec = rep.sections.find(s => s.id === sid) || fail("Bölüm bulunamadı.");
  const data = sec.data || {};
  const table = [data.columns || []].concat(data.rows || []).map(r => r.map(c => c && typeof c === "object" ? c.text : c).join(" | ")).join("\n");
  const out = await TT.ai(`Sen T.C. Taşkent Ticaret Müşavirliği adına resmî pazar/ülke raporu yazan bir uzmansın.
Görev: verilen bölümün geçen yılki metnini güncelle.
- Güncel veri tablosu varsa metindeki rakamları ve yılları tablodaki değerlerle değiştir.
- Tabloda karşılığı olmayan rakam veya bilgiyi değiştirme; güncelliği şüpheli ifadeleri [KONTROL] ile işaretle.
- Yeni bilgi uydurma. Resmî, nesnel Türkçe kullan. Paragrafları boş satırla ayır, madde işareti için "- " kullan.
- notes alanında editöre neyi değiştirdiğini ve neyi kontrol etmesi gerektiğini kısaca yaz.
Çıktı biçimi: {"text":"...","notes":"..."}

Rapor: ${rep.title}\nBölüm: ${sec.id} ${sec.title}\n\n<gecen_yil_metni>\n${sec.text || "(boş)"}\n</gecen_yil_metni>\n\n<guncel_veri kaynak="${data.note || ""}">\n${table.trim() || "(veri tablosu yok)"}\n</guncel_veri>`, { json: true });
  sec.text = out.text || sec.text; sec.ai_notes = out.notes || ""; sec.status = "taslak";
  repLog(rep, w, `${sec.id} Claude ile güncellendi`);
  return repSave(rep);
}
async function repRender(rep, w) {
  const { blob, pages } = await TT.reportPdf(rep, progressToast("Rapor PDF'i hazırlanıyor"));
  const base = asciiSlug(rep.title) + "-" + todayIssue();
  const used = new Set(fileDocs().map(x => x.ref));
  let name = base + ".pdf";
  for (let k = 2; used.has(`report:${rep.id}/${name}`); k++) name = `${base}-${k}.pdf`;
  await putFile(`report:${rep.id}/${name}`, name, blob, { group: "rapor", pages });
  repLog(rep, w, `PDF üretildi: ${name}`);
  return repSave(rep);
}

/* ------------------------------------------------------------------ gelen kutusu */
const IB_STATUSES = { yeni: "Yeni", inceleniyor: "İnceleniyor", yayina_alindi: "Yayına alındı", reddedildi: "Reddedildi" };
const IB_TYPES = { haber: "Haber", duyuru: "Duyuru", etkinlik: "Etkinlik", mesaj: "Mesaj / bilgi" };
function subLoad(id) { const s = Store.get("gelen/" + id); return s ? clone(s) : fail("Kayıt bulunamadı."); }
async function subSave(s) { await Store.set("gelen/" + s.id, s); return s; }
async function me() {
  const u = await TT.cap("user");
  let name = TT.lsGet("who") || "", id = "yerel";
  if (u) { try { const m = await u.me(); id = m.id || id; name = name || m.name || ""; } catch (e) {} }
  return { username: id, name: name || "Kullanıcı", role: "yonetici", institution: TT.lsGet("tt-birim") || "ticaret", inst_name: instName(TT.lsGet("tt-birim") || "ticaret") };
}
async function subNew(b) {
  const u = await me();
  const title = (b.title || "").trim() || fail("Başlık gerekli.");
  if (!IB_TYPES[b.type]) fail("Geçersiz tür.");
  const id = TT.newId();
  const files = [];
  let total = 0;
  for (const f of b.files || []) {
    const name = String(f.name || "ek").replace(/[^\w.\-]+/g, "_").slice(0, 80);
    if (!/\.(pdf|jpe?g|png|webp|docx?|xlsx|mp4)$/i.test(name)) fail(`Bu dosya türü kabul edilmiyor: ${name}`);
    const blob = TT.dataUrlToBlob(f.data); total += blob.size;
    if (total > 25 * 1048576) fail("Ekler toplamda 25 MB'ı geçemez.");
    await putFile(`sub:${id}/${name}`, name, blob);
    files.push(name);
  }
  const s = { id, type: b.type, title: title.slice(0, 200), text: (b.text || "").trim().slice(0, 8000), date: b.date || "", date_end: b.date_end || "",
    time: (b.time || "").slice(0, 40), place: (b.place || "").slice(0, 200), deadline: b.deadline || "", link: (b.link || "").trim().slice(0, 500),
    contact: (b.contact || "").trim().slice(0, 200), lang: b.lang || "tr", wants: (b.wants || []).filter(x => ["bulten", "telegram", "duyuru"].includes(x)),
    files, institution: b.institution || u.institution, sender: u.username, sender_name: b.sender_name || u.name, status: "yeni", note: "", created: nowIso(), history: [] };
  s.history.push({ at: s.created, who: s.sender_name, action: "gönderildi" });
  return subSave(s);
}

/* ------------------------------------------------------------------ Telegram (jeton yalnızca bu tarayıcıda) */
const tgCfg = () => clone(Store.get("tt/tg") || { channels: [], log: [] });
function tgStatus() {
  const c = tgCfg(), bot = TT.lsGet("tt-tg-bot");
  return { connected: !!TT.lsGet("tt-tg-token"), bot: bot ? JSON.parse(bot) : null, channels: c.channels || [], log: (c.log || []).slice(-30) };
}
async function tgCall(method, data, token) {
  token = token || TT.lsGet("tt-tg-token") || fail("Önce bot jetonunu girin.");
  let r;
  try { r = await fetch(`https://api.telegram.org/bot${token}/${method}`, { method: "POST", body: data }); }
  catch (e) { fail(Store.mode === "db" ? "claude.ai güvenlik kuralları Telegram'a doğrudan bağlantıya izin vermiyor. Dosyayı ⬇ indirip Telegram'da paylaşın ya da Vercel sürümünden gönderin." : "Telegram'a ulaşılamadı: " + e.message); }
  const j = await r.json();
  if (!j.ok) fail(j.description || "Telegram hatası");
  return j.result;
}
const fd = o => { const f = new FormData(); Object.entries(o).forEach(([k, v]) => v != null && f.append(k, v)); return f; };
async function telegram(op, b, w) {
  const c = tgCfg();
  if (op === "connect") {
    const token = String(b.token || "").trim();
    const meR = await tgCall("getMe", fd({}), token);
    TT.lsSet("tt-tg-token", token); TT.lsSet("tt-tg-bot", JSON.stringify({ username: meR.username, name: meR.first_name }));
    return tgStatus();
  }
  if (op === "disconnect") { TT.lsSet("tt-tg-token", null); TT.lsSet("tt-tg-bot", null); return tgStatus(); }
  if (op === "channel") {
    let id = String(b.chat_id || "").trim().replace(/^https?:\/\/t\.me\//, "@");
    if (!id) fail("Kanal adı gerekli.");
    if (!id.startsWith("@") && !/^-?\d+$/.test(id)) id = "@" + id;
    const chat = await tgCall("getChat", fd({ chat_id: id }));
    if (!c.channels.some(x => String(x.id) === String(chat.id))) c.channels.push({ id: chat.id, title: chat.title || chat.username || id, username: chat.username, type: chat.type, enabled: true });
    await Store.set("tt/tg", c); return tgStatus();
  }
  if (op === "channel-update") {
    c.channels = c.channels.filter(x => !(String(x.id) === String(b.id) && b.remove));
    c.channels.forEach(x => { if (String(x.id) === String(b.id) && b.enabled != null) x.enabled = !!b.enabled; });
    await Store.set("tt/tg", c); return tgStatus();
  }
  if (op === "send") {
    const url = fileUrl(b.ref), name = decodeURIComponent(b.ref.split(":").slice(1).join(":").split("/").pop());
    const blob = await (await fetch(url)).blob();
    const chans = c.channels.filter(x => (b.channels || []).map(String).includes(String(x.id)));
    if (!chans.length) fail("Kanal seçin.");
    const isImg = /\.(png|jpe?g|webp)$/i.test(name), isVid = /\.mp4$/i.test(name);
    const results = [];
    for (const ch of chans) {
      try {
        const m = isImg ? "sendPhoto" : isVid ? "sendVideo" : "sendDocument", field = isImg ? "photo" : isVid ? "video" : "document";
        const f = new FormData(); f.append("chat_id", ch.id); if (b.caption) f.append("caption", String(b.caption).slice(0, 1024)); f.append(field, blob, name);
        const res = await tgCall(m, f);
        results.push({ channel: ch.title, ok: true, link: ch.username ? `https://t.me/${ch.username}/${res.message_id}` : null });
      } catch (e) { results.push({ channel: ch.title, ok: false, error: e.message }); }
    }
    c.log = (c.log || []).concat(results.map(r => ({ at: nowIso(), who: w, file: name, ...r }))).slice(-100);
    await Store.set("tt/tg", c);
    await log(w, `Telegram: ${name} -> ${results.filter(r => r.ok).length}/${results.length} kanal`);
    return { results, status: tgStatus() };
  }
  fail("bilinmeyen işlem");
}

/* ------------------------------------------------------------------ yönlendirici */
/* ------------------------------------------------------------------ haber akışı → Türkçe → bülten */
// Doğruluk kuralı: çeviriyi yalnızca Claude yapar (makine çevirisi yedeği yok); rakamlar kaynakla karşılaştırılır.
const digitsOf = s => (String(s).match(NUM) || []).map(n => n.replace(/\D/g, "")).filter(n => n.length >= 2);
function numDiff(src, tr, titleOnly) {  // titleOnly: özet çevrilmemiş, yalnızca "kaynakta yok" denetlenir
  if (!tr.trim()) return [];
  const s = new Set(digitsOf(src)), b = new Set(digitsOf(tr)), out = [];
  if (!titleOnly) s.forEach(n => { if (!b.has(n)) out.push(`'${n}' çeviride yok`); });
  b.forEach(n => { if (!s.has(n)) out.push(`'${n}' kaynakta yok`); });
  return out;
}
function trCache() { return (Store.get("tt/ceviri") || {}).map || {}; }
async function feedTranslate(ids) {
  if (!(await TT.aiAvailable())) return { done: 0, message: "Claude kullanılamıyor; haberler özgün dilinde gösteriliyor." };
  const tr = trCache(), rows = feedItems().filter(r => ids.includes(r.id) && r.lang !== "tr" && !(tr[r.id] && tr[r.id].s) && !r.summary_tr).slice(0, 25);
  if (!rows.length) return { done: 0 };
  const src = rows.map(r => ({ id: r.id, dil: r.lang, baslik: r.title, ozet: (r.text || r.summary || "").slice(0, 600) }));
  const out = await TT.ai(`Aşağıdaki haber başlıklarını ve özetlerini Türkçeye çevir.
Kurallar: Yalnızca çevir; bilgi ekleme, çıkarma ya da yorum yapma. Bütün rakamları, yüzdeleri, tarihleri, para birimlerini, kişi ve kurum adlarını kaynaktaki gibi koru (ondalık ayırıcı virgül: 7,8). Kurum adlarında Türkçe yerleşik karşılığı kullan; emin değilsen özgün adı yaz. Başlık tek cümle, haber başlığı üslubunda olsun.
${TT.GLOSSARY}
Biçim: {"items":[{"id":"...","t":"Türkçe başlık","s":"Türkçe özet"}]}

${JSON.stringify(src)}`, { json: true, tier: "default" });
  const fresh = Store.get("tt/ceviri") || { map: {} };
  let done = 0;
  (out.items || []).forEach(x => {
    const r = rows.find(y => y.id === x.id); if (!r || !x.t) return;
    const warn = numDiff(r.title + " " + (r.text || r.summary || "").slice(0, 600), x.t + " " + (x.s || ""));
    fresh.map[r.id] = { t: x.t, s: x.s || "", by: "claude", warn, at: nowIso() }; done++;
  });
  await Store.set("tt/ceviri", fresh);
  return { done };
}
async function feedPhoto(r) {
  if (!r.thumb) return null;
  const credit = r.publisher || r.source;
  try {
    let res = await fetch(r.thumb, { mode: "cors" }).catch(() => null);
    if ((!res || !res.ok) && Store.mode !== "db") res = await fetch("api/resim?u=" + encodeURIComponent(r.thumb)).catch(() => null);  // Vercel sürümü
    if (!res || !res.ok) throw new Error("indirilemedi");
    const blob = await res.blob();
    if (!/^image\//.test(blob.type) || blob.size < 2000) throw new Error("görsel değil");
    const ext = ({ "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif" })[blob.type] || ".jpg";
    const name = `haber-${r.id}${ext}`;
    await putFile("img:" + name, name, blob);
    return { file: name, credit, url: r.thumb, show: sourceCfg().photos !== false };
  } catch (e) {
    return { file: null, src: r.thumb, credit, url: r.thumb, show: sourceCfg().photos !== false };  // tarayıcı indiremezse doğrudan bağlantı
  }
}
async function feedToItems(ids) {
  const rows = ids.map(id => feedItems().find(r => r.id === id)).filter(Boolean);
  if (!rows.length) fail("Haber bulunamadı.");
  await feedTranslate(rows.map(r => r.id)).catch(() => {});
  const tr = trCache();
  // kaynak metin, rakam denetimi ve editördeki "Kaynak metin" sekmesi için aday olarak saklanır
  const fc = Store.get("tt/fcands") || { list: [] };
  const cands = rows.map(r => {
    const c = { cid: "f-" + r.id, title: r.title, text: r.text || r.summary || "", source: r.source, url: r.url, lang: r.lang, published: r.published, score: 0 };
    fc.list = fc.list.filter(x => x.cid !== c.cid).concat([c]);
    return c;
  });
  await Store.set("tt/fcands", fc);
  let items;
  if (await TT.aiAvailable()) {
    if (window.toast) window.toast(`Claude ${rows.length} haberi bülten üslubunda yazıyor…`);
    const body = cands.map(c => `<aday id="${c.cid}" kaynak="${c.source}" dil="${c.lang}" tarih="${c.published}" url="${c.url}">\nBAŞLIK: ${c.title}\n${c.text}\n</aday>`).join("\n");
    const out = await TT.ai(`${TT.STYLE_GUIDE}\n\nEditör aşağıdaki ${cands.length} haberi bültene eklemek için seçti. Her aday için AYRI bir haber yaz (birleştirme, eleme yapma; sıra aynı kalsın). YALNIZCA aday metnindeki bilgileri kullan: kaynakta geçmeyen rakam, tarih, isim veya yorum ekleme. Kaynak kısa ise metin de kısa olsun (1-2 paragraf). "X sitesinin … tarihli haberine göre" gibi kaynak ve tarih cümlesi yazma; kaynak ayrıca listelenir.\n${TT.GLOSSARY}\n\n${body}\n\nÇıktı biçimi: ${TT.ITEM_SHAPE}`, { json: true });
    items = (out.items || []).slice(0, cands.length);
    if (items.length !== cands.length) fail("Claude haberlerin hepsini yazmadı; yeniden deneyin.");
    items.forEach(it => { it.paragraphs = (it.paragraphs || []).map(cleanLead).filter(Boolean); });
  } else {
    items = cands.map(c => { const x = tr[c.cid.slice(2)] || {}; const r = rows.find(y => "f-" + y.id === c.cid);
      return { headline: r.title_tr || x.t || c.title, paragraphs: [r.summary_tr || x.s || c.text], category: "diğer" }; });
  }
  for (let i = 0; i < items.length; i++) {
    const it = items[i], r = rows[i];
    it.candidate_ids = [cands[i].cid];
    it.sources = [{ name: r.publisher || r.source, url: r.url }];
    it.category = it.category || "diğer";
    const ph = await feedPhoto(r);
    if (ph) it.photo = ph;
  }
  return items;
}

/* ------------------------------------------------------------------ sunum ve video (tarayıcıda) */
const jobs = { deck: {}, video: {} };
function media() { return Store.get("tt/media") || { decks: [], videos: [], slides: [] }; }
async function addMedia(kind, doc) {
  const m = media();
  m[kind] = [doc].concat((m[kind] || []).filter(x => x.ref !== doc.ref));
  await Store.set("tt/media", m);
}
async function slidesFor(lang, job) {
  const d = lang === "tr" ? drafts() : langDrafts(lang);
  if (!d || !d.items.length) fail("Bültende haber yok.");
  const pngs = [];
  const total = d.items.length + 1;
  job.total = total * (job.kind === "video" ? 2 : 1); job.step = 0;
  for (let i = 0; i <= d.items.length; i++) {
    job.message = i ? `Slayt ${i + 1}/${total}: ${d.items[i - 1].headline.slice(0, 50)}` : "Kapak slaytı";
    pngs.push(await TT.slidePng(d, i, B.state.issue, lang));
    job.step++;
  }
  return pngs;
}
function runJob(kind, fn) {
  if (jobs[kind].state === "çalışıyor") return jobs[kind];
  const job = jobs[kind] = { kind, state: "çalışıyor", step: 0, total: 1, message: "Başlıyor…" };
  fn(job).then(() => { job.state = "bitti"; job.step = job.total; job.message = "Hazır"; })
    .catch(e => { console.error(e); job.state = "hata"; job.message = e.message || String(e); });
  return job;
}
function deckStart(lang, w) {
  return runJob("deck", async job => {
    const L = TT.labels().B[lang];
    const pngs = await slidesFor(lang, job);
    job.message = "PDF birleştiriliyor";
    const blob = await TT.slidesPdf(pngs);
    const name = `${L.doc_title}-${B.state.issue}-${lang}-sunum.pdf`;
    const doc = await putFile("deck:" + name, name, blob);
    await addMedia("decks", { name, ref: "deck:" + name, size_kb: doc.size_kb, modified: doc.modified });
    if (lang === "tr") {
      const names = [];
      for (let i = 0; i < pngs.length; i++) { const n = `slayt-${String(i).padStart(2, "0")}.png`; await putFile("slide:" + n, n, pngs[i]); names.push(n); }
      const m = media(); m.slides = names; await Store.set("tt/media", m);
    }
    await log(w, `sunum üretildi (${lang.toUpperCase()}, ${pngs.length} slayt)`);
  });
}
function videoStart(lang, seconds, w) {
  return runJob("video", async job => {
    const L = TT.labels().B[lang];
    const pngs = await slidesFor(lang, job);
    const blob = await TT.slidesVideo(pngs, Math.max(3, Math.min(20, seconds || 8)), (i, n) => { job.step = n + i; job.message = `Video kaydediliyor: slayt ${i + 1}/${n}`; });
    const name = `${L.doc_title}-${B.state.issue}-${lang}.webm`;
    const doc = await putFile("video:" + name, name, blob);
    await addMedia("videos", { name, ref: "video:" + name, size_kb: doc.size_kb, modified: doc.modified });
    await log(w, `video üretildi (${lang.toUpperCase()}, seslendirmesiz)`);
  });
}

async function route(path, body) {
  const url = new URL(path, "http://x"), p = url.pathname, q = k => url.searchParams.get(k);
  const w = who(body);
  if (body === undefined) {  // GET
    switch (p) {
      case "/api/state": return state();
      case "/api/feed": return feedRows();
      case "/api/search": return search(q("q") || "");
      case "/api/rates": return B.rates;
      case "/api/video/status": return jobs.video;
      case "/api/deck/status": return jobs.deck;
      case "/api/web": return { built: null, files: 0, mb: 0, job: {}, settings: await settingsStatus() };
      case "/api/inst": return institutions();
      case "/api/ann/special": return specialDays(q("lang") || "tr");
      case "/api/ann/list": return annList();
      case "/api/voices": return [];
      case "/api/settings": return settingsStatus();
      case "/api/telegram": return tgStatus();
      case "/api/report-types": return B["report-types"];
      case "/api/reports": return repList();
      case "/api/report": return repLoad(q("id"));
      case "/api/sub/all": return { items: Store.list("gelen").sort((a, b) => b.created.localeCompare(a.created)), statuses: IB_STATUSES, types: IB_TYPES };
      case "/api/sub/mine": { const u = await me(); return Store.list("gelen").filter(s => s.sender === u.username).sort((a, b) => b.created.localeCompare(a.created)); }
      case "/api/me": return me();
      case "/api/users": return { users: clone((Store.get("tt/users") || {}).users || []), network: { lan: false }, ip: null, port: 0, bound: "web" };
      case "/api/setup-status": return { needed: false };
    }
    fail("bulunamadı");
  }
  // POST
  if (p.startsWith("/api/telegram/")) return telegram(p.slice(14), body, w);
  if (p.startsWith("/api/ann/")) {
    const op = p.slice(9);
    if (op === "new") { const a = await annNew(body.kind, body.lang); await log(w, `yeni ${body.kind || "etkinlik"} oluşturuldu`); return a; }
    if (op === "save") return annUpdate(body.id, body);
    if (op === "delete") { await Store.set("ann/" + body.id, { id: body.id, deleted: true }); await log(w, "duyuru silindi"); return { ok: true }; }
    if (op === "photo") return annPhoto(body);
    if (op === "produce") { const files = await annProduce(body.id, body.fmts || ["kare"]); await log(w, "duyuru tasarımı üretildi: " + (body.fmts || ["kare"]).join(", ")); return { files }; }
    if (op === "special") { const a = await fromSpecial(body.key, body.lang || "tr"); await log(w, `özel gün kartı oluşturuldu: ${a.title.slice(0, 50)}`); return a; }
    if (op === "translate") { const b2 = await annTranslate(body.id, body.lang); await log(w, `duyuru ${body.lang.toUpperCase()} diline çevrildi`); return b2; }
    fail("bilinmeyen işlem");
  }
  if (p.startsWith("/api/report")) {
    if (p === "/api/report/create") return repCreate(body.type, body.params || {}, w);
    const rep = await repLoad(body.id);
    if (p === "/api/report/save") {
      const ed = Object.fromEntries((body.sections || []).map(s => [s.id, s]));
      rep.sections.forEach(s => { if (ed[s.id]) ["title", "text", "status"].forEach(k => { if (k in ed[s.id]) s[k] = ed[s.id][k]; }); });
      repLog(rep, w, `kaydedildi (${Object.keys(ed).length} bölüm)`);
      return repSave(rep);
    }
    if (p === "/api/report/refresh") fail("Resmî veri kaynaklarını (UN Comtrade, Dünya Bankası, SIAT) tarama sunucu sürümünde çalışır; tarayıcıdaki bu sürüm bu sitelere doğrudan bağlanamaz. Sunucu kurulunca tablolar günde bir kez kendiliğinden de yenilenir.");
    if (p === "/api/report/import") return repImport(rep, TT.dataUrlToBlob(body.data), w);
    if (p === "/api/report/render") return repRender(rep, w);
    if (p === "/api/report/source") {
      rep.refs = rep.refs || [];
      if (body.remove) { rep.refs = rep.refs.filter(r => r.id !== body.remove); repLog(rep, w, "kaynak silindi"); return repSave(rep); }
      const a = body.add || {}, name = String(a.name || "").trim();
      if (!name) fail("Kaynağın adını yazın.");
      if (a.url && !/^https?:\/\//.test(a.url)) fail("Bağlantı http:// veya https:// ile başlamalı.");
      const ref = { id: "k" + Date.now().toString(36), name, url: a.url || "", note: String(a.note || "").trim(), added: nowIso(), by: w };
      if (a.data && a.filename) { const fn = String(a.filename).replace(/[^\w.\-]+/g, "_"); ref.file = `repsrc:${rep.id}/${ref.id}-${fn}`; ref.filename = fn;
        await putFile(ref.file, fn, TT.dataUrlToBlob(a.data), { group: "kaynak" }); }
      rep.refs.push(ref); repLog(rep, w, "kaynak eklendi: " + name); return repSave(rep);
    }
    if (p === "/api/report/ai") return repAi(rep, body.sid, w);
    fail("bilinmeyen işlem");
  }
  switch (p) {
    case "/api/inst/message": {
      const msgs = instMsgs();
      let out = msgs;
      if (body.op === "delete") out = msgs.filter(m => m.id !== body.id);
      else {
        if (!(body.title || "").trim()) fail("Başlık gerekli.");
        let att = null;
        if (body.attachment && body.attachment.data) { const nm = String(body.attachment.name || "ek").replace(/[^\w.\-]+/g, "_"); att = `upload:${nm}`; await putFile(att, nm, TT.dataUrlToBlob(body.attachment.data)); }
        out = msgs.concat([{ id: "m" + nowIso().replace(/\D/g, ""), institution: body.institution, title: body.title.trim(), date: body.date || todayIso(),
          text: (body.text || "").trim(), link: (body.link || "").trim() || null, attachment: att || body.attachment || null, who: w }]);
      }
      await Store.set("tt/inst", { msgs: out });
      await log(w, "temsilcilik mesajı " + (body.op === "delete" ? "silindi" : "eklendi"));
      return institutions();
    }
    case "/api/inst/to-bulletin": {
      const f = institutions().feed.find(x => x.id === body.id) || fail("Kayıt bulunamadı.");
      const text = String(f.summary || "").replace(/\s+/g, " ").trim();
      const n = await addToBulletin({ headline: f.title.replace(/\.$/, "") + ".", paragraphs: [text || ""], category: "diğer", candidate_ids: [],
        source_text: f.title + " " + (f.summary || ""), sources: [{ name: f.publisher || instName(f.inst) || f.source, url: f.url || "" }] }, w, `temsilcilik haberi bültene eklendi: ${f.title.slice(0, 60)}`);
      return { n, state: await state() };
    }
    case "/api/inst/to-ann": {
      const f = institutions().feed.find(x => x.id === body.id) || fail("Kayıt bulunamadı.");
      const a = await annNew("duyuru", "tr");
      const ins = B.inst.institutions.find(i => i.key === f.inst);
      const r = await annUpdate(a.id, { title: f.title.slice(0, 140), text: (f.summary || "").slice(0, 700), link: f.url || "", tag: ins ? ins.short : "" });
      await log(w, `temsilcilik haberi duyuruya dönüştürüldü: ${f.title.slice(0, 60)}`);
      return r;
    }
    case "/api/sub/new": { const s = await subNew(body); await log(s.sender_name, `yeni bilgi gönderdi: ${s.title.slice(0, 60)}`); return s; }
    case "/api/sub/status": {
      if (!IB_STATUSES[body.status]) fail("Geçersiz durum.");
      const s = subLoad(body.id); s.status = body.status; if (body.note != null) s.note = String(body.note).trim().slice(0, 1000);
      s.history.push({ at: nowIso(), who: w, action: IB_STATUSES[body.status] + (body.note ? ` – ${body.note.trim()}` : "") });
      return subSave(s);
    }
    case "/api/sub/to-bulletin": {
      const s = subLoad(body.id);
      const paras = s.text.split(/\n\s*\n/).map(x => x.trim()).filter(Boolean);
      const item = { headline: s.title.replace(/\.$/, "") + ".", paragraphs: paras.length ? paras : [""], category: "diğer", candidate_ids: [],
                     source_text: s.title + " " + s.text, sources: [{ name: instName(s.institution), url: s.link || "" }] };
      const img = s.files.find(f => /\.(jpe?g|png|webp)$/i.test(f));
      if (img) {
        const fname = `gelen-${s.id}${img.match(/\.\w+$/)[0].toLowerCase()}`;
        const d = fileDoc(`sub:${s.id}/${img}`);
        if (d) await Store.set("files/" + dslug("img:" + fname), { ...d, ref: "img:" + fname, name: fname });
        item.photo = { file: fname, credit: instName(s.institution), url: "", show: true };
      }
      const n = await addToBulletin(item, w, `gelen bilgi bültene eklendi: ${s.title.slice(0, 60)}`);
      s.status = "yayina_alindi"; s.history.push({ at: nowIso(), who: w, action: `bültene ${n}. haber olarak eklendi` }); await subSave(s);
      return { n, state: await state() };
    }
    case "/api/sub/to-ann": {
      const s = subLoad(body.id);
      const kind = { etkinlik: "etkinlik", duyuru: "duyuru", haber: "haber" }[s.type] || "duyuru";
      const a = await annNew(kind, s.lang || "tr");
      const vals = Object.fromEntries(["title", "text", "date", "date_end", "time", "place", "deadline", "link", "contact"].map(k => [k, s[k] || ""]));
      vals.tag = instName(s.institution).split(" ")[0];
      const img = s.files.find(f => /\.(jpe?g|png|webp)$/i.test(f));
      if (img) { const ext = img.match(/\.\w+$/)[0].toLowerCase(), d = fileDoc(`sub:${s.id}/${img}`); if (d) { await Store.set("files/" + dslug(`ann:${a.id}/foto${ext}`), { ...d, ref: `ann:${a.id}/foto${ext}`, name: `foto${ext}` }); vals.photo = `foto${ext}`; } }
      const r = await annUpdate(a.id, vals);
      s.status = "inceleniyor"; s.history.push({ at: nowIso(), who: w, action: "duyuru tasarımı hazırlanıyor" }); await subSave(s);
      await log(w, `gelen bilgi duyuruya dönüştürüldü: ${s.title.slice(0, 60)}`);
      return r;
    }
    case "/api/users": {
      const u = clone((Store.get("tt/users") || {}).users || []);
      let out = u;
      if (body.op === "add") {
        const name = String(body.username || "").trim();
        if (!name) fail("Kullanıcı adı gerekli.");
        if (u.some(x => x.username === name)) fail("Bu kullanıcı zaten var.");
        out = u.concat([{ username: name, name: body.name || "", role: body.role || "birim", institution: body.institution, last_login: null }]);
      } else if (body.op === "delete") out = u.filter(x => x.username !== body.username);
      else if (body.op === "password") fail("Web sürümünde giriş claude.ai hesabıyla yapılır; şifre kullanılmaz. Erişimi yayının Paylaş menüsünden verin.");
      else if (body.op === "network") fail("Web sürümü zaten her bilgisayardan açılır; ağ ayarı gerekmez.");
      await Store.set("tt/users", { users: out });
      await log(w, `kullanıcı ayarı: ${body.op}`);
      return { users: out, network: { lan: false }, ip: null, port: 0, bound: "web" };
    }
    case "/api/logout": return { ok: true };
    case "/api/upload": {
      const name = String(body.name || "").split(/[\\/]/).pop();
      if (!/\.(pdf|png|jpe?g|mp4)$/i.test(name)) fail("Yalnızca PDF, görsel ve MP4 yüklenebilir.");
      const blob = TT.dataUrlToBlob(body.data);
      const extra = /\.pdf$/i.test(name) ? { group: "yüklenen", pages: await TT.pdfPageCount(blob).catch(() => 1) } : {};
      await putFile("upload:" + name, name, blob, extra);
      await log(w, `dosya yüklendi: ${name}`);
      return { ref: "upload:" + name, state: await state() };
    }
    case "/api/save": await saveItems(body.items, w); return state();
    case "/api/editor-pdf": await renderBulletin("tr", true); await log(w, "editör PDF'i üretildi"); return state();
    case "/api/deck/start": return deckStart(body.lang || "tr", w);
    case "/api/video/start": return videoStart(body.lang || "tr", body.seconds, w);
    case "/api/tts/sample":
      fail("Seslendirme yalnızca Mac'teki masaüstü panelde yapılır; burada video seslendirmesiz üretilir.");
    case "/api/feed/translate": return feedTranslate(body.ids || []);
    case "/api/feed/to-items": return { items: await feedToItems(body.ids || []) };
    case "/api/settings": {
      if ("anthropic_api_key" in body) { const v = String(body.anthropic_api_key || "").trim(); if (v) TT.lsSet("tt-anthropic-key", v); else if (body.clear_anthropic_api_key) TT.lsSet("tt-anthropic-key", null); }
      if ("azure_speech_key" in body) fail("Seslendirme yalnızca Mac'teki panelde kullanılır.");
      return settingsStatus();
    }
    case "/api/sources/update": await sourcesUpdate(body, w); return state();
    case "/api/feed/read": return feedRead(body.id);
    case "/api/auto/pick": return autoPick(body.count);
    case "/api/auto/learn": { await autoLearn(body.files || [], w); return autoState(); }
    case "/api/auto/save": { const c = autoCfg(); ["enabled", "days", "time", "count"].forEach(k => { if (k in body) c[k] = body[k]; });
      c.count = Math.max(3, Math.min(25, +c.count || 10)); await Store.set("tt/auto", c); await log(w, "otomatik bülten ayarlandı"); return autoState(); }
    case "/api/file/delete": { const d = fileDocs().find(x => x.ref === body.ref); if (!d || !/^(issue|report):/.test(d.ref)) fail("Dosya bulunamadı.");
      await Store.del("files/" + dslug(body.ref)); await log(w, "dosya silindi: " + d.name); return { ok: true }; }
    case "/api/scan": { const r = await scan(w); return { ...r, state: await state() }; }
    case "/api/image": {
      const nm = String(body.name || "gorsel").replace(/[^\w-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "gorsel";
      const fname = `${nm}-${nowIso().slice(11).replace(/:/g, "")}.png`;
      await putFile("img:" + fname, fname, TT.dataUrlToBlob(body.data));
      await log(w, `görsel kaydedildi: ${fname}`);
      return { file: fname, state: await state() };
    }
    case "/api/translate": await translate(body.lang, w); return state();
    case "/api/write-item": return { item: await writeItem(body.cid) };
    case "/api/approve": await approve(w); return state();
    case "/api/web/build": case "/api/web/deploy": fail("Bu panel zaten web'de yayında.");
  }
  fail("bulunamadı");
}

/* ------------------------------------------------------------------ bağlantılar (src/href) ve önizlemeler */
const BLANK = "data:image/svg+xml;charset=utf-8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="14"><rect width="10" height="14" fill="#f3efec"/></svg>');
function url(u) {
  if (!u || /^(https?:|data:|blob:|#|mailto:|about:|javascript:)/.test(u) || u.startsWith("d/") || u.startsWith("static/") || u.startsWith("/_blob/")) return u;
  const x = new URL(u, "http://x"), q = k => x.searchParams.get(k) || "", p = x.pathname;
  if (p === "/file") return fileUrl(q("ref"));
  if (p.startsWith("/img/")) return fileUrl("img:" + decodeURIComponent(p.slice(5)));
  if (p.startsWith("/static/")) return p.slice(1);
  if (p === "/onizleme" || p.startsWith("/onizleme/")) return "./";
  if (p === "/giris" || p === "/") return "./";
  return u;
}
TT.url = url;
async function viewHtml(u) {
  const x = new URL(u, "http://x"), q = k => x.searchParams.get(k) || "", p = x.pathname;
  if (p === "/preview") {
    const lang = q("lang") || "tr", d = lang === "tr" ? check(drafts()) : langDrafts(lang);
    if (!d) return `<p style="font:14px sans-serif;padding:20px">${lang.toUpperCase()} çevirisi henüz yok.</p>`;
    return TT.bulletinHtml(d, B.state.issue, lang, lang === "tr", B.rates);
  }
  if (p === "/report-preview") return TT.reportHtml(await repLoad(q("id")));
  if (p === "/ann-preview") { const a = annLoad(q("id")); return a ? TT.annHtml(a, q("fmt") || "kare", annPhotoUrl(a)) : ""; }
  return null;
}
const thumbObs = new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting && e.target._ttThumb) { const f = e.target._ttThumb; e.target._ttThumb = null; thumbObs.unobserve(e.target); f(); }
}), { rootMargin: "600px" });
function fixEl(el, attr, v) {
  if (el.dataset && el.dataset.ttv === v) return;
  if (el.tagName === "IFRAME" && attr === "src" && /^\/(preview|report-preview|ann-preview)\?/.test(v)) {
    el.dataset.ttv = v;
    // Başlamış gezinmeyi about:blank ile kes, sonra içeriği doğrudan yaz
    const loaded = new Promise(r => { el.addEventListener("load", r, { once: true }); setTimeout(r, 1500); });
    el.setAttribute("src", "about:blank");
    Promise.all([viewHtml(v), loaded]).then(([html]) => {
      if (el.dataset.ttv !== v || html == null) return;
      const d = el.contentDocument; if (!d) return;
      d.open(); d.write(html); d.close();
    }).catch(e => window.toast && window.toast(e.message, true));
    return;
  }
  if (el.tagName === "IMG" && attr === "src" && v.startsWith("/pdfpage?")) {
    // PDF sayfa görüntüleri tarayıcıda (pdf.js) çizilir; yalnızca ekrana gelince
    const x = new URL(v, "http://x"), ref = x.searchParams.get("ref"), page = +(x.searchParams.get("page") || 0), w = +(x.searchParams.get("w") || 600);
    el.dataset.ttv = v;
    el.setAttribute("src", BLANK);
    if (!el.style.minHeight && w > 600) el.style.minHeight = "400px";
    el._ttThumb = () => TT.pdfThumb(fileUrl(ref), page, w > 600 ? 1100 : 420).then(du => {
      if (el.dataset.ttv === v) { el.dataset.ttv = du; el.setAttribute("src", du); el.style.minHeight = ""; }
    }).catch(() => {});
    thumbObs.observe(el);
    return;
  }
  const n = url(v);
  if (n !== v) el.setAttribute(attr, n);
}

Object.assign(TT, { init, api: route, url, fixEl, state, annList, annProduce, annNew, annUpdate, fromSpecial, specialDays, drafts, annOutputs,
  base: B, putFile, log, feedItems });
})();
