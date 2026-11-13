# Taşkent Ticaret Paneli: web sürümü

Mac'teki panelin aynısı (aynı ekranlar, aynı içerik), tarayıcıda çalışır. Gizli anahtar içermez.

## Vercel'e koymak
1. Bu klasörü vercel.com → **Add New → Project** ile yükleyin (ya da klasörde `npx vercel deploy --prod`).
2. Verilen `https://….vercel.app` adresini açın; panel hemen çalışır.
3. Claude anahtarı ve Telegram bot jetonu **Ayarlar**'dan girilir; yalnızca o tarayıcıda saklanır.

Başka bir sunucuda da çalışır (Netlify, kurum sunucusu, `python3 -m http.server`); yalnızca "Kaynakları şimdi tara" için `api/topla.js` (Node sunucu işlevi) gerekir.

## Klasörler
- `index.html`, `static/` – panel ve tarayıcı arka ucu (`tt*.js`), PDF/görsel üretimi, Türk bayrağı süslemesi
- `veri/` – başlangıç içeriği (bülten, kaynaklar, raporlar, duyurular, akış)
- `d/` – mevcut PDF, görsel, sunum ve video dosyaları
- `api/topla.js` – haber toplama servisi (RSS, Atom, Telegram kanalları)
- `api/resim.js` – haber fotoğraflarını bültene almak için görsel aktarıcı

## Bu sürümde (22.10.2026)
- Duyurular, Gelen Kutusu (birimlerin Bilgi Gönder sayfası) ve Temsilcilikler sekmesi kaldırıldı; panel yalnızca yönetim içindir.
- Haber Akışı'nda her haberde **＋ Bültene ekle**, birden çok haber seçip birlikte ekleme; haberin fotoğrafı bültene gelir.
- Yabancı dildeki haberler Türkçe gösterilir. Çeviriyi yalnızca Claude yapar; rakamlar aslıyla karşılaştırılır, aslı her haberin altında açılır.
- Sunum (16:9 PDF) ve video (WebM, seslendirmesiz) tarayıcıda üretilir.
- **Haber ve Bülten** tek sayfa, üç sütun: solda haberler (kısa/uzun hali, aslı), ortada bültendekiler (sırala, çıkar, metni yerinde düzelt, kaynakla karşılaştır), sağda dil seçimi, **Bülten üret** ve **Video bülten üret**; sayfalar görünür, altta **PDF indir**. Rakam uyarısı varken bülten üretilmez. Eski Haberler, Editör, Görsel Stüdyo, Video ve Sunum sekmeleri kaldırıldı; Kaynaklar Yardım altında.
- Yayınla bölümü (Dosyalar, Telegram, Web) menüden kaldırıldı. Ana Sayfa gösterge paneli oldu: sayı kutucukları ve grafikler.

## Notlar
- Bu sürümde değişiklikler tarayıcıda saklanır. Ortak kayıt için claude.ai bağlantısını kullanın: https://claude.ai/artifact/GtLkbez1knUF3tiW76iQba
- Seslendirmeli video ve rapor tablolarını resmî kaynaklardan tarama (Raporlar → ⟳ Şimdi tara) sunucu sürümünde çalışır.
- Raporlar da üç sütun: solda raporlar ve yeni rapor, ortada bölümler (yerinde düzenleme), sağda Rapor üret, sayfalar ve PDF indir.
- Kılavuz (Yardım → Kılavuz ve PDF) son hâle göre yenilendi; Özbekçe arayüz yeni sayfaları da kapsıyor.
