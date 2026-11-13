/* Taşkent Ticaret Müşavirliği paneli – tarayıcıda çalışan arka uç.
 *
 * Orijinal panel (static/panel.html) Python sunucusuyla konuşur; bu dosya aynı /api/... uçlarını
 * tarayıcıda yanıtlar. Başlangıç içeriği api/*.json ve d/ klasöründeki anlık görüntüdür; üzerine
 * yapılan her değişiklik ortak veritabanında (claude.ai yayınında) ya da bu tarayıcıda (Vercel /
 * başka sunucu) saklanır. Gizli anahtarlar (Claude, Telegram) yalnızca bu tarayıcıda kalır.
 */
(function () {
"use strict";

const LANGS = ["tr", "en", "ru", "uz"];
const clone = x => JSON.parse(JSON.stringify(x));
const pad = n => String(n).padStart(2, "0");
function nowIso(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
const todayIso = () => nowIso().slice(0, 10);
const dslug = r => String(r).replace(/[^a-zA-Z0-9._-]+/g, "_");
const H = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&#34;", "'": "&#39;" }[c]));
const TRMAP = { ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", Ç: "C", Ğ: "G", İ: "I", Ö: "O", Ş: "S", Ü: "U" };
const asciiSlug = s => String(s).replace(/[çğıöşüÇĞİÖŞÜ]/g, c => TRMAP[c]).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const fail = msg => { throw new Error(msg); };
const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
const lsSet = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} };
function newId() { return nowIso().replace(/[-:]/g, "").replace("T", "-") + "-" + Math.random().toString(16).slice(2, 6); }

async function sha12(obj) {
  const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(JSON.stringify(obj)));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}
const contentHash = d => sha12(d.items.map(it => [it.headline, it.paragraphs, it.sources]));
const approvalHash = d => sha12(d.items.map(it => [it.headline, it.paragraphs, it.sources, it.image || null, it.image_caption || null, it.photo || null, it.videos || null]));

/* ------------------------------------------------------------------ yetenekler (claude.ai) */
const caps = {};
function cap(name) {
  if (!(name in caps)) caps[name] = (window.claude && window.claude.use ? window.claude.use(name) : Promise.resolve(null)).catch(() => null);
  return caps[name];
}

/* ------------------------------------------------------------------ kayıt deposu
 * Ortak veritabanı varsa (claude.ai) belgeler ortak; yoksa bu tarayıcının localStorage'ı.
 * Bellekte bir ayna tutulur: okumalar anlık, yazmalar arka planda. */
const COLLS = ["tt", "ann", "rep", "files", "feed", "gelen"];
const Store = {
  docs: {}, mode: "local", db: null, listeners: [],
  get(p) { return this.docs[p]; },
  list(c) { return Object.entries(this.docs).filter(([k]) => k.startsWith(c + "/")).map(([k, v]) => ({ id: k.slice(c.length + 1), ...v })); },
  async set(p, data) {
    data = clone(data);
    this.docs[p] = data;
    if (this.mode === "db") await this.db.doc(p).set(data);
    else lsSet("tt:" + p, JSON.stringify(data));
    this.changed();
  },
  async del(p) {
    delete this.docs[p];
    if (this.mode === "db") await this.db.doc(p).delete();
    else lsSet("tt:" + p, null);
    this.changed();
  },
  changed() { this.ver = (this.ver || 0) + 1; this.listeners.forEach(f => { try { f(); } catch (e) {} }); },
  async init() {
    const db = await Promise.race([cap("db"), new Promise(r => setTimeout(() => r(null), 4000))]);
    if (db) {
      this.mode = "db"; this.db = db;
      await Promise.all(COLLS.map(c => new Promise(resolve => {
        let first = true;
        db.collection(c).onSnapshot(qs => {
          qs.docChanges().forEach(ch => {
            const p = c + "/" + ch.doc.id;
            if (ch.type === "removed") delete this.docs[p]; else this.docs[p] = clone(ch.doc.data());
          });
          if (first) { first = false; resolve(); } else this.changed();
        }, () => { if (first) { first = false; resolve(); } });
        setTimeout(() => { if (first) { first = false; resolve(); } }, 6000);
      })));
    } else {
      // Vercel paketi: ilk açılışta claude.ai'den aktarılan veriler (veri/canli.json) bu tarayıcıya yüklenir
      try {
        const r = await fetch("veri/canli.json", { cache: "no-cache" });
        if (r.ok) {
          const seed = await r.json();
          window.TT_BLOB_EXT = seed.blobs || {};
          if (lsGet("tt-seeded") !== seed.exported) {
            Object.entries(seed.docs || {}).forEach(([k, v]) => { if (localStorage.getItem("tt:" + k) === null) lsSet("tt:" + k, JSON.stringify(v)); });
            lsSet("tt-seeded", seed.exported);
          }
        }
      } catch (e) {}
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k && k.startsWith("tt:")) this.docs[k.slice(3)] = JSON.parse(localStorage.getItem(k));
        }
      } catch (e) {}
      window.addEventListener("storage", e => {
        if (e.key && e.key.startsWith("tt:")) { if (e.newValue) this.docs[e.key.slice(3)] = JSON.parse(e.newValue); else delete this.docs[e.key.slice(3)]; this.changed(); }
      });
    }
  },
};

/* ------------------------------------------------------------------ dosya deposu (PDF, PNG, foto)
 * claude.ai: "assets" (herkes görür). Diğer: tarayıcının IndexedDB'si. Anahtar: "a:<id>" | "l:<id>" */
const Blobs = {
  urls: {}, idb: null,
  async open() {
    if (this.idb) return this.idb;
    this.idb = await new Promise((ok, err) => {
      const r = indexedDB.open("tt-blobs", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("b");
      r.onsuccess = () => ok(r.result); r.onerror = () => err(r.error);
    });
    return this.idb;
  },
  async init() {
    if (Store.mode === "db") return;
    try {
      const db = await this.open();
      await new Promise(ok => {
        const tx = db.transaction("b", "readonly"), st = tx.objectStore("b"), req = st.openCursor();
        req.onsuccess = () => { const c = req.result; if (!c) return ok(); this.urls["l:" + c.key] = URL.createObjectURL(c.value); c.continue(); };
        req.onerror = () => ok();
      });
    } catch (e) {}
  },
  async put(blob, type) {
    if (type && blob.type !== type) blob = new Blob([blob], { type });
    if (Store.mode === "db") {
      const assets = await cap("assets");
      if (!assets) fail("Dosya kaydetmek için bu yayında düzenleme izni gerekir.");
      try {
        const r = await assets.upload(blob, blob.type ? undefined : { type: "application/octet-stream" });
        this.urls["a:" + r.id] = r.url;
        return "a:" + r.id;
      } catch (e) { fail("Dosya kaydedilemedi: " + (e.message || e.code || e)); }
    }
    const key = Math.random().toString(36).slice(2) + Date.now().toString(36);
    const db = await this.open();
    await new Promise((ok, err) => { const tx = db.transaction("b", "readwrite"); tx.objectStore("b").put(blob, key); tx.oncomplete = ok; tx.onerror = () => err(tx.error); });
    this.urls["l:" + key] = URL.createObjectURL(blob);
    return "l:" + key;
  },
  url(key) {
    if (!key) return "";
    if (this.urls[key]) return this.urls[key];
    if (key.startsWith("a:")) return Store.mode === "db" ? "/_blob/" + key.slice(2) : "d/a/" + key.slice(2) + ((window.TT_BLOB_EXT || {})[key.slice(2)] || "");
    return "";
  },
  async bytes(url) { const r = await fetch(url); if (!r.ok) fail("Dosya okunamadı"); return new Uint8Array(await r.arrayBuffer()); },
};
function dataUrlToBlob(du) {
  const [h, b] = du.split(",", 2), type = (h.match(/data:([^;]+)/) || [])[1] || "application/octet-stream";
  const bin = atob(b), a = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
  return new Blob([a], { type });
}
const MIME = { pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", mp4: "video/mp4", webm: "video/webm", gif: "image/gif",
  doc: "application/msword", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation" };
const mimeOf = n => MIME[(n.split(".").pop() || "").toLowerCase()] || "application/octet-stream";

/* ------------------------------------------------------------------ Claude (yazım, çeviri) */
async function aiAvailable() { return !!(await cap("sample")) || !!lsGet("tt-anthropic-key"); }
async function ai(prompt, { json = false, tier = "default" } = {}) {
  const sample = await cap("sample");
  const p = json ? prompt + "\n\nYanıt olarak YALNIZCA geçerli JSON döndür; açıklama ya da kod bloğu ekleme." : prompt;
  if (sample) {
    try { return json ? await sample.json(p, { modelTier: tier }) : (await sample(p, { modelTier: tier })).text; }
    catch (e) {
      if (e && e.code === "not_granted") fail("Claude kullanımına izin verilmedi.");
      if (e && e.code === "rate_limited") fail("Claude şu an yoğun; biraz sonra yeniden deneyin.");
      if (e && e.code === "invalid_json" && e.text) { const m = e.text.match(/[\[{][\s\S]*[\]}]/); if (m) return JSON.parse(m[0]); }
      fail("Claude yanıt veremedi: " + (e.message || e.code || e));
    }
  }
  const key = lsGet("tt-anthropic-key");
  if (!key) fail("Claude için anahtar gerekli (Yardım → Ayarlar).");
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" },
    body: JSON.stringify({ model: "claude-opus-5-5", max_tokens: 32000, messages: [{ role: "user", content: p }] }),
  });
  const j = await r.json();
  if (!r.ok) fail("Claude hatası: " + ((j.error && j.error.message) || r.status));
  const text = j.content.filter(b => b.type === "text").map(b => b.text).join("");
  if (!json) return text;
  const m = text.match(/[\[{][\s\S]*[\]}]/);
  if (!m) fail("Claude geçerli JSON döndürmedi.");
  return JSON.parse(m[0]);
}

const STYLE_GUIDE = `Sen T.C. Taşkent Büyükelçiliği Ticaret Müşavirliği'nin haftalık
"Ekonomi, Ticaret ve Yatırım ile İlgili Haber Başlıkları" bültenini hazırlayan editörsün.
Okuyucu: Özbekistan'da faaliyet gösteren veya göstermek isteyen Türk iş insanları.

Kurallar:
- Adaylar arasından Türk iş dünyası için en önemli haberleri seç: makro göstergeler,
  uluslararası kuruluş tahminleri, büyük yatırım/ihale projeleri, mevzuat değişiklikleri,
  vergi/gümrük düzenlemeleri, enerji, lojistik, Türkiye-Özbekistan ilişkileri.
  Asayiş, spor, kültür, turistik haberler alınmaz.
- Başlık: Bülten üslubunda, Her Kelimenin İlk Harfi Büyük, sonunda nokta.
  Örnek: "IMF, Özbekistan İçin 2026 Yılında %7,8 Büyüme Öngörüyor."
- Metin: resmi, nesnel, 2-4 paragraf. Kaynakta olmayan hiçbir bilgi, rakam veya yorum
  ekleme. Rakamları kaynaktaki gibi aktar (ondalık ayırıcı virgül: %7,8; para:
  "356 milyon ABD Doları"). Kurum adlarının Türkçe yerleşik karşılıklarını kullan.
- Her haberin kaynaklarını (site adı + URL) belirt.
- Türkiye ile ilgili haberleri önemli say, ama yalnızca gerçekten ilgiliyse.`;
const ITEM_SHAPE = `{"items":[{"headline":"...","paragraphs":["..."],"category":"makro|ticaret|yatırım|enerji|lojistik|mevzuat|finans|türkiye|diğer","candidate_ids":["..."],"sources":[{"name":"...","url":"..."}]}]}`;
const GLOSSARY = `Terim sözlüğü (her zaman bu karşılıkları kullan):
Yeni Taşkent = New Tashkent = Новый Ташкент = Yangi Toshkent
Ticaret Müşavirliği = Commercial Counsellor's Office = Торговое представительство
Dünya Bankası = World Bank = Всемирный банк = Jahon banki`;

window.TT = { Store, Blobs, ai, aiAvailable, cap, H, clone, nowIso, todayIso, dslug, asciiSlug, sha12, contentHash, approvalHash,
  dataUrlToBlob, mimeOf, newId, lsGet, lsSet, fail, LANGS, STYLE_GUIDE, ITEM_SHAPE, GLOSSARY };
})();
