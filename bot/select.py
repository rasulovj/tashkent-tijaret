"""2. adım: Haftanın ham haberlerinden ekonomiyle ilgili adayları seçer.

- Anahtar kelime puanı (ekonomi, ticaret, yatırım, Türkiye ...)
- Aynı haberin farklı sitelerdeki kopyalarını kümeler (başlık benzerliği)
- En iyi adayların tam metnini çeker
Çıktı: data/<sayı>/candidates.json  (YZ yazım adımının girdisi)

Not: Üretim sürümünde kümeleme için embedding (pgvector) önerilir; burada basit
kelime örtüşmesi kullanılıyor.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import requests
import trafilatura

from bot.collect import UA, save_raw

KEYWORDS = {
    3: ["türkiye", "turkey", "turkish", "турци", "турец", "türk "],
    2: ["invest", "инвест", "export", "экспорт", "import", "импорт", "trade", "торгов",
        "gdp", "ввп", "economy", "экономик", "billion", "млрд", "million", "млн", "$",
        "tariff", "тариф", "tax", "налог", "logistic", "логист", "railway", "железн",
        "energy", "энерг", "solar", "wind", "ветр", "солнеч", "bank", "банк", "inflation",
        "инфляц", "world bank", "всемирный банк", "imf", "мвф", "adb", "ebrd", "ербр",
        "free economic zone", "свободн", "industrial", "промышлен", "privatiz", "приватиз",
        "customs", "тамож", "agreement", "соглашен", "project", "проект",
        "ekonomi", "ticaret", "yatırım", "ihracat", "ithalat", "milyar", "milyon", "enerji", "anlaşma",
        "fabrika", "ihale", "vergi", "gümrük", "lojistik", "demiryolu", "tekstil", "banka", "enflasyon",
        "büyüme", "serbest bölge", "sanayi", "iş birliği", "işbirliği", "heyet", "fuar", "doğalgaz"],
    1: ["company", "компани", "price", "цен", "market", "рын", "plant", "завод",
        "factory", "фабрик", "construction", "строител", "tender", "budget", "бюджет",
        "decree", "указ", "постановлен", "resolution"],
}
NEGATIVE = ["futbol", "maç", "konser", "dizi", "magazin", "kaza", "cinayet", "football", "футбол", "olympi", "concert", "weather", "погод", "crime",
            "detained", "задержан", "опий", "drug", "наркот", "deport", "accident", "дтп",
            "wrestl", "boxing", "chess", "film festival"]


def score(item):
    text = (item["title"] + " " + item["summary"]).replace("İ", "i").replace("I", "ı").lower()
    s = sum(w for w, kws in KEYWORDS.items() for k in kws if k in text)
    s -= 4 * sum(1 for k in NEGATIVE if k in text)
    return s


def tokens(s):
    return {t for t in re.findall(r"[\wа-яё]{4,}", s.lower())}


def cluster(items, threshold=0.45):
    """Başlık kelime örtüşmesiyle (Jaccard) kopya haberleri gruplar."""
    clusters = []
    for it in items:
        tk = tokens(it["title"])
        for c in clusters:
            inter = len(tk & c["tokens"])
            union = len(tk | c["tokens"]) or 1
            if inter / union >= threshold:
                c["items"].append(it)
                c["tokens"] |= tk
                break
        else:
            clusters.append({"tokens": tk, "items": [it]})
    return clusters


def fetch_text(item):
    try:
        r = requests.get(item["url"], headers=UA, timeout=20)
        text = trafilatura.extract(r.text, include_comments=False, include_tables=False)
    except requests.RequestException:
        text = None
    return (text or item["summary"])[:6000]


def select(items, cfg, out_dir):
    since = datetime.now(timezone.utc) - timedelta(days=cfg["window_days"])
    week = [it for it in items.values()
            if datetime.fromisoformat(it["published"]) >= since]
    for it in week:
        it["score"] = score(it)
    relevant = sorted([it for it in week if it["score"] >= 3],
                      key=lambda x: x["score"], reverse=True)
    clusters = cluster(relevant)[: cfg["max_candidates"]]
    print(f"  {len(week)} haber bu hafta -> {len(relevant)} ilgili -> {len(clusters)} aday küme")

    candidates = []
    for i, c in enumerate(clusters, 1):
        main = c["items"][0]
        if not main.get("text"):
            main["text"] = fetch_text(main)
        candidates.append({
            "cid": f"c{i:02d}",
            "score": main["score"],
            "title": main["title"],
            "source": main["source"],
            "lang": main["lang"],
            "url": main["url"],
            "published": main["published"][:10],
            "also_in": [{"source": o["source"], "url": o["url"]} for o in c["items"][1:]],
            "text": main["text"],
        })
    from bot import media
    media.enrich(candidates)  # görseller ve video bağlantıları
    save_raw(items)  # tam metinler önbelleğe
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=1), encoding="utf-8")
    return candidates
