# Taşkent Ticaret Paneli

Taşkent Ticaret Müşavirliği için haber → Türkçe çeviri → bülten, raporlar ve çok kullanıcılı yönetim paneli.

Canlı (claude.ai) sürüm: https://claude.ai/artifact/GtLkbez1knUF3tiW76iQba

## Depoda ne var

| Klasör | Ne işe yarar |
|---|---|
| kök (`bot/`, `static/`, `templates/`, `Dockerfile`) | **Tam sunucu sürümü** (Python). Giriş ekranı, Editör/Yönetici rolleri, saatlik haber taraması + Claude çevirisi, günlük rapor taraması, PDF ve seslendirmeli video. |
| `web/` | **Vercel sürümü** (13.11.2026): claude.ai panelinin bugünkü hali, verileriyle (bülten listesi, 255 haber, 45 kaynak, raporlar, PDF'ler). Haber toplama `web/api/topla.js`. Kayıtlar tarayıcıda saklanır. |
| `config/` | Hazır ayarlar: haber kaynakları, birimler, rapor türleri. Gizli anahtar yok. |
| `deploy/` | Kendi sunucusu için kurulum betiği, Caddy (otomatik HTTPS), günlük yedek. |
| `KURULUM.md` | Ayrıntılı kurulum ve kullanım (Türkçe). |

Depoda **hiçbir gizli bilgi yok**: Claude anahtarı, Telegram jetonu, kullanıcı listesi kurulumdan sonra panelin Ayarlar bölümünden girilir ve yalnızca sunucuda (`config/keys.json`, `config/users.json`) saklanır. Bu dosyalar `.gitignore` içinde.

## Depodan yayına alma

**Railway (önerilen, sunucu yönetmeden)**
1. railway.com → New Project → *Deploy from GitHub repo* → `tashkent-tijaret`.
2. Kökteki `Dockerfile` ve `railway.json` kendiliğinden kullanılır.
3. Bir **Volume** ekleyin, bağlama yolu `/kalici`; değişken `PERSIST_DIR=/kalici`.
4. Settings → Networking → *Generate Domain* (veya kendi alan adınız).
5. Deployments → Logs içindeki `İLK KURULUM KODU` ile giriş ekranında yönetici hesabını oluşturun, Ayarlar'dan Claude anahtarını girin.

**Kendi sunucunuz (Ahost VPS vb.)**
```bash
git clone https://github.com/rasulovj/tashkent-tijaret && cd tashkent-tijaret
cp .env.example .env && nano .env   # DOMAIN=panel.alanadiniz.uz  ACME_EMAIL=...
sh deploy/sunucu-kur.sh             # sonunda İLK KURULUM KODU yazar
```
Alan adının DNS A kaydı sunucu IP'sini göstermelidir. Ayrıntı: `KURULUM.md`.

**Vercel (web/ sürümü)**
Vercel → Add New → Project → bu depoyu Import → **Root Directory: `web`**, Framework: Other → Deploy. Ayrıntı: `web/BENIOKU.md`.

## Maliyet
Haber çevirisi Claude Haiku, bülten Claude Sonnet ile yapılır; panelde aylık 5 $ tavan var (`AI_MONTHLY_LIMIT_USD`), tahmini kullanım ~3 $/ay. Masraf yalnızca girilen Claude anahtarına yansır.

## Not
Sunucu sürümü 23.10.2026 tarihlidir. 12.11.2026'daki yenilikler (otomatik bülten, haber okuma penceresi, Kaynaklar sayfası, yeni rapor türleri) şimdilik yalnızca `web/` sürümündedir; sunucuya taşınmaları ayrı bir adımdır.
