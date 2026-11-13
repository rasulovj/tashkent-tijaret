# Kalıcı web sitesi kurulumu

Panel bir bulut sunucusunda 7/24 çalışır ve `https://panel.alanadiniz.uz` gibi sabit bir adresten her bilgisayar ve telefondan açılır. Mac'in açık olması gerekmez.

```
İnternet ──HTTPS──► Caddy (sertifika, 443) ──► panel konteyneri (8765) ──► config/  data/  (sunucu diskinde)
                                                                                  │
                                                                     her gece 03:15 yedek ──► yedekler/
```

## Neler değişti

Panel (22.10.2026): **Haber ve Bülten** tek sayfa, üç sütun (haberler · bültendekiler · dil seçimi, Bülten üret / Video bülten üret, sayfalar, PDF indir). **Raporlar** da üç sütun; tablolar tek **⟳ Şimdi tara** ile resmî kaynaklardan yenilenir. Ana Sayfa gösterge paneli. Duyurular, Gelen Kutusu, Yayınla, Editör, Stüdyo sekmeleri kaldırıldı.


| Dosya | Görev |
|---|---|
| `Dockerfile` | Python 3.12 + Chromium (başsız) + ffmpeg + Türkçe/Kiril fontları |
| `docker-compose.yml` | Panel + Caddy (otomatik Let's Encrypt HTTPS) |
| `deploy/Caddyfile` | Alan adı, HTTPS, güvenlik başlıkları |
| `deploy/entrypoint.sh` | İlk açılışta hazır ayarları `config/` içine kopyalar, paneli yetkisiz kullanıcıyla başlatır |
| `deploy/yedekle.sh` | `config/` ve `data/` günlük yedeği (14 gün saklanır, istenirse buluta da kopyalanır) |
| `deploy/sunucu-kur.sh` | Yeni sunucuda tek komutla kurulum (Docker, güvenlik duvarı, yedek zamanlaması) |
| `.env.example` | Alan adı ve e-posta |

Kodda yapılan küçük değişiklikler (yerel Mac kullanımı aynen devam eder):

- **Güvenlik:** Mevcut kodda oturum açmamış herkes otomatik olarak *yönetici* sayılıyordu (`auth.OPEN_ADMIN`). Bu internette herkesin paneli, API anahtarlarını ve Telegram yayınını kullanabilmesi demekti. Sunucuda (`PANEL_PUBLIC=1`) artık herkes kullanıcı adı ve şifreyle girer, ilk kurulum kodu çalışır ve çerez yalnızca HTTPS üzerinden gönderilir.
- Hatalı giriş sınırı, Caddy arkasında gerçek ziyaretçi adresine göre işler (yoksa tek bir kişinin hataları herkesi kilitlerdi).
- Panelde sol altta **Çıkış** bağlantısı; oturum süresi dolunca giriş ekranına dönülür.
- Chrome yolu `CHROME_PATH` ile ayarlanır (Linux sunucuda Mac yolu yok).
- `PANEL_HOST` ile dinlenecek adres; boş kurulumda panel ilk sayı klasörünü kendisi açar.

## Gerekenler

1. **Sunucu:** Ubuntu 24.04, 2 CPU / 4 GB RAM / 40 GB disk. Örnek: Hetzner CX22 (~5 €/ay), DigitalOcean, Azure B2s.
2. **Alan adı:** ör. `panel.taskentticaret.uz`. DNS'te bir **A kaydı** sunucunun IP adresini göstermeli.
3. Sunucuya SSH ile bağlanabilmek.

## Seçenek A: Kendi sunucunuz (yaklaşık 15 dakika)

```bash
# 1) Sunucuya bağlanıp kodu GitHub'dan alın
ssh root@SUNUCU_IP
cd /opt && git clone https://github.com/rasulovj/tashkent-tijaret taskentticaret
cd taskentticaret

# 2) Alan adı ve e-postayı yazın
cp .env.example .env
nano .env          # DOMAIN=panel.alanadiniz.uz   ACME_EMAIL=...

# 3) Kur ve başlat (Docker, güvenlik duvarı, günlük yedek)
sh deploy/sunucu-kur.sh
```

Betik sonunda **İLK KURULUM KODU**nu yazar. `https://panel.alanadiniz.uz` adresini açın, "İlk kurulum" ekranında bu kodla yönetici hesabını oluşturun. Kodu sonradan görmek için: `docker compose logs panel | grep KURULUM`.

### Mac'teki mevcut verileri taşımak (önerilir)

Bültenler, raporlar, duyurular, kullanıcılar ve ayarlar Mac'teki `config/` ve `data/` klasörlerindedir. Bunları taşırsanız aynı kullanıcılarla devam edilir ve ilk kurulum kodu gerekmez:

```bash
# Mac'te, proje klasöründe:
tar -czf tasima.tar.gz config data
scp tasima.tar.gz root@SUNUCU_IP:/opt/taskentticaret/

# Sunucuda:
cd /opt/taskentticaret
docker compose down
tar -xzf tasima.tar.gz
docker compose up -d --build
```

Kılavuz (Yardım → Kılavuz) ve PDF'i pakette güncel hâliyle gelir; Mac'teki eski `static/guide` klasörünü taşımayın. API anahtarları `config/keys.json` ile taşınır; yoksa panelde **Ayarlar**'dan girilir.

## Seçenek B: Railway (sunucu yönetmeden)

1. Kod GitHub'da: rasulovj/tashkent-tijaret (gizli dosyalar `.gitignore` sayesinde girmez).
2. railway.com → GitHub ile giriş → **New Project → Deploy from GitHub repo** → depoyu seçin. `railway.json` sayesinde Dockerfile ile derlenir.
3. Servis → **Variables**: `PERSIST_DIR=/kalici`
4. Servis → **Volumes → Add volume**, bağlama yolu `/kalici` (config ve data burada kalıcı tutulur).
5. **Settings → Networking → Generate Domain**: `https://….up.railway.app` adresi açılır. Kendi alan adınızı da buradan bağlayabilirsiniz.
6. **Deployments → Logs** içinde `İLK KURULUM KODU`nu bulun ve giriş ekranında yönetici hesabını oluşturun.

Railway'de yedek için volume ekranındaki **Backups** özelliğini açın.

## Günlük kullanım (kendi sunucunuzda)

| İş | Komut (sunucuda, `/opt/taskentticaret` içinde) |
|---|---|
| Durum | `docker compose ps` |
| Kayıtlar | `docker compose logs -f panel` |
| Yeniden başlat | `docker compose restart panel` |
| Kod güncelleme | yeni dosyaları kopyala → `docker compose up -d --build` |
| Elle yedek | `sh deploy/yedekle.sh` |

Sunucu yeniden başlarsa panel ve HTTPS kendiliğinden açılır (`restart: unless-stopped`).

## Arkadaki robotlar (sunucuda kendiliğinden çalışır)

Panel sunucuda açık kaldığı sürece, kimse giriş yapmasa da:

| Robot | Ne zaman | Ne yapar |
|---|---|---|
| Haber tarama | Her 60 dakikada bir (Ayarlar'dan değiştirilebilir) | Kaynaklardaki yeni haberleri toplar, fotoğraf bağlantısını alır |
| Türkçe çeviri | Her taramadan hemen sonra | Yeni yabancı dildeki haberlerin başlık ve özetini Claude ile Türkçeye çevirir; rakamları aslıyla karşılaştırır, tutmayanı uyarı olarak gösterir |
| Rapor verisi | Günde bir kez | Raporlardaki tabloları UN Comtrade, Dünya Bankası ve SIAT'tan yeniler |
| Yedek | Her gece 03:15 | `config/` ve `data/` yedeği |

Panelde **⟳ Şimdi tara** (Haber ve Bülten'de haberler, Raporlar'da tablolar) beklemeden aynı işi hemen yapar.

**Gerekli tek ayar:** Çeviri ve bülten metni için **Ayarlar → Claude API anahtarı** girilmelidir. Anahtar yoksa haberler yine toplanır ama özgün dilinde görünür; makine çevirisine düşülmez.

Robotlar panelle aynı konteynerde çalışır ve `restart: unless-stopped` sayesinde sunucu yeniden başlasa da kendiliğinden açılır. Durumu görmek için: `docker compose logs --tail 50 panel`.

## Kullanıcılar ve yetkiler

İlk kurulum kodunuyla açılan hesap **Yönetici**dir. Arkadaşlarınızı **Ayarlar → 👥 Kullanıcılar** kartından siz eklersiniz; açık kayıt yoktur.

| Rol | Ne yapabilir |
|---|---|
| **Editör** | Haberleri görür ve seçer, bülteni ve raporları hazırlar, PDF ve video üretir. Ayarlar'a giremez. |
| **Yönetici** | Editörün yaptığı her şey + anahtarlar, kullanıcı ekleme/silme/şifre, otomatik tarama sıklığı, kaynaklar. |

- Bülteni üreten kişinin adı kayda geçer (sol alttaki ad, giriş yapan kişiden gelir).
- Şifre en az 8 karakterdir. Aynı adresten 5 hatalı denemede giriş 5 dakika kilitlenir.
- Kullanıcı adı ve şifreyi kişiye güvenli yoldan (yüz yüze, şifreli mesaj) iletin.

## Claude anahtarı ve maliyet

Çeviri ve bülten yazımı Claude ile yapılır. Anahtar: https://console.anthropic.com → **API Keys**. Panelde **Ayarlar → Claude API anahtarı** alanına yapıştırın (sunucuda `config/keys.json` içinde kalır, tarayıcıya gönderilmez).

Maliyeti düşük tutmak için iş bölümü yapılır:

| İş | Model | Tahmini aylık |
|---|---|---|
| Haber çevirisi (günde ~50 haber) | Claude Haiku 5.5 | ~0,50 $ |
| Bülten yazımı + EN/RU/UZ çeviri (ayda 4 bülten) | Claude Sonnet 5.5 | ~2,50 $ |
| **Toplam** | | **~3 $/ay** |

- Çeviriler önbelleğe alınır; aynı metin ikinci kez ücretlendirilmez.
- Panel kendi sayacını tutar (**Ayarlar → Claude** kartında "Bu ay harcanan"). `.env` içindeki `AI_MONTHLY_LIMIT_USD` (varsayılan **5 $**) aşılınca çeviri ve yazım o ay durur; haberler toplanmaya devam eder, özgün dilinde görünür.
- Ek güvence için Console'da **Billing → Spend limits** ile de aynı sınırı koyun.
- Rakam denetimi her çeviride çalışır: özgün metindeki rakamlarla tutmayan çeviri uyarıyla gösterilir.

## Yedekleme ve geri yükleme

- Her gece 03:15'te `yedekler/yedek-TARİH.tar.gz` oluşur, 14 günlük tutulur (`SAKLA_GUN` ile değişir).
- Sunucu tamamen kaybolursa yedek de gider. Sunucu dışına kopya için `rclone` kurup (`apt install rclone`, `rclone config`) cron satırına `UZAK=hedef:klasor` ekleyin; ya da sağlayıcının otomatik disk yedeğini (snapshot) açın.
- Geri yükleme: `docker compose down && tar -xzf yedekler/yedek-....tar.gz && docker compose up -d`

Yedekte şifre karmaları ve API anahtarları bulunur; yedek dosyalarını kimseyle paylaşmayın.

## Notlar

- **Ses:** Sunucuda macOS `say` yoktur. Video bülten anahtarsız da üretilir ama sessizdir; seslendirme için Ayarlar'dan **Azure Speech** anahtarı girin.
- **Uzun işler:** Video ve rapor üretimi 15 dakikaya kadar beklenir (Caddyfile, `read_timeout`).
- **Yükleme sınırı:** 50 MB (Caddyfile, `max_size`).
- **Arama motorları:** Site `noindex` başlığıyla gönderilir; Google'da listelenmez.
- **Oturumlar** bellekte tutulur; panel yeniden başlatılınca herkes tekrar giriş yapar.
