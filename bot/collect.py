"""1. adım: RSS kaynaklarını tarar, yeni haberleri ham depoya (data/raw/items.jsonl) ekler.

Sık çalıştırılmak üzere tasarlandı (ör. 2 saatte bir): daha önce görülen haberler atlanır,
böylece hafta boyunca birikim olur.
"""
import calendar
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) TicaretBulteniBot/0.1"}
RAW = Path("data/raw/items.jsonl")


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


def load_raw():
    if not RAW.exists():
        return {}
    items = {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        if line.strip():
            it = json.loads(line)
            items[it["id"]] = it
    return items


def save_raw(items):
    RAW.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(items.values(), key=lambda x: x["published"], reverse=True)
    RAW.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def telegram_posts(handle):
    """Herkese açık Telegram kanalının web önizlemesinden (t.me/s/...) son gönderiler."""
    r = requests.get(f"https://t.me/s/{handle}", headers=UA, timeout=20)
    posts = []
    for block in r.text.split('class="tgme_widget_message_wrap')[1:]:
        m = re.search(r'data-post="([^"]+)"', block)
        txt = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        when = re.search(r'<time datetime="([^"]+)"', block)
        if not (m and txt and when):
            continue
        body = strip_html(re.sub(r"<br\s*/?>", "\n", txt.group(1)))
        photo = re.search(r"tgme_widget_message_photo_wrap[^>]*background-image:url\('([^']+)'\)", block)
        posts.append({"link": f"https://t.me/{m.group(1)}", "text": body,
                      "published": datetime.fromisoformat(when.group(1)).astimezone(timezone.utc).isoformat(),
                      "photo": photo.group(1) if photo else None})
    return posts


def collect(sources):
    items = load_raw()
    now = datetime.now(timezone.utc).isoformat()
    for src in sources:
        if src.get("enabled") is False:
            continue
        if src.get("kind") == "telegram":
            try:
                posts = telegram_posts(src["handle"])
            except requests.RequestException as e:
                print(f"  ! {src['name']}: {e}")
                continue
            new = 0
            for po in posts:
                item_id = hashlib.sha1(po["link"].encode()).hexdigest()[:12]
                if item_id in items or not po["text"]:
                    continue
                if src.get("filter") and not any(k in tr_lower(po["text"]) for k in src["filter"]):
                    continue
                first = re.split(r"(?<=[.!?])\s|\n", po["text"].strip(), 1)[0][:160]
                if src.get("require") and not all(any(k in tr_lower(po["text"]) for k in grp) for grp in src["require"]):
                    continue
                items[item_id] = {"id": item_id, "source": src["name"], "group": src.get("group", "Telegram"),
                                  "institution": src.get("institution"),
                                  "lang": src["lang"], "url": po["link"], "title": first, "summary": po["text"][:1500],
                                  "published": po["published"], "fetched_at": now, "text": po["text"],
                                  "thumb": po["photo"]}
                new += 1
            print(f"  {src['name']:22} {len(posts):3} kayıt, {new} yeni")
            continue
        if src.get("kind") == "mfa":  # Dışişleri temsilcilik sitesi: /Mission/Announcements
            try:
                html = requests.get(src["url"].rstrip("/") + "/Mission/Announcements", headers=UA, timeout=20).text
            except requests.RequestException as e:
                print(f"  ! {src['name']}: erişilemedi ({type(e).__name__})")
                continue
            new = 0
            base = re.match(r"https?://[^/]+", src["url"]).group(0)
            for href, text in re.findall(r'href="(/Mission/ShowAnnouncement/[^"]+)"[^>]*>(.*?)</a>', html, re.S):
                url, title = base + href, strip_html(text)
                item_id = hashlib.sha1(url.encode()).hexdigest()[:12]
                if not title or item_id in items:
                    continue
                items[item_id] = {"id": item_id, "source": src["name"], "group": src.get("group", ""), "lang": "tr",
                                  "institution": src.get("institution"), "url": url, "title": title, "summary": "",
                                  "published": now, "fetched_at": now, "text": None}
                new += 1
            print(f"  {src['name']:22} {new} yeni duyuru")
            continue
        try:
            r = requests.get(src["url"], headers=UA, timeout=20)
            feed = feedparser.parse(r.content)
        except requests.RequestException as e:
            print(f"  ! {src['name']}: {e}")
            continue
        new = 0
        for e in feed.entries:
            url = e.get("link")
            if not url:
                continue
            item_id = hashlib.sha1(url.encode()).hexdigest()[:12]
            if item_id in items:
                continue
            title, summary = strip_html(e.get("title")), strip_html(e.get("summary"))[:1500]
            publisher = None
            if src.get("publisher_from_title") and " - " in title:  # Google Haberler: "Başlık - Yayın"
                title, publisher = title.rsplit(" - ", 1)
                summary = "" if summary.startswith(title[:30]) else summary
            if src.get("filter") and not any(k in tr_lower(title + " " + summary) for k in src["filter"]):
                continue  # genel akış: yalnızca Özbekistan ile ilgili olanlar
            if src.get("require") and not all(any(k in tr_lower(title + " " + summary) for k in grp) for grp in src["require"]):
                continue  # kurum aramaları: kurum adı ve ülke birlikte geçmeli
            if src.get("exclude") and any(k in tr_lower(title + " " + summary) for k in src["exclude"]):
                continue  # konu dışı (ör. namaz/iftar vakitleri)
            t = e.get("published_parsed") or e.get("updated_parsed")
            published = (datetime.fromtimestamp(calendar.timegm(t), timezone.utc).isoformat()
                         if t else now)
            item = {
                "id": item_id,
                "source": src["name"],
                "group": src.get("group", ""),
                "lang": src["lang"],
                "url": url,
                "title": title,
                "summary": summary,
                "published": published,
                "fetched_at": now,
                "text": None,
            }
            if publisher:
                item["publisher"] = publisher
            if src.get("institution"):
                item["institution"] = src["institution"]
            img = next((m.get("url") for m in (e.get("media_content") or []) + (e.get("media_thumbnail") or []) if m.get("url")), None) \
                or next((x.get("href") for x in (e.get("enclosures") or []) if str(x.get("type", "")).startswith("image")), None)
            if img:  # haberin fotoğrafı (bültene birlikte gelir)
                item["thumb"] = img
            if src.get("kind") == "youtube":
                item["video"] = url
                thumbs = e.get("media_thumbnail") or []
                item["thumb"] = thumbs[0]["url"] if thumbs else None
            items[item_id] = item
            new += 1
        print(f"  {src['name']:22} {len(feed.entries):3} kayıt, {new} yeni")
    save_raw(items)
    return items
