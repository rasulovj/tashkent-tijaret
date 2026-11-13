"""Salt okunur önizleme sitesi: panelin o anki hâlini sabit dosyalara döker (Vercel'de barındırılır).

Çıktı: site/  (index.html + static/ + api/*.json + d/ dosyaları)
Gizli veriler (anahtarlar, kullanıcılar, Telegram, gelen kutusu) dışarıda bırakılır.
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import fitz

from bot import announce, render, tts
from bot.reports import builder as reports

OUT = Path("site")  # Vercel bu klasörü yayınlar (GitHub üzerinden)
MAX_PAGES = 12          # PDF görüntüleyicide gösterilecek en fazla sayfa
THUMB_W = 900


def slug(ref):
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(ref))


def _json(name, data):
    p = OUT / "api" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _copy(src, rel):
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)


def build(issue, resolve, progress=lambda m: None):
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "d").mkdir(parents=True)
    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    # --- uygulama kabuğu
    html = Path("static/panel.html").read_text(encoding="utf-8")
    html = html.replace('<script src="/static/i18n-uz.js"></script>',
                        f'<script>window.DEMO = true; window.DEMO_DATE = "{stamp}";</script>\n<script src="static/i18n-uz.js"></script>')
    (OUT / "index.html").write_text(html, encoding="utf-8")
    for f in ["i18n-uz.js", "kilavuz.html", "birim-kilavuzu.html"]:
        _copy(Path("static") / f, f"static/{f}")
    for f in Path("static/guide").glob("*"):
        _copy(f, f"static/guide/{f.name}")

    # --- durum (gizli alanlar temizlenmiş)
    progress("Veriler hazırlanıyor")
    st = issue.state()
    st["api"] = False
    st["settings"] = {"anthropic": False, "azure": False, "azure_region": "", "voices": {}}
    st["inbox_new"] = 0
    for f in st["files"]:
        f["pages"] = min(f["pages"], MAX_PAGES)
    st["decks"] = [d for d in st.get("decks", []) if d["name"].endswith(".pdf")]
    _json("state", st)
    _json("feed", issue.feed()[:600])
    _json("inst", issue.institutions())
    _json("reports", reports.list_reports())
    _json("report-types", reports.types())
    for r in reports.list_reports():
        _json(f"report-{slug(r['id'])}", reports.load(r["id"]))
    anns = announce.list_all()
    _json("ann-list", anns)
    for lang in ("tr", "uz", "en", "ru"):
        _json(f"ann-special-{lang}", announce.special_days(lang))
        _json(f"voices-{lang}", tts.voices(lang))
    _json("sub-all", {"items": [], "statuses": {}, "types": {}})
    _json("telegram", {"connected": False, "bot": None, "channels": [], "log": []})
    _json("settings", st["settings"])
    _json("users", {"users": [], "network": {"lan": False}, "ip": None, "port": 0, "bound": ""})
    _json("me", {"username": "onizleme", "name": "Önizleme", "role": "yonetici"})
    try:
        from bot import charts
        _json("rates", {"today": charts.today_rates(), "USD": charts.history("USD"), "TRY": charts.history("TRY")})
    except Exception:
        pass

    # --- dosyalar: PDF'ler, sayfa görüntüleri, videolar, slaytlar, görseller
    progress("PDF sayfaları resimleniyor")
    (OUT / "d/thumb").mkdir(parents=True, exist_ok=True)
    for f in st["files"]:
        src = resolve(f["ref"])
        _copy(src, f"d/file/{slug(f['ref'])}")
        render.compress_pdf(OUT / f"d/file/{slug(f['ref'])}")
        with fitz.open(src) as doc:
            for i in range(min(doc.page_count, MAX_PAGES)):
                pg = doc[i]
                z = THUMB_W / pg.rect.width
                pg.get_pixmap(matrix=fitz.Matrix(z, z)).save(OUT / f"d/thumb/{slug(f['ref'])}-{i}.jpg", jpg_quality=72)
    for v in st.get("videos", [])[:1]:  # yalnızca son video (boyut sınırı)
        _copy(resolve(v["ref"]), f"d/file/{slug(v['ref'])}")
    st_videos = st.get("videos", [])[:1]
    for dk in st["decks"]:
        _copy(resolve(dk["ref"]), f"d/file/{slug(dk['ref'])}")
        render.compress_pdf(OUT / f"d/file/{slug(dk['ref'])}")
    for s in st.get("slides", []):
        pix = fitz.Pixmap(str(resolve("slide:" + s)))
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)
        (OUT / "d/file").mkdir(parents=True, exist_ok=True)
        pix.save(OUT / f"d/file/{slug('slide:' + s)}", output="jpg", jpg_quality=78)  # adı .png ama içerik JPEG; tarayıcı tanır
    if issue.img_dir.exists():
        for img in issue.img_dir.iterdir():
            if img.is_file():
                _copy(img, f"d/img/{img.name}")
                _copy(img, f"d/file/{slug('img:' + img.name)}")
    for a in anns:
        for o in a["outputs"]:
            _copy(resolve(o["ref"]), f"d/file/{slug(o['ref'])}")
        if a.get("photo"):
            _copy(announce._dir(a["id"]) / a["photo"], f"d/ann-photo/{a['id']}{Path(a['photo']).suffix}")
            _copy(announce._dir(a["id"]) / a["photo"], f"d/file/{slug('ann:' + a['id'] + '/' + a['photo'])}")
    st["videos"] = st_videos
    _json("state", st)

    # --- önizleme sayfaları (anlık görüntü)
    progress("Önizleme sayfaları hazırlanıyor")
    for lang in ("tr", "en", "ru", "uz"):
        d = issue.lang_drafts(lang)
        if d:
            (OUT / f"d/preview-{lang}.html").write_text(render.build_html(d, issue.date, lang, review=False), encoding="utf-8")
    for r in reports.list_reports():
        (OUT / f"d/report-{slug(r['id'])}.html").write_text(reports.build_html(reports.load(r["id"])), encoding="utf-8")
    for a in anns:
        purl = f"ann-photo/{a['id']}{Path(a['photo']).suffix}" if a.get("photo") else None
        for fmt in announce.FORMATS:
            (OUT / f"d/ann-{slug(a['id'])}-{fmt}.html").write_text(announce.html(a, fmt, photo_url=purl), encoding="utf-8")

    (OUT / "vercel.json").write_text(json.dumps({
        "cleanUrls": False,
        "headers": [{"source": "/(.*)", "headers": [{"key": "X-Robots-Tag", "value": "noindex, nofollow"}]}]
    }, indent=1))
    files = [p for p in OUT.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    return {"files": len(files), "mb": round(size / 1024 / 1024, 1), "stamp": stamp}
