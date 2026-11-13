# Taşkent Ticaret Paneli · Vercel paketi (13.11.2026)

claude.ai'deki panelin bugünkü hali, **verileriyle birlikte**: 6 haberlik bülten listesi, 255 haber (Türkçe çevirileriyle), 45 kaynak, 6 rapor, üretilmiş bülten ve rapor PDF'leri. Gizli anahtar yoktur.

## Vercel'e koyma (5 dakika)
1. vercel.com → **Add New → Project**.
2. Ya bu klasörü GitHub deposuna koyup **Import** edin, ya da klasörde `npx vercel deploy --prod` çalıştırın.
   Framework: **Other**, Build Command: boş, Output Directory: boş (kök).
3. Verilen `https://….vercel.app` adresini açın. Panel veriler yüklenmiş olarak açılır.
4. **Yardım → Ayarlar**'dan Claude anahtarını girin (çeviri, bülten yazımı, otomatik bülten için).

## İçinde ne var
- `index.html`, `static/`: panel
- `veri/`: başlangıç içeriği; `veri/canli.json` claude.ai'deki güncel kayıtlar (bülten listesi, haberler, kaynaklar, raporlar)
- `d/`: PDF, görsel, sunum ve video dosyaları
- `api/topla.js`: "⟳ Şimdi tara" için haber toplama (RSS, Atom, Telegram kanalları)
- `api/resim.js`: haber fotoğraflarını bültene almak için

## Bilmeniz gerekenler
- Bu sürümde kayıtlar **tarayıcıda** tutulur: her bilgisayar paketteki verilerle başlar, sonraki değişiklikler o tarayıcıda kalır. Ortak kayıt (herkes aynı listeyi görsün) için veritabanı eklemek gerekir (ör. Vercel'deki Neon/Upstash).
- Haber taraması "⟳ Şimdi tara" ile yapılır. Saatlik otomatik tarama sunucu sürümünde ya da Vercel Pro'da (Cron) mümkündür.
- Claude anahtarı yalnızca o tarayıcıda saklanır; masraf yalnızca sizin anahtarınıza yansır.
