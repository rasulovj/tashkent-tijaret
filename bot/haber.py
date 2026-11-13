"""Haber → bülten akışı (22.10.2026): Türkçe çeviri önbelleği, rakam denetimi ve haberi bültene yazma.

- Yabancı dildeki başlık ve özetleri yalnızca Claude çevirir; makine çevirisine düşülmez.
- Her çeviride özgün metin ile Türkçe metnin rakamları karşılaştırılır; tutmayanlar uyarı olarak saklanır.
- "Bültene ekle": haber aday olarak kaydedilir (rakam doğrulaması bu metne göre yapılır), Claude yalnızca
  aday metnindeki bilgilerle bülten haberini yazar, haberin fotoğrafı bülten klasörüne indirilir.
"""
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

import requests

from bot import collect, writer

CACHE = Path("data/cache/feed_tr.json")
_lock = threading.Lock()
NUM = re.compile(r"\d+(?:[.,]\d+)*")
GLOSSARY = """Terim sözlüğü (her zaman bu karşılıkları kullan):
Yeni Taşkent = New Tashkent = Новый Ташкент = Yangi Toshkent
Ticaret Müşavirliği = Commercial Counsellor's Office = Торговое представительство
Dünya Bankası = World Bank = Всемирный банк = Jahon banki"""
TR_SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "string"}, "t": {"type": "string"}, "s": {"type": "string"}},
    "required": ["id", "t", "s"], "additionalProperties": False}}}, "required": ["items"], "additionalProperties": False}


def ai_ready():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def cache():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def _save(c):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


def digits(s):
    return {re.sub(r"\D", "", n) for n in NUM.findall(s or "") if len(re.sub(r"\D", "", n)) >= 2}


def num_diff(src, tr):
    """Özgün metinde olup çeviride olmayan ya da çeviride olup kaynakta olmayan rakamlar."""
    if not (tr or "").strip():
        return []
    s, b = digits(src), digits(tr)
    return [f"'{n}' çeviride yok" for n in sorted(s - b)] + [f"'{n}' kaynakta yok" for n in sorted(b - s)]


def _src_text(it):
    return (it.get("text") or it.get("summary") or "")[:600]


def translate_ids(ids, limit=25):
    """Verilen haberlerin başlık ve özetini Claude ile Türkçeye çevirir, rakamları denetler."""
    if not ai_ready():
        return {"done": 0, "message": "Claude anahtarı tanımlı değil; haberler özgün dilinde gösteriliyor (Ayarlar)."}
    raw, c = collect.load_raw(), cache()
    rows = [raw[i] for i in ids if i in raw and raw[i]["lang"] != "tr" and not (c.get(i) or {}).get("s")][:limit]
    if not rows:
        return {"done": 0}
    src = [{"id": r["id"], "dil": r["lang"], "baslik": r["title"], "ozet": _src_text(r)} for r in rows]
    system = ("Haber başlıklarını ve özetlerini Türkçeye çevir. Yalnızca çevir; bilgi ekleme, çıkarma ya da yorum yapma. "
              "Bütün rakamları, yüzdeleri, tarihleri, para birimlerini, kişi ve kurum adlarını kaynaktaki gibi koru "
              "(ondalık ayırıcı virgül: 7,8). Kurum adlarında Türkçe yerleşik karşılığı kullan; emin değilsen özgün adı yaz. "
              "Başlık tek cümle, haber başlığı üslubunda olsun.\n" + GLOSSARY)
    out = writer._call(system, json.dumps(src, ensure_ascii=False), TR_SCHEMA, kind="cevir")["items"]
    done = 0
    with _lock:
        c = cache()
        for x in out:
            r = next((y for y in rows if y["id"] == x["id"]), None)
            if not r or not x["t"]:
                continue
            warn = num_diff(r["title"] + " " + _src_text(r), x["t"] + " " + x["s"])
            c[r["id"]] = {"t": x["t"], "s": x["s"], "by": "claude", "warn": warn,
                          "at": datetime.now().isoformat(timespec="seconds")}
            done += 1
        _save(c)
    return {"done": done}


def translate_new(limit=40):
    """Otomatik taramadan sonra: en yeni, henüz çevrilmemiş haberleri çevirir (anahtar varsa)."""
    if not ai_ready():
        return 0
    c = cache()
    raw = sorted(collect.load_raw().values(), key=lambda x: x["published"], reverse=True)
    ids = [r["id"] for r in raw if r["lang"] != "tr" and not (c.get(r["id"]) or {}).get("s")][:limit]
    done = 0
    for i in range(0, len(ids), 20):
        done += translate_ids(ids[i:i + 20], 20).get("done", 0)
    return done


def row_extra(it, c):
    x = c.get(it["id"]) or {}
    if it["lang"] == "tr":
        return {}
    return {k: v for k, v in (("title_tr", x.get("t")), ("summary_tr", x.get("s")), ("tr_warn", x.get("warn") or []))
            if v is not None}


def _photo(issue, it):
    url = it.get("thumb")
    if not url:
        return None
    try:
        r = requests.get(url, headers=collect.UA, timeout=20)
        ctype = r.headers.get("Content-Type", "")
        if r.status_code != 200 or not ctype.startswith("image/") or len(r.content) < 2000:
            return None
        ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype.split(";")[0], ".jpg")
        issue.img_dir.mkdir(parents=True, exist_ok=True)
        name = f"haber-{it['id']}{ext}"
        (issue.img_dir / name).write_bytes(r.content)
        return {"file": name, "credit": it.get("publisher") or it["source"], "url": url, "show": True}
    except requests.RequestException:
        return None


def to_items(issue, ids):
    """Seçilen haberleri bülten haberine dönüştürür (her habere bir bülten haberi)."""
    raw = collect.load_raw()
    rows = [raw[i] for i in ids if i in raw]
    if not rows:
        raise ValueError("Haber bulunamadı.")
    cands = issue._read("candidates.json", [])
    new = []
    for r in rows:
        cid = "f-" + r["id"]
        cands = [x for x in cands if x["cid"] != cid]
        c = {"cid": cid, "title": r["title"], "text": r.get("text") or r.get("summary") or "", "source": r["source"],
             "url": r["url"], "lang": r["lang"], "published": r["published"], "score": 0}
        cands.append(c)
        new.append(c)
    issue._write("candidates.json", cands)
    c = cache()
    items = []
    if ai_ready():
        system = writer.STYLE_GUIDE
        prompt = (f"Editör aşağıdaki {len(new)} haberi bültene eklemek için seçti. Her aday için AYRI bir haber yaz "
                  "(birleştirme, eleme yapma; sıra aynı kalsın). YALNIZCA aday metnindeki bilgileri kullan: kaynakta "
                  "geçmeyen rakam, tarih, isim veya yorum ekleme. Kaynak kısa ise metin de kısa olsun (1-2 paragraf).\n"
                  + GLOSSARY + "\n\n" + "\n".join(
                      f"<aday id=\"{x['cid']}\" kaynak=\"{x['source']}\" dil=\"{x['lang']}\" tarih=\"{x['published']}\" "
                      f"url=\"{x['url']}\">\nBAŞLIK: {x['title']}\n{x['text']}\n</aday>" for x in new))
        items = writer._call(system, prompt, writer.DRAFT_SCHEMA)["items"][:len(new)]
        if len(items) != len(new):
            raise ValueError("Claude haberlerin hepsini yazmadı; yeniden deneyin.")
    else:
        for r in rows:
            x = c.get(r["id"]) or {}
            items.append({"headline": x.get("t") or r["title"], "paragraphs": [x.get("s") or r.get("summary") or ""],
                          "category": "diğer"})
    for it, r, cand in zip(items, rows, new):
        it["candidate_ids"] = [cand["cid"]]
        it["sources"] = [{"name": r.get("publisher") or r["source"], "url": r["url"]}]
        it["category"] = it.get("category") or "diğer"
        ph = _photo(issue, r)
        if ph:
            it["photo"] = ph
    return items
