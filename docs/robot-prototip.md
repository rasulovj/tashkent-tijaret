# Bülten Robotu – Prototip

Taşkent Ticaret Müşavirliği haftalık "Ekonomi Haberleri" bülteni için otomatik hazırlama hattı.

```
collect -> select -> write (Claude) -> review (rakam kontrolü) -> [editör onayı] -> render (TR/EN/RU PDF)
```

| Dosya | Görev |
|---|---|
| `config/sources.json` | Kaynak listesi (RSS) ve sayı ayarları |
| `bot/collect.py` | RSS tarama, ham depo `data/raw/items.jsonl` (hafta boyunca birikir) |
| `bot/select.py` | Ekonomi puanı, kopya haber kümeleme, tam metin çekme -> `candidates.json` |
| `bot/writer.py` | Claude ile seçim + Türkçe bülten metni (`drafts.json`) ve çeviri (`drafts.en.json` ...) |
| `bot/verify.py` | Metindeki her rakamın kaynakta geçtiğini kontrol eder |
| `bot/charts.py` | Merkez Bankası kurları ve SVG grafikler |
| `bot/render.py` + `templates/bulten.html` | HTML şablon -> Chrome ile PDF |

## Kurulum

```bash
python3 -m venv .venv && .venv/bin/pip install feedparser jinja2 anthropic requests trafilatura
export ANTHROPIC_API_KEY=...   # yazım ve çeviri adımı için
```

## Kullanım

```bash
.venv/bin/python run.py collect      # cron ile 2 saatte bir
.venv/bin/python run.py all          # perşembe sabahı: seç + yaz + editör PDF'i
# editör drafts.json'u düzeltir / sıralar
.venv/bin/python run.py render tr en ru
```

Editör PDF'inde (`...-EDITOR.pdf`) kaynakta bulunamayan rakam içeren haberler sarı işaretlenir.

## Editör paneli

```bash
.venv/bin/python run.py panel        # http://127.0.0.1:8765 (yalnızca bu bilgisayar)
```

- Haberleri sürükleyerek sırala, başlık/metin/kategori/kaynak düzenle, haber çıkar.
- Aday havuzundan haber ekle (API anahtarı varsa Claude yazar, yoksa boş taslak açılır).
- Sağda kaynak metin: taslakta kullanılan rakamlar yeşil, kullanılmayanlar sarı.
- Kaydet (Ctrl+S) her seferinde rakam kontrolü yapar; uyarı varken onay verilemez.
- Türkçe metin değişince çeviriler "eski" olur; onayda yalnızca güncel çeviriler PDF'e girer.
- Onay, editör adı ve saatle `meta.json` geçmişine yazılır.

## Raporlar (Sektör / Ülke / Yatırım Profili)

Panelde **Raporlar** sayfası. Rapor türleri `config/reports/*.json` içinde tanımlı (bölüm yapısı, veri blokları).

1. **Oluştur:** tür + parametreler (ülke, Comtrade kodu, sektör, GTİP kodları, yıl).
2. **Önceki raporu aktar:** geçen yılın PDF'i bölüm başlıklarına göre ayrılır, metinler taslak olur.
3. **Verileri güncelle:** dış ticaret tabloları UN Comtrade'den, makro göstergeler Dünya Bankası'ndan
   otomatik gelir (`bot/reports/blocks.py`, önbellek `data/cache`).
4. Bölümleri düzenle/onayla → **PDF üret** (kapak, sayfa numaralı içindekiler, tablolar, grafikler).
   `config/assets/logo.png` varsa kapağa eklenir. API anahtarı varsa "Claude ile güncelle" eski metni yeni veriyle günceller.

## Telegram yayını

Panelde **Telegram Yayını** sayfası (resmî Bot API, `bot/telegram.py`):
@BotFather'dan bot jetonu al → botu kanallara yönetici ekle → jetonu panele gir → kanalları ekle.
Sonra PDF/görsel yükle (veya üretilmiş PDF seç) → açıklama → **Seçili kanallara gönder**.
Jeton yalnızca `config/telegram.json` (izin 600) içinde durur, panele geri gönderilmez.

## Yeni: Türk basını, çok dilli arama, görseller, video bülten, TR/UZ

- **Kaynaklar** (`config/sources.json`): Özbekistan basını + Türk basını (Google Haberler TR, AA, TRT Haber, Dünya;
  genel akışlardan yalnızca Özbekistan haberleri `filter` ile alınır) + TRT Avaz (site ve YouTube).
- **Türkçe arama:** Haber Akışı'nda Türkçe yazıp Enter → sorgu EN/RU'ya çevrilir, tüm dillerde aranır, başlıklar
  Türkçe gösterilir (`bot/translate.py`; Claude anahtarı yoksa ücretsiz MyMemory, günlük ~5.000 karakter).
- **Görseller ve bağlantılar:** aday haberlerin ana görseli ve video bağlantıları toplanır (`bot/media.py`);
  PDF'te fotoğraf ("Görsel: kaynak") ve video QR kodu çıkar. Editörde fotoğraf kapatılabilir, video eklenebilir.
- **Video bülten:** panelde *Video Bülten* → slaytlar + macOS Türkçe seslendirme (Yelda) → MP4 (`bot/video.py`).
  Telegram'a video olarak gönderilebilir.
- **Raporlar:** 30 hazır sektör (GTİP kodlarıyla) `config/reports/sektor.json` → `presets`.
- **TR/UZ:** panel arayüzü sol alttan Türkçe/Özbekçe (`static/i18n-uz.js`); bülten PDF'i ve video Özbekçe de üretilir.
- **Kılavuz:** panelde *Kılavuz* sayfası ve `static/guide/Kullanim-Kilavuzu.pdf`. Ekran görüntülerini yenilemek için
  panel açıkken `.venv/bin/python tools/make_guide.py`.

## Güncel: menü, şehir raporları, sunum, ses, kaynak yönetimi

- **Menü 6 başlık:** Ana Sayfa · Haberler · Bülten · Raporlar · Yayınla · Yardım (alt bölümler sekmeli).
- **Şehir / bölge raporu** (`config/reports/sehir.json`, `config/regions.json`): 14 bölge; SIAT (siat.stat.uz) bölge
  istatistikleri, ülke payı ve sıra, bölge haberleri, isteğe bağlı odak sektör.
- **Sunum bülteni:** video slaytlarından 16:9 PDF + PowerPoint (`video.build_deck`), panelde tam ekran gösterim.
- **Ses:** `bot/tts.py` — Mac sesi (Yelda; "Gelişmiş" sürüm indirilirse otomatik) veya Azure Neural (Emel, Ahmet, Madina, Sardor).
- **Ayarlar:** Claude ve Azure anahtarları panelden (`config/keys.json`, izin 600); anahtar gerektiren düğmeler anahtar ister.
- **Kaynaklar:** 36 kaynak (Özbekistan basını, 20 Türk basını, 8 Telegram kanalı, TRT Avaz). Panelden ekle/aç-kapa/sil.
  Telegram kanalları herkese açık web önizlemesinden (t.me/s/...) okunur. Instagram herkese açık okumaya izin vermez.
- **Otomatik tarama:** panel açıkken varsayılan her 60 dakikada (Yardım → Ayarlar).

## Duyurular (etkinlik, duyuru, ilan, haber)

Panelde **Duyurular** (`bot/announce.py`, `templates/announce.html`): form + canlı önizleme; kare/dikey/yatay PNG,
A4 afiş PDF, Telegram metni; kayıt bağlantısı QR kod olur; Özbekçe/İngilizce/Rusça kopya; tek tıkla Telegram'a.
Kayıtlar `data/duyurular/<id>/`. Yaklaşan etkinlikler Ana Sayfa'da listelenir.

## Temsilcilikler

Panelde **Haberler → Temsilcilikler**: Büyükelçilik, Semerkant Başkonsolosluğu, Eğitim, Tarım, Din Hizmetleri ve Ticaret
müşavirliklerinin haber ve mesajları (`config/institutions.json`). Otomatik kaynaklar: Büyükelçilik Telegram (@TCTaskentBE),
mfa.gov.tr temsilcilik duyuru sayfaları (`kind: mfa`), kurum adlarıyla Google Haberler taraması (`require`/`exclude` süzgeçleri).
Elle mesaj ekleme (`data/kurum_mesajlari.json`), "Bültene ekle", "Duyuruya dönüştür".

## Gelen Kutusu ve birimler (yönetim bu birimde)

- Diğer birimler (Büyükelçilik, Başkonsolosluk, müşavirlikler) kendi kullanıcılarıyla **/gonder** sayfasından bilgi gönderir
  (`static/gonder.html`, TR/UZ). Yönetim, **Gelen Kutusu**'nda inceler ve yayınlar (`bot/inbox.py`, `data/gelen/`).
- Kullanıcılar ve roller: `bot/auth.py` (`config/users.json`, PBKDF2; roller *yonetici* / *birim*). Ayarlar → Birim kullanıcıları.
- Bu bilgisayardan (127.0.0.1) açılan panel yönetici masasıdır; ağdan girenler şifre ile girer.
- Ağ erişimi: Ayarlar → Ağ erişimi (`config/network.json`), açınca panel yeniden başlatılır ve 0.0.0.0'da dinler.
  Yalnızca ofis ağı/VPN için; HTTPS yoktur, internete açılmamalıdır.
- Birimlere dağıtmak için: `static/guide/Birim-Kilavuzu.pdf` (TR/UZ).
