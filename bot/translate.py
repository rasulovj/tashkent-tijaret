"""Çeviri katmanı: Türkçe arama sorgusunu kaynak dillere, sonuçları Türkçeye çevirir.

Sağlayıcı sırası: Claude (ANTHROPIC_API_KEY varsa; sınırsız, kaliteli) -> MyMemory (ücretsiz,
anahtarsız; günde ~5.000 karakter). Her çeviri data/cache/translations.json'da saklanır, tekrar istenmez.
"""
import hashlib
import html
import json
import os
import threading
from pathlib import Path

import requests

CACHE = Path("data/cache/translations.json")
_lock = threading.Lock()
_mem = None
_quota_hit = [False]
NAMES = {"tr": "Türkçe", "en": "İngilizce", "ru": "Rusça", "uz": "Özbekçe"}


def _cache():
    global _mem
    if _mem is None:
        _mem = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    return _mem


def _key(text, src, tgt):
    return f"{src}>{tgt}:" + hashlib.sha1(text.encode()).hexdigest()[:16]


def _save():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(_mem, ensure_ascii=False), encoding="utf-8")


def provider():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "Claude"
    return "MyMemory (ücretsiz, günlük sınırlı)" if not _quota_hit[0] else "yok (günlük ücretsiz kota doldu)"


def _claude(texts, src, tgt):
    from bot import writer
    schema = {"type": "object", "properties": {"t": {"type": "array", "items": {"type": "string"}}},
              "required": ["t"], "additionalProperties": False}
    system = (f"{NAMES.get(src, src)} metinleri {NAMES[tgt]} diline çevir. Ekonomi haberi başlıkları; "
              f"kurum ve özel adları yerleşik {NAMES[tgt]} karşılıklarıyla yaz. Aynı sırayla, aynı sayıda döndür.")
    out = writer._call(system, json.dumps(texts, ensure_ascii=False), schema, kind="cevir")["t"]
    return out if len(out) == len(texts) else [None] * len(texts)


def _mymemory(text, src, tgt):
    if _quota_hit[0]:
        return None
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text[:480], "langpair": f"{src}|{tgt}"}, timeout=15)
        j = r.json()
    except (requests.RequestException, ValueError):
        return None
    if j.get("quotaFinished") or j.get("responseStatus") in (429, "429"):
        _quota_hit[0] = True
        return None
    t = (j.get("responseData") or {}).get("translatedText")
    return html.unescape(t) if t and "MYMEMORY WARNING" not in t else None


def cached(text, src, tgt):
    t = _cache().get(_key(text, src, tgt))
    return html.unescape(t) if t else t


def translate_many(texts, src, tgt, limit=60):
    """Önbellekte olmayanları çevirir (en fazla `limit` tane); sözlük {metin: çeviri} döner."""
    with _lock:
        c = _cache()
        out, todo = {}, []
        for t in texts:
            if not t or src == tgt:
                out[t] = t
            elif _key(t, src, tgt) in c:
                out[t] = c[_key(t, src, tgt)]
            elif len(todo) < limit:
                todo.append(t)
        if todo:
            if os.environ.get("ANTHROPIC_API_KEY"):
                res = []
                for i in range(0, len(todo), 40):
                    res += _claude(todo[i:i + 40], src, tgt)
            else:
                res = [_mymemory(t, src, tgt) for t in todo]
            for t, r in zip(todo, res):
                if r:
                    c[_key(t, src, tgt)] = r
                    out[t] = r
            _save()
        return out


def translate(text, src, tgt):
    return translate_many([text], src, tgt).get(text)
