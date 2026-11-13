"""Rapor veri bağlayıcıları: UN Comtrade (dış ticaret) ve Dünya Bankası (makro göstergeler).

Tüm yanıtlar data/cache altında önbelleklenir; aynı sorgu tekrar ağa gitmez.
"""
import hashlib
import json
import time
from pathlib import Path

import requests

CACHE = Path("data/cache")
UA = {"User-Agent": "Mozilla/5.0 TaskentTicaretRaporBot/0.1"}
COMTRADE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
WB = "https://api.worldbank.org/v2/country/{iso}/indicator/{ind}?format=json&per_page=100&date={y0}:{y1}"
_last_call = [0.0]

# Sık geçen ülkelerin Türkçe adları (Comtrade kodu -> ad)
TR_NAMES = {
    0: "Dünya", 4: "Afganistan", 31: "Azerbaycan", 36: "Avustralya", 40: "Avusturya", 56: "Belçika",
    76: "Brezilya", 112: "Belarus", 124: "Kanada", 156: "Çin", 203: "Çekya", 208: "Danimarka",
    251: "Fransa", 268: "Gürcistan", 276: "Almanya", 300: "Yunanistan", 344: "Hong Kong", 348: "Macaristan",
    364: "İran", 372: "İrlanda", 376: "İsrail", 380: "İtalya", 392: "Japonya", 398: "Kazakistan",
    410: "Güney Kore", 417: "Kırgızistan", 428: "Letonya", 440: "Litvanya", 458: "Malezya", 484: "Meksika",
    498: "Moldova", 528: "Hollanda", 586: "Pakistan", 616: "Polonya", 620: "Portekiz", 642: "Romanya",
    643: "Rusya", 682: "Suudi Arabistan", 699: "Hindistan", 702: "Singapur", 703: "Slovakya", 704: "Vietnam",
    705: "Slovenya", 724: "İspanya", 752: "İsveç", 757: "İsviçre", 762: "Tacikistan", 764: "Tayland",
    784: "BAE", 792: "Türkiye", 795: "Türkmenistan", 804: "Ukrayna", 818: "Mısır", 826: "Birleşik Krallık",
    842: "ABD", 860: "Özbekistan", 490: "Tayvan", 360: "Endonezya", 51: "Ermenistan", 246: "Finlandiya",
}

# Fasıl 94 (mobilya) 6'lı GTİP Türkçe kısa tanımları; olmayanlar İngilizce kalır
HS_TR = {
    "9401": "Oturmaya mahsus mobilyalar", "9402": "Tıpta kullanılan mobilyalar", "9403": "Diğer mobilyalar",
    "9404": "Somyalar, yataklar, yorganlar", "9405": "Aydınlatma cihazları", "9406": "Prefabrik yapılar",
    "940110": "Hava taşıtlarında kullanılan oturma yerleri", "940120": "Motorlu kara taşıtlarında kullanılan oturma yerleri",
    "940130": "Yüksekliği ayarlanabilir döner koltuklar", "940140": "Yatak haline getirilebilen oturma yerleri",
    "940161": "Ahşap iskeletli, döşenmiş oturma yerleri", "940169": "Ahşap iskeletli diğer oturma yerleri",
    "940171": "Metal iskeletli, döşenmiş oturma yerleri", "940179": "Metal iskeletli diğer oturma yerleri",
    "940180": "Diğer oturma yerleri", "940190": "Oturma yerlerinin aksam ve parçaları",
    "940191": "Oturma yerlerinin ahşap aksam ve parçaları", "940199": "Oturma yerlerinin diğer aksam ve parçaları",
    "940290": "Tıpta, cerrahide, dişçilikte kullanılan diğer mobilyalar",
    "940310": "Büro mobilyası (metal)", "940320": "Diğer metal mobilyalar", "940330": "Büro mobilyası (ahşap)",
    "940340": "Mutfak mobilyası (ahşap)", "940350": "Yatak odası mobilyası (ahşap)",
    "940360": "Diğer ahşap mobilyalar", "940370": "Plastik mobilyalar", "940389": "Diğer maddelerden mobilyalar",
    "940390": "Mobilya aksam ve parçaları", "940391": "Mobilyaların ahşap aksam ve parçaları",
    "940399": "Mobilyaların diğer aksam ve parçaları", "940410": "Somyalar", "940421": "Hücreli kauçuk/plastik yataklar",
    "940429": "Diğer yataklar", "940430": "Uyku tulumları", "940490": "Yorgan, yastık vb. diğer ürünler",
    "940511": "LED avize, tavan ve duvar aydınlatmaları", "940519": "Diğer avize, tavan ve duvar aydınlatmaları",
    "940521": "LED masa ve yatak başı lambaları", "940529": "Diğer masa ve yatak başı lambaları",
    "940542": "LED diğer elektrikli aydınlatma cihazları", "940549": "Diğer elektrikli aydınlatma cihazları",
    "940599": "Aydınlatma cihazlarının diğer aksam ve parçaları", "940610": "Ahşaptan prefabrik yapılar",
    "940690": "Diğer prefabrik yapılar",
}


def _cached(url, ttl_days=7):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
    if p.exists() and time.time() - p.stat().st_mtime < ttl_days * 86400:
        return json.loads(p.read_text())
    for attempt in range(4):
        wait = 2.2 - (time.time() - _last_call[0])  # Comtrade: saniyede ~1 istek
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        r = requests.get(url, headers=UA, timeout=60)
        if r.status_code == 429:
            time.sleep(3 + attempt * 2)
            continue
        r.raise_for_status()
        data = r.json()
        p.write_text(json.dumps(data))
        return data
    raise RuntimeError("Veri kaynağı yoğun (429), lütfen biraz sonra tekrar deneyin.")


def name(code, fallback=""):
    return TR_NAMES.get(int(code), fallback or str(code))


_hs_ref = {}


def hs_desc(code):
    if code in HS_TR:
        return HS_TR[code]
    if not _hs_ref:
        try:
            for x in _cached("https://comtradeapi.un.org/files/v1/app/reference/HS.json", 90)["results"]:
                _hs_ref[x["id"]] = x["text"].split(" - ", 1)[-1].strip(" -")
        except Exception:
            pass
    text = _hs_ref.get(code, code)
    return text if len(text) <= 80 else text[:77].rsplit(" ", 1)[0] + "…"


_partner_ref = {}


def partner_name(code):
    if int(code) in TR_NAMES:
        return TR_NAMES[int(code)]
    if not _partner_ref:
        try:
            for x in _cached("https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json", 90)["results"]:
                _partner_ref[int(x["id"])] = x["text"].strip()
        except Exception:
            pass
    return _partner_ref.get(int(code), str(code))


def comtrade(reporter, flow, period, cmd, partner=None):
    """Tek yıl sorgusu (önizleme API'si yılda 1 dönem ve 500 satır sınırlı)."""
    url = f"{COMTRADE}?reporterCode={reporter}&period={period}&cmdCode={cmd}&flowCode={flow}"
    if partner is not None:
        url += f"&partnerCode={partner}"
    rows = _cached(url).get("data") or []
    # Aynı satırın motorlu taşıt/kıyı tekrarlarını ayıkla (yalnızca toplam kayıt)
    return [r for r in rows if r.get("partner2Code") in (0, None) and r.get("customsCode") in ("C00", None)
            and r.get("motCode") in (0, None)]


def latest_year(reporter, cmd, start):
    """Verisi yayımlanmış en son yıl (start'tan geriye)."""
    for y in range(start, start - 4, -1):
        if comtrade(reporter, "M", y, cmd, 0):
            return y
    return start - 1


def worldbank(iso3, indicator, y0, y1):
    url = WB.format(iso=iso3, ind=indicator, y0=y0, y1=y1)
    data = _cached(url, ttl_days=3)
    rows = data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []
    return {int(r["date"]): r["value"] for r in rows if r["value"] is not None}


# ---------------------------------------------------------------- SIAT (Özbekistan İstatistik Ajansı)
SIAT = "https://siat.stat.uz/api/sdmx/{id}/{what}/?lang=en"


def siat_table(ind):
    """Bölge bazında yıllık seri: {bölge_en: {yıl: değer}}"""
    rows = _cached(SIAT.format(id=ind, what="table"), ttl_days=7)
    out = {}
    for r in rows:
        series = {}
        for d in r.get("data", []):
            for y, v in d.items():
                if v not in (None, "", "-") and str(y).isdigit():
                    try:
                        series[int(y)] = float(v)
                    except (TypeError, ValueError):
                        pass
        out[r["name_en"].strip()] = series
    return out


SIAT_UNITS_TR = {"thousand people": "bin kişi", "million usd": "milyon $", "billion soums": "milyar som",
                 "billions soums": "milyar som", "units": "adet", "unit": "adet", "soums": "som", "thousand soums": "bin som", "percent": "%"}


def siat_unit(ind):
    meta = _cached(SIAT.format(id=ind, what="metadata"), ttl_days=30)
    items = meta if isinstance(meta, list) else meta.get("meta_data") or meta.get("results") or [meta]
    for m in items:
        if isinstance(m, dict) and (m.get("name_en") or "").lower().startswith("unit"):
            v = (m.get("value_en") or "").strip()
            return SIAT_UNITS_TR.get(v.lower(), v)
    return ""


def regions():
    return json.loads(Path("config/regions.json").read_text(encoding="utf-8"))


def region_tr(en):
    return next((tr for tr, r in regions().items() if r["en"] == en), en)
