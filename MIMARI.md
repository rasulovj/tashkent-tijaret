# Taşkent Ticaret Müşavirliği – Robot Platform Mimarisi

**Kurum:** T.C. Taşkent Büyükelçiliği Ticaret Müşavirliği
**Belge:** Sistem mimarisi ve yeniden kurulum rehberi · Ekim 2026

---

## 1. Amaç

Haftalık ekonomik bülteni, raporları, duyuruları ve sosyal medya yayınlarını tek bir web panelinden **otomatik** hazırlayan, onaylatan ve yayınlayan platform.

**Yönetim modeli:** Diğer birimler (Büyükelçilik, Başkonsolosluk, Eğitim, Tarım, Din İşleri müşavirlikleri) bilgi **gönderir**. **Ticaret Müşavirliği** inceler, onaylar ve **yayınlar**. Yönetim bu birimdedir.

---

## 2. Genel akış

```
KAYNAKLAR              ROBOT                    İNSAN            YAYIN
RSS / Google Haberler  1. Topla (saatlik)       3. Panelde       PDF bülten (4 dil)
Telegram, YouTube      2. Seç + puanla    ───►  düzenle    ───►  Video bülten
Bakanlık siteleri      4. Yaz (Claude AI)       ve onayla        Sunum (PDF+PPTX)
Birim gönderileri      5. Rakam doğrula                          Telegram
Veri API'leri          6. Çevir (TR/EN/RU/UZ)                    Duyuru görselleri
(Comtrade, WB, SIAT)   7. Tasarla → PDF                          Raporlar
```

---

## 3. Teknoloji

| Katman | Seçim | Neden |
|---|---|---|
| Dil | **Python 3.9+** | Veri, PDF, yapay zekâ kütüphaneleri hazır |
| Web sunucu | Python standart `ThreadingHTTPServer` | Ek kurulum yok, tek dosya |
| Arayüz | **Tek sayfa HTML + JavaScript** (`static/panel.html`) | Derleme gerektirmez, telefonda çalışır |
| Şablon | **Jinja2** | Bülten, rapor, duyuru, slayt tasarımı HTML olarak |
| PDF üretimi | **Google Chrome (başsız)** | HTML → baskı kalitesinde PDF |
| PDF işleme | **PyMuPDF** | Küçük resim, sıkıştırma, PDF içe aktarma |
| Yapay zekâ | **Claude API** (`claude-opus-5-5`) | Haber yazımı, özet, çeviri |
| Çeviri yedeği | MyMemory | API anahtarı yoksa |
| Ses | **Azure Neural TTS** (yedek: macOS `say`) | Video bülten seslendirme |
| Video | **ffmpeg** (`imageio-ffmpeg`) | Slayt + ses → MP4 |
| Sunum | `python-pptx` | Konuşmacı notlu PPTX |
| Haber çekme | `feedparser`, `trafilatura`, `requests` | RSS ve tam metin |
| Veri saklama | **JSON dosyaları** (veritabanı yok) | Basit, yedeklemesi kolay |

**Gerekli paketler (`requirements.txt`):** feedparser, jinja2, anthropic, requests, trafilatura, pymupdf, imageio-ffmpeg, qrcode, python-pptx

---

## 4. Klasör yapısı

```
taşkentticaret/
├── run.py                  Komut satırı: collect | select | write | review | render | all | panel
├── requirements.txt
├── bot/                    ROBOTUN BEYNİ
│   ├── panel.py            Web sunucu + tüm API uçları + otomatik tarama
│   ├── auth.py             Kullanıcılar, şifreler, oturumlar, ilk kurulum
│   ├── collect.py          Kaynaklardan haber toplama (RSS, Telegram, YouTube, bakanlık)
│   ├── select.py           Puanlama, kümeleme, tam metin, görsel bulma
│   ├── writer.py           Claude ile haber yazımı ve çeviri
│   ├── verify.py           Rakam doğrulama (kaynakta geçmeyen sayı uyarısı)
│   ├── translate.py        Çeviri + önbellek
│   ├── render.py           Bülten HTML → PDF, göstergeler, QR kod
│   ├── media.py            Haber fotoğrafları ve video bağlantıları
│   ├── charts.py           Döviz kurları (Özbekistan Merkez Bankası) + grafik
│   ├── video.py            Video bülten ve sunum üretimi
│   ├── tts.py              Seslendirme (Azure / macOS)
│   ├── announce.py         Duyuru, etkinlik, kutlama, anma görselleri
│   ├── inbox.py            Birimlerden gelen gönderiler
│   ├── telegram.py         Telegram botu ve kanallara yayın
│   ├── settings.py         API anahtarları (config/keys.json)
│   ├── demo.py / vercel.py Salt okunur önizleme sitesi
│   └── reports/            RAPOR MOTORU
│       ├── sources.py      UN Comtrade, Dünya Bankası, SIAT (Özbekistan istatistik)
│       ├── blocks.py       Rapor blokları (ortaklar, ürünler, seriler, bölge…)
│       ├── builder.py      Rapor oluştur / yenile / PDF içe aktar / yazdır
│       ├── svg.py          Grafikler
│       └── ai.py           Rapor metinleri için yapay zekâ
├── static/                 ARAYÜZ
│   ├── panel.html          Yönetim paneli (tek sayfa)
│   ├── giris.html          Giriş + ilk kurulum ekranı
│   ├── gonder.html         Birimlerin bilgi gönderme sayfası
│   ├── i18n-uz.js          Özbekçe arayüz sözlüğü
│   ├── kilavuz.html        Kullanım kılavuzu
│   └── guide/              Kılavuz PDF'leri, tanıtım afişleri
├── templates/              TASARIM ŞABLONLARI
│   ├── bulten.html         Haftalık bülten
│   ├── report.html         Rapor
│   ├── announce.html       Duyuru / kutlama görseli
│   ├── video_slide.html    Video ve sunum slaytı
│   └── tanitim_afisi.html  Tanıtım afişi
├── config/                 AYARLAR
│   ├── sources.json        45 haber kaynağı + otomatik tarama ayarı
│   ├── institutions.json   Birimler (Büyükelçilik, Konsolosluk, müşavirlikler)
│   ├── ozel_gunler.json    Bayram ve anma günleri (TR + UZ)
│   ├── regions.json        Özbekistan bölgeleri
│   ├── reports/*.json      Rapor türleri: sektör (30 hazır), ülke, yatırım, şehir
│   ├── users.json          Kullanıcılar (gizli, şifreler karma)
│   └── keys.json           API anahtarları (gizli)
├── data/                   ÜRETİLEN İÇERİK
│   ├── raw/items.jsonl     Toplanan tüm haberler
│   ├── 2026-10-21/         Her sayı ayrı klasör: taslaklar, çeviriler, PDF, video, sunum, görseller
│   ├── reports/            Raporlar
│   ├── duyurular/          Duyuru ve kutlamalar
│   ├── gelen/              Birim gönderileri
│   └── cache/              API önbelleği
└── tools/                  Kılavuz ve afiş üretim araçları
```

---

## 5. Modüller

### 5.1 Haftalık bülten
1. **Topla:** 45 kaynak. Türk basını (AA, TRT Avaz, Dünya…), Özbek basını (Gazeta, Kun, Daryo, UzA…), Google Haberler sorguları, Telegram kanalları, YouTube, bakanlık siteleri. Kaynak başına `filter` / `require` / `exclude` kelime süzgeci.
2. **Seç:** EN/RU/TR anahtar kelime puanı, benzer haberleri kümeleme, tam metni çekme, fotoğraf ve video bağlantısı ekleme.
3. **Yaz:** Claude, stil rehberine göre Türkçe haber yazar (başlık, özet, metin, kaynak).
4. **Doğrula:** Metindeki her rakam kaynak metinde aranır; bulunamayan işaretlenir.
5. **Onay:** Editör panelde düzenler, sıralar, onaylar.
6. **Çevir:** EN / RU / UZ.
7. **Yazdır:** Şablon → PDF. Kur göstergeleri, grafikler, fotoğraflar, QR kod.

### 5.2 Raporlar
- **Türler:** Sektör · Ülke · Yatırım profili · Şehir/Bölge.
- **Veri:** UN Comtrade (dış ticaret, HS kodları), Dünya Bankası (makro), SIAT (bölge istatistikleri, pay ve sıralama).
- **Bloklar:** ilk 10 ortak, ilk 10 ürün, Türkiye ihracatı, makro seriler, bölge haberleri.
- **Çıktı:** Mevcut PDF raporlar içe aktarılıp şablona dönüştürülebilir. İçindekiler tablosu otomatik oluşur.

### 5.3 Duyurular ve kutlamalar
- **Türler:** etkinlik, duyuru, ilan, haber, kutlama, anma.
- **Temalar:** bordo, bayram, lacivert, anma, gece.
- **Biçimler:** kare (1080²), dikey (1080×1350), yatay (1600×900), afiş (A4).
- **Özel günler takvimi:** 29 Ekim, 23 Nisan, 19 Mayıs, 30 Ağustos, 10 Kasım, 15 Temmuz, 18 Mart, Nevruz, Özbekistan Bağımsızlık ve Anayasa günleri, dini bayramlar. Yıl dönümü sayısı otomatik hesaplanır.

### 5.4 Video ve sunum bülteni
Bülten haberlerinden slaytlar üretilir. Seslendirme (Azure Neural ses) eklenip MP4 video yapılır. Aynı slaytlardan PDF ve PPTX sunum çıkar.

### 5.5 Gelen kutusu (birimler)
- Birim kullanıcısı yalnızca `/gonder` sayfasını görür. Metin, fotoğraf ve dosya gönderir.
- **Durumlar:** yeni → inceleniyor → yayına alındı / reddedildi. Birim, durumu ve notu takip eder.
- Müşavirlik gönderiyi tek tıkla **bültene** ya da **duyuruya** aktarır.

### 5.6 Telegram
Bot bağlanır, kanallar eklenir. PDF, video ve görsel seçilen tüm kanallara tek tıkla gider. Yayın günlüğü tutulur.

---

## 6. Kullanıcılar ve güvenlik

| Rol | Yetki |
|---|---|
| **Yönetici** (Ticaret Müşavirliği) | Her şey: düzenleme, onay, yayın, kullanıcı yönetimi, ayarlar |
| **Birim** | Yalnızca bilgi gönderme ve kendi gönderilerini izleme |

- **Herkes kullanıcı adı ve şifreyle girer.** Paneli çalıştıran bilgisayar da dahil.
- **İlk kurulum:** Hiç yönetici yokken giriş ekranı "İlk kurulum"a döner. Sunucudaki tek kullanımlık **kurulum kodu** (`config/kurulum-kodu.txt`) olmadan yönetici oluşturulamaz.
- **Şifreler:** PBKDF2-SHA256 ile karma olarak saklanır, düz metin tutulmaz.
- **Oturum:** HttpOnly + SameSite çerez, 12 saat geçerli.
- **Deneme sınırı:** 5 dakikada en fazla 5 hatalı deneme.
- **Hesap koruması:** Son yönetici ve kişinin kendi hesabı silinemez.
- **Gizli dosyalar:** `users.json`, `keys.json`, `telegram.json` yalnızca sahibine açıktır (izin 600).

---

## 7. Dış hizmetler ve anahtarlar

| Hizmet | Ne için | Anahtar |
|---|---|---|
| Claude API (Anthropic) | Haber yazımı, çeviri, rapor metni | `ANTHROPIC_API_KEY` |
| Azure Speech | Doğal ses (video bülten) | `AZURE_SPEECH_KEY` + bölge |
| Telegram Bot | Kanal yayını | BotFather jetonu |
| UN Comtrade, Dünya Bankası, SIAT, Özbekistan MB | Veri | Anahtarsız (açık) |
| Vercel (isteğe bağlı) | Salt okunur önizleme sitesi | Vercel jetonu |

Anahtarlar panelde **Ayarlar** bölümünden girilir.

---

## 8. Çalıştırma

### Yerel (tek bilgisayar)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py panel          # http://127.0.0.1:8765
```
Google Chrome kurulu olmalıdır (PDF için).

### Geçici internet linki (bu Mac üzerinden)
```bash
tools/bin/cloudflared tunnel --url http://127.0.0.1:8765
```
`https://….trycloudflare.com` linki verir. Mac açık kaldıkça çalışır; yeniden başlatınca link değişir.

### Kalıcı web sitesi (önerilen hedef)

| Bileşen | Seçim |
|---|---|
| Sunucu | Azure (veya benzeri) Linux sanal makine, 2 CPU / 4 GB |
| Paket | Docker imajı: Python + Chrome + ffmpeg |
| Ses | macOS `say` yerine Azure Neural TTS |
| Adres | Sabit alan adı (ör. `panel.taskentticaret…`) + HTTPS sertifikası |
| Yedek | `config/` ve `data/` klasörlerinin günlük yedeği |

---

## 9. Otomatik görevler

| Görev | Sıklık |
|---|---|
| Kaynak tarama | Saatlik (panelden açılıp kapatılır) |
| Döviz kurları ve göstergeler | 30 dakika önbellek |
| API verileri (Comtrade, Dünya Bankası) | Önbellekli, gerektiğinde yenilenir |

---

## 10. Yeniden kurulum sırası (sıfırdan yapılacaksa)

1. **Temel:** klasör yapısı, `run.py`, kaynak listesi (`sources.json`), toplama ve seçme.
2. **Bülten:** yazım (Claude), doğrulama, şablon, PDF, 4 dil.
3. **Panel:** web sunucu, düzenleme ve onay ekranı, canlı PDF önizleme.
4. **Kullanıcılar:** giriş, roller, ilk kurulum, birim gönderi sayfası, gelen kutusu.
5. **Raporlar:** veri bağlayıcıları, bloklar, rapor türleri.
6. **Duyurular:** şablonlar, temalar, özel günler takvimi.
7. **Medya:** video, sunum, seslendirme.
8. **Yayın:** Telegram.
9. **Arayüz:** Özbekçe dil, telefon uyumu, kılavuz.
10. **Sunucu:** Docker, alan adı, HTTPS, yedekleme.

---

## 11. Bugünkü durum (21 Ekim 2026)

| Bileşen | Durum |
|---|---|
| Bülten, raporlar, duyurular, video/sunum, gelen kutusu, TR/UZ, mobil | ✅ Çalışıyor |
| Şifreli giriş + ilk kurulum | ✅ Etkin |
| Geçici internet linki | ✅ Bu Mac açıkken |
| Claude API, Azure ses, Telegram botu | ⏳ Anahtar bekleniyor |
| Kalıcı sunucu (Docker, alan adı, HTTPS) | ⏳ Yapılacak |
