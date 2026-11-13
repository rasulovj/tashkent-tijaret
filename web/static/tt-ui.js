/* Web sürümüne özgü arayüz eklemeleri: tasarım robotu, Bilgi Gönder formu, Web sayfası. */
(function () {
"use strict";
const { H } = TT;
const PUBLIC_LINK = "https://claude.ai/artifact/GtLkbez1knUF3tiW76iQba";
TT.ready = TT.init().catch(e => { console.error(e); if (window.toast) window.toast("Başlatılamadı: " + e.message, true); throw e; });

// Dış sitelerden gelen küçük resimler (haber akışı) engellenirse boş kutu yerine gizle
document.addEventListener("error", e => { const t = e.target; if (t && t.tagName === "IMG" && /^https?:/.test(t.getAttribute("src") || "")) t.style.display = "none"; }, true);

/* ------------------------------------------------------------------ tasarım robotu */
async function designRobot(opts, progress) {
  const done = [];
  const list = TT.annList();
  const has = (title, lang) => list.some(a => a.title === title && a.lang === lang);
  if (opts.special) {
    for (const lang of ["tr", "uz"]) {
      for (const d of TT.specialDays(lang, opts.days)) {
        if (has(d.title, lang)) continue;
        progress(`Özel gün kartı: ${d.title}`);
        const a = await TT.fromSpecial(d.key, lang);
        await TT.annProduce(a.id, ["kare", "dikey"]);
        done.push(`${d.title} (${lang.toUpperCase()})`);
      }
    }
  }
  if (opts.news) {
    const items = TT.drafts().items.slice(0, opts.newsCount);
    for (const it of items) {
      const title = it.headline.replace(/\.$/, "");
      if (has(title, "tr")) continue;
      progress(`Haber kartı: ${title.slice(0, 50)}`);
      const first = ((it.paragraphs[0] || "").match(/^.{40,260}?[.!?](\s|$)/) || [it.paragraphs[0] || ""])[0].trim();
      const a = await TT.annNew("haber", "tr");
      const vals = { title, subtitle: first.slice(0, 220), theme: "bordo", tag: (it.category || "").toLocaleUpperCase("tr"), link: (it.sources[0] || {}).url || "" };
      if (it.photo && it.photo.file) {
        const ext = (it.photo.file.match(/\.\w+$/) || [".jpg"])[0];
        const blob = await (await fetch(TT.fileUrl("img:" + it.photo.file))).blob();
        await TT.putFile(`ann:${a.id}/foto${ext}`, `foto${ext}`, blob);
        vals.photo = `foto${ext}`;
      }
      await TT.annUpdate(a.id, vals);
      await TT.annProduce(a.id, ["kare"]);
      done.push(title.slice(0, 60));
    }
  }
  if (opts.missing) {
    for (const a of TT.annList()) {
      if (a.outputs.length || !a.title) continue;
      progress(`Çıktılar: ${a.title.slice(0, 50)}`);
      await TT.annProduce(a.id, ["kare", "dikey", "yatay", "afis"]);
      done.push(a.title.slice(0, 60));
    }
  }
  return done;
}
function openDesignRobot() {
  const d = document.querySelector("#dlg");
  const soon = TT.specialDays("tr", 45);
  d.innerHTML = `<h3>🤖 Tasarım robotu</h3>
    <p class="hint" style="margin-top:0">Seçtiğiniz kartları orijinal şablonlarla hazırlar ve PNG/PDF çıktılarını Duyurular'a kaydeder. Hazır olanları atlar.</p>
    <label class="row" style="margin:8px 0"><input type="checkbox" id="dr-sp" style="width:auto" checked> Yaklaşan özel günler (45 gün): ${soon.length ? soon.map(x => H(x.title)).join(", ") : "yok"} · Türkçe + Özbekçe, kare + dikey</label>
    <label class="row" style="margin:8px 0"><input type="checkbox" id="dr-news" style="width:auto" checked> Bültenin ilk <input id="dr-n" type="number" min="1" max="15" value="3" style="width:56px;display:inline-block"> haberi için sosyal medya kartı (kare)</label>
    <label class="row" style="margin:8px 0"><input type="checkbox" id="dr-miss" style="width:auto" checked> Çıktısı olmayan duyurular için 4 format (kare, dikey, yatay, A4 afiş)</label>
    <div class="hint" id="dr-st" style="min-height:18px;margin:6px 0"></div>
    <div class="row" style="justify-content:flex-end"><button id="dlg-no">Kapat</button><button class="primary" id="dlg-yes">Çalıştır</button></div>`;
  d.showModal();
  document.querySelector("#dlg-no").onclick = () => d.close();
  document.querySelector("#dlg-yes").onclick = async () => {
    const btn = document.querySelector("#dlg-yes"); btn.disabled = true;
    const st = document.querySelector("#dr-st");
    try {
      const done = await designRobot({ special: document.querySelector("#dr-sp").checked, days: 45, news: document.querySelector("#dr-news").checked,
        newsCount: +document.querySelector("#dr-n").value || 3, missing: document.querySelector("#dr-miss").checked }, m => { st.textContent = m + "…"; });
      await TT.log(window.who ? window.who() : "editör", `tasarım robotu: ${done.length} kart hazırlandı`);
      st.innerHTML = done.length ? `<b style="color:var(--ok)">✓ ${done.length} kart hazır:</b> ${done.map(H).join(" · ")}` : "Yeni kart gerekmedi; hepsi hazır.";
      try { annList = null; if (typeof renderAnn === "function" && page === "ann") await renderAnn(); } catch (e) {}
    } catch (e) { st.innerHTML = `<span style="color:#a1261b">${H(e.message)}</span>`; }
    btn.disabled = false;
  };
}
document.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest("#robot-design");
  if (b) { e.preventDefault(); openDesignRobot(); }
});

/* ------------------------------------------------------------------ Bilgi Gönder (birim formu) */
TT.openGonder = function () {
  const o = document.createElement("div");
  o.style.cssText = "position:fixed;inset:0;z-index:100;background:rgba(20,10,10,.45);display:flex;align-items:center;justify-content:center;padding:16px";
  o.innerHTML = `<div style="background:#fff;border-radius:14px;width:min(980px,100%);height:min(92vh,100%);display:flex;flex-direction:column;overflow:hidden">
    <div class="row" style="padding:10px 14px;border-bottom:1px solid var(--line)"><b style="flex:1">✉ Bilgi Gönder · birimlerin kullandığı form</b><button class="ghost" id="g-x">Kapat ✕</button></div>
    <iframe src="static/gonder.html" title="Bilgi Gönder" style="flex:1;border:0;width:100%"></iframe></div>`;
  document.body.appendChild(o);
  o.querySelector("#g-x").onclick = () => { o.remove(); try { if (page === "inbox") renderInbox(); } catch (e) {} };
};

/* ------------------------------------------------------------------ Yayınla → Web */
TT.renderWeb = async function (el) {
  const st = await TT.state();
  const robot = TT.Store.get("tt/robot") || TT.base._robot || {};
  const db = TT.Store.mode === "db";
  el.innerHTML = `
    <div class="grid two">
      <div class="card"><h3>🌐 Panel web'de yayında</h3>
        <p>${db ? "Bu panel claude.ai üzerinde yayında. Bağlantıyı gören ve erişim verilen herkes her bilgisayardan açabilir; yapılan değişiklikler herkes için ortak kaydedilir."
          : "Bu kopya kendi sunucunuzda (ör. Vercel) çalışıyor. Değişiklikler bu tarayıcıda saklanır."}</p>
        <div class="keybox"><input readonly value="${H(PUBLIC_LINK)}" onclick="this.select()"><a href="${H(PUBLIC_LINK)}" target="_blank" rel="noopener"><button>Aç ↗</button></a></div>
        <p class="hint">Erişim vermek için claude.ai'deki yayının <b>Paylaş</b> menüsünü kullanın.</p></div>
      <div class="card"><h3>📦 Taşınabilir paket (Vercel / başka sunucu)</h3>
        <p>Projenin <b>web-surumu</b> klasöründeki <b>panel-web.zip</b> bu panelin tamamıdır: aynı ekranlar, aynı içerik, haber toplama servisi (<code>api/topla</code>) dahil.</p>
        <ol class="hint" style="padding-left:18px;margin:0"><li>Zip'i açın, klasörü vercel.com → <b>Add New → Project → Import</b> ile yükleyin (ya da <code>npx vercel</code>).</li>
          <li>Açılan adreste panel hemen çalışır; Claude anahtarı ve Telegram jetonu Ayarlar'dan girilir, yalnızca o tarayıcıda kalır.</li></ol></div>
    </div>
    <div class="grid two">
      <div class="card"><h3>🤖 Haber toplama robotu</h3>
        <p class="hint" style="margin-top:0">${db ? "Robot claude.ai'de zamanlanmış görev olarak 3 saatte bir kaynakları tarar ve yeni haberleri akışa ekler. “Kaynakları şimdi tara” düğmesi robotu hemen çalıştırır." : "“Kaynakları şimdi tara” düğmesi sunucudaki api/topla servisini çağırır."}</p>
        <table class="dtable"><tbody>
          <tr><td class="l">Son tarama</td><td class="l">${robot.last ? H(fmtTime(robot.last)) + " · " + (robot.added ?? 0) + " yeni haber" : "—"}</td></tr>
          <tr><td class="l">Toplam haber</td><td class="l">${st.stats.raw_total} (bu hafta ${st.stats.raw_week})</td></tr>
          <tr><td class="l">Kaynak</td><td class="l">${st.sources.filter(s => s.enabled !== false).length} açık / ${st.sources.length}</td></tr></tbody></table></div>
      <div class="card"><h3>Bu sürümde neler farklı?</h3>
        <ul class="hint" style="padding-left:18px;margin:0">
          <li>PDF'ler (bülten, editör, rapor, afiş) tarayıcıda üretilir; sayfa düzeni Mac'tekiyle aynıdır, metin görüntü olarak gömülür.</li>
          <li>Video ve sesli sunum üretimi yalnızca Mac'teki panelde yapılır; mevcut video ve sunumlar burada izlenir/indirilir.</li>
          <li>Rapor tablolarını resmî kaynaklardan (Comtrade, Dünya Bankası, SIAT) yenileme Mac'teki panelde yapılır.</li>
          <li>${db ? "claude.ai güvenlik kuralları gereği Telegram'a doğrudan gönderim yapılamaz; dosyayı indirip paylaşın ya da Vercel sürümünü kullanın." : "Telegram'a gönderim bot jetonuyla doğrudan yapılır."}</li></ul></div>
    </div>`;
};
})();
