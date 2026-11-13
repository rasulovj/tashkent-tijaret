// Haber toplama servisi: RSS, Atom ve Telegram (t.me/s) kanallarını okur.
// POST { sources: [{ name, url, lang, group }] } -> { items: [...] }
const crypto = require("crypto");
const UA = "Mozilla/5.0 (compatible; TaskentTicaretBot/1.0)";
const DAYS = 10, PER_SOURCE = 25;

const sha12 = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 12);
const ent = s => String(s || "").replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
  .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n)).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
  .replace(/&quot;/g, '"').replace(/&apos;|&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
const strip = s => ent(ent(s).replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, " ").replace(/<br\s*\/?>|<\/p>/gi, "\n").replace(/<[^>]+>/g, " "))
  .replace(/[ \t\r]+/g, " ").replace(/\n\s*/g, "\n").trim();
const tag = (x, t) => { const m = x.match(new RegExp(`<${t}(?:\\s[^>]*)?>([\\s\\S]*?)</${t}>`, "i")); return m ? m[1] : ""; };
const attr = (x, t, a) => { const m = x.match(new RegExp(`<${t}\\b[^>]*\\b${a}=["']([^"']+)["']`, "i")); return m ? ent(m[1]) : ""; };
const iso = d => { const t = Date.parse(d); return isNaN(t) ? null : new Date(t).toISOString().replace(/\.\d+Z$/, "Z"); };

async function get(url) {
  const r = await fetch(url, { headers: { "User-Agent": UA, "Accept": "*/*" }, redirect: "follow", signal: AbortSignal.timeout(8000) });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return await r.text();
}

function parseFeed(xml, base) {
  const out = [];
  const blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || xml.match(/<entry[\s>][\s\S]*?<\/entry>/gi) || [];
  for (const b of blocks) {
    let link = strip(tag(b, "link")) || attr(b, "link", "href") || strip(tag(b, "guid"));
    if (!link) continue;
    try { link = new URL(link, base).href; } catch (e) { continue; }
    const body = tag(b, "content:encoded") || tag(b, "content") || "";
    const summ = tag(b, "description") || tag(b, "summary") || body;
    const thumb = attr(b, "media:content", "url") || attr(b, "media:thumbnail", "url") || attr(b, "enclosure", "url") || attr(summ + body, "img", "src") || null;
    out.push({ title: strip(tag(b, "title")), url: link, summary: strip(summ).slice(0, 600), text: body ? strip(body).slice(0, 20000) : "",
      published: iso(strip(tag(b, "pubDate") || tag(b, "published") || tag(b, "updated") || tag(b, "dc:date"))), thumb });
  }
  return out;
}

function parseTelegram(html, chan) {
  const out = [];
  const parts = html.split(/<div class="tgme_widget_message_wrap/).slice(1);
  for (const p of parts) {
    const post = attr(p, "div", "data-post"); if (!post) continue;
    const text = strip((p.match(/tgme_widget_message_text[^>]*>([\s\S]*?)<\/div>/) || [])[1] || "");
    if (!text) continue;
    const time = attr(p, "time", "datetime");
    const photo = (p.match(/tgme_widget_message_photo_wrap[^>]*background-image:url\('([^']+)'\)/) || [])[1] || null;
    out.push({ title: text.split("\n")[0].slice(0, 200), url: "https://t.me/" + post, summary: text.slice(0, 600), text, published: iso(time), thumb: photo });
  }
  return out.reverse();
}

async function readSource(s) {
  let url = String(s.url || "").trim(); if (!url) return [];
  const tg = url.match(/^(?:https?:\/\/)?t\.me\/(?:s\/)?([A-Za-z0-9_]+)/) || url.match(/^@([A-Za-z0-9_]+)$/);
  if (tg) return parseTelegram(await get("https://t.me/s/" + tg[1]), tg[1]);
  if (!/^https?:\/\//.test(url)) url = "https://" + url;
  let txt = await get(url);
  if (!/<(rss|feed|rdf:RDF)[\s>]/i.test(txt.slice(0, 2000))) {          // site adresi: RSS bağlantısını bul
    const m = txt.match(/<link[^>]+type=["']application\/(?:rss|atom)\+xml["'][^>]*>/i);
    const href = m && (m[0].match(/href=["']([^"']+)["']/i) || [])[1];
    if (!href) return [];
    url = new URL(ent(href), url).href; txt = await get(url);
  }
  return parseFeed(txt, url);
}

module.exports = async (req, res) => {
  if (req.method !== "POST") { res.status(405).json({ error: "POST" }); return; }
  let body = req.body; if (typeof body === "string") { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  const sources = ((body && body.sources) || []).slice(0, 80);
  const since = Date.now() - DAYS * 864e5, now = new Date().toISOString().replace(/\.\d+Z$/, "Z");
  const items = [], errors = [];
  await Promise.all(sources.map(async s => {
    try {
      const list = (await readSource(s)).filter(x => x.title && (!x.published || Date.parse(x.published) >= since)).slice(0, PER_SOURCE);
      for (const x of list) items.push({ id: sha12(x.url), url: x.url, title: x.title, summary: x.summary, text: x.text || "", published: x.published || now,
        fetched_at: now, source: s.name || new URL(x.url).hostname, group: s.group || "Diğer", lang: s.lang || "", thumb: x.thumb, publisher: null, cid: null, status: "", video: null });
    } catch (e) { errors.push({ source: s.name || s.url, error: String(e.message || e) }); }
  }));
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({ items, errors });
};
