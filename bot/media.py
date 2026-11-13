"""Kaynak haberlerden görsel ve bağlantı toplama.

- Haber sayfasının ana görseli (og:image) indirilir: data/<sayı>/img/src-<aday>.<uzantı>
- Sayfadaki video bağlantıları (YouTube) toplanır.
Görseller bültende kaynağıyla ("Görsel: Gazeta.uz") gösterilir; editör her haberde kapatabilir.
"""
import re
from pathlib import Path

import requests
import trafilatura

from bot.collect import UA

VIDEO = re.compile(r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([\w-]{11})")


def page_media(url):
    try:
        html = requests.get(url, headers=UA, timeout=20).text
    except requests.RequestException:
        return None, []
    meta = trafilatura.extract_metadata(html)
    image = meta.image if meta and meta.image and meta.image.startswith("http") else None
    vids = []
    for vid in VIDEO.findall(html):
        u = f"https://www.youtube.com/watch?v={vid}"
        if u not in vids:
            vids.append(u)
    return image, vids[:3]


def enrich(candidates):
    """Adaylara 'image' ve 'videos' ekler (bir kez; sonra önbellekte kalır)."""
    for c in candidates:
        if "image" in c:
            continue
        if "news.google.com" in c["url"]:
            c["image"], c["videos"] = None, []  # yönlendirme bağlantısı; sayfa açılamaz
            continue
        c["image"], c["videos"] = page_media(c["url"])
    return candidates


def download(url, dest_stem):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
    except requests.RequestException:
        return None
    ctype = r.headers.get("Content-Type", "")
    ext = {"image/webp": ".webp", "image/png": ".png", "image/gif": ".gif"}.get(ctype.split(";")[0], ".jpg")
    if not ctype.startswith("image/") or len(r.content) < 2000:
        return None
    p = Path(str(dest_stem) + ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return p.name


def attach(drafts, candidates, img_dir):
    """Taslaktaki her habere ilk adayın görselini (photo) ve video bağlantılarını (videos) ekler."""
    by_id = {c["cid"]: c for c in candidates}
    for it in drafts["items"]:
        cands = [by_id[c] for c in it.get("candidate_ids", []) if c in by_id]
        if "photo" not in it:
            for c in cands:
                if c.get("image"):
                    fname = download(c["image"], Path(img_dir) / f"src-{c['cid']}")
                    if fname:
                        it["photo"] = {"file": fname, "credit": c["source"], "url": c["image"], "show": True}
                        break
        if not it.get("videos"):
            vids = [v for c in cands for v in c.get("videos", [])]
            if vids:
                it["videos"] = [{"url": v, "title": "Haberle ilgili video"} for v in vids[:2]]
    return drafts
