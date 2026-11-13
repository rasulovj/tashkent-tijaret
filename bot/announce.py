"""Duyuru, ilan, etkinlik ve haber tasarımları.

Her kayıt data/duyurular/<id>/duyuru.json'da saklanır. Çıktılar (aynı klasörde):
kare / dikey / yatay PNG (sosyal medya), A4 afiş PDF ve Telegram metni.
"""
import json
import re
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from bot import render

STORE = Path("data/duyurular")
KINDS = {
    "etkinlik": {"tr": "Etkinlik", "uz": "Tadbir", "en": "Event", "ru": "Мероприятие", "color": "#8B1A1A"},
    "duyuru": {"tr": "Duyuru", "uz": "E’lon", "en": "Announcement", "ru": "Объявление", "color": "#2f6db5"},
    "ilan": {"tr": "İlan", "uz": "E’lon", "en": "Notice", "ru": "Извещение", "color": "#a35f00"},
    "haber": {"tr": "Haber", "uz": "Yangilik", "en": "News", "ru": "Новость", "color": "#1e7a3c"},
    "kutlama": {"tr": "Kutlama", "uz": "Bayram", "en": "Celebration", "ru": "Праздник", "color": "#C0392B"},
    "anma": {"tr": "Anma", "uz": "Xotira", "en": "Commemoration", "ru": "Память", "color": "#3a3a3a"},
}
THEMES = {
    "bordo": {"primary": "#8B1A1A", "bg": "#FBF7F4", "ink": "#1d1d1f", "muted": "#6b6460", "accent": "#C0392B",
              "soft": "#F3E4DE", "foot": "#241a1a", "footInk": "#d9cfcc"},
    "lacivert": {"primary": "#14325C", "bg": "#F4F7FB", "ink": "#14213a", "muted": "#5d6b80", "accent": "#2F6DB5",
                 "soft": "#DCE6F3", "foot": "#0f1f38", "footInk": "#cfd9e8"},
    "bayram": {"primary": "#C8102E", "bg": "#FFFFFF", "ink": "#1d1d1f", "muted": "#5c5c5c", "accent": "#C8102E",
               "soft": "#FBE3E6", "foot": "#9E0B22", "footInk": "#ffe9ec"},
    "anma": {"primary": "#2b2b2b", "bg": "#F3F2F0", "ink": "#151515", "muted": "#555555", "accent": "#7a7a7a",
             "soft": "#DCDAD6", "foot": "#151515", "footInk": "#cfcfcf"},
    "gece": {"primary": "#8B1A1A", "bg": "#17171B", "ink": "#F4F1EE", "muted": "#A8A3A0", "accent": "#E07A5F",
             "soft": "#2A2A30", "foot": "#000000", "footInk": "#bbbbbb"},
}
FORMATS = {  # ad: (genişlik, yükseklik, açıklama)
    "kare": (1080, 1080, "Kare – Instagram / Telegram"),
    "dikey": (1080, 1350, "Dikey 4:5 – Instagram"),
    "yatay": (1600, 900, "Yatay 16:9 – web / sunum"),
    "afis": (1240, 1754, "A4 afiş – yazdırılabilir PDF"),
}
LABELS = {
    "tr": {"office": "T.C. TAŞKENT BÜYÜKELÇİLİĞİ · TİCARET MÜŞAVİRLİĞİ", "office_full": "T.C. Taşkent Büyükelçiliği Ticaret Müşavirliği",
           "site": "Akademik Yahya Gulyamov Ko’chasi No:87 Taşkent", "deadline": "Son başvuru", "scan": "Kayıt / ayrıntı için okutun",
           "placeholder": "Başlık yazın", "months": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]},
    "uz": {"office": "TURKIYA ELCHIXONASI · SAVDO MASLAHATCHILIGI", "office_full": "Turkiya Respublikasining Toshkentdagi Elchixonasi Savdo maslahatchiligi",
           "site": "Akademik Yahyo G‘ulomov ko‘chasi, 87, Toshkent", "deadline": "Ariza muddati", "scan": "Ro‘yxatdan o‘tish uchun skanerlang",
           "placeholder": "Sarlavha yozing", "months": ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"]},
    "en": {"office": "EMBASSY OF TÜRKİYE · COMMERCIAL COUNSELLOR'S OFFICE", "office_full": "Commercial Counsellor's Office, Embassy of Türkiye in Tashkent",
           "site": "87 Akademik Yahya Gulyamov St., Tashkent", "deadline": "Deadline", "scan": "Scan to register / details",
           "placeholder": "Enter a title", "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]},
    "ru": {"office": "ПОСОЛЬСТВО ТУРЦИИ · ТОРГОВОЕ ПРЕДСТАВИТЕЛЬСТВО", "office_full": "Торговое представительство Посольства Турции в Ташкенте",
           "site": "ул. Академика Яхьи Гулямова, 87, Ташкент", "deadline": "Срок подачи", "scan": "Сканируйте для регистрации",
           "placeholder": "Введите заголовок", "months": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]},
}
FIELDS = ("kind", "lang", "theme", "title", "subtitle", "text", "date", "date_end", "time", "place", "deadline",
          "link", "contact", "tag", "photo", "status")


def _dir(aid):
    return STORE / Path(aid).name


def new(kind="etkinlik", lang="tr"):
    import secrets
    aid = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)  # aynı saniyede iki kayıt çakışmasın
    a = {"id": aid, "kind": kind, "lang": lang, "theme": "bordo", "title": "", "subtitle": "", "text": "",
         "date": "", "date_end": "", "time": "", "place": "", "deadline": "", "link": "", "contact": "", "tag": "",
         "photo": None, "status": "taslak", "created": datetime.now().isoformat(timespec="seconds")}
    save(a)
    return a


def load(aid):
    return json.loads((_dir(aid) / "duyuru.json").read_text(encoding="utf-8"))


def save(a):
    d = _dir(a["id"])
    d.mkdir(parents=True, exist_ok=True)
    a["updated"] = datetime.now().isoformat(timespec="seconds")
    (d / "duyuru.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return a


def update(aid, values):
    a = load(aid)
    for k in FIELDS:
        if k in values:
            a[k] = values[k]
    return save(a)


def delete(aid):
    shutil.rmtree(_dir(aid), ignore_errors=True)


def outputs(aid):
    d = _dir(aid)
    return [{"name": p.name, "ref": f"ann:{aid}/{p.name}"} for p in sorted(d.glob("*")) if p.suffix in (".png", ".pdf") and not p.name.startswith("foto")]


def list_all():
    out = []
    for p in STORE.glob("*/duyuru.json"):
        a = json.loads(p.read_text(encoding="utf-8"))
        a["outputs"] = outputs(a["id"])
        a["caption"] = caption(a)
        out.append(a)
    # yaklaşan etkinlikler önce, sonra en yeni
    today = date.today().isoformat()
    return sorted(out, key=lambda a: (0 if (a.get("date") or "") >= today else 1, a.get("date") or "9999", a.get("updated", "")))


def _fmt_date(s, lang):
    try:
        d = date.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return d


def html(a, fmt, photo_url=None):
    W, H = FORMATS[fmt][:2]
    L = LABELS[a.get("lang", "tr")]
    K = {"label": KINDS[a["kind"]][a.get("lang", "tr")], "color": KINDS[a["kind"]]["color"]}
    d1, d2 = _fmt_date(a.get("date"), a["lang"]), _fmt_date(a.get("date_end"), a["lang"])
    dd = None
    if d1:
        dd = {"day": d1.day if not d2 or d2 == d1 else f"{d1.day}–{d2.day}" if d2.month == d1.month else d1.day,
              "month": L["months"][d1.month - 1], "year": d1.year,
              "end": f"{d2.day} {L['months'][d2.month - 1]}" if d2 and d2.month != d1.month else ""}
    dl = _fmt_date(a.get("deadline"), a["lang"])
    photo = None
    if a.get("photo") and (_dir(a["id"]) / a["photo"]).exists():
        photo = photo_url or (_dir(a["id"]) / a["photo"]).resolve().as_uri()  # önizlemede http, çıktıda dosya yolu
    layout = {"kare": (35, 44, 4.8, not photo), "dikey": (36, 44, 5.4, True), "yatay": (0, 13, 5.0, not photo),
              "afis": (32, 41, 5.0, True)}[fmt]
    photo_h, body_top, title_size, show_text = layout
    if not photo and fmt != "yatay":
        body_top = 12
    title_len = len(a.get("title") or "")
    if title_len > 70:
        title_size *= 0.8
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    return env.get_template("announce.html").render(
        a=a, fmt="wide" if fmt == "yatay" else ("poster" if fmt == "afis" else fmt), W=W, H=H, U=min(W, H) / 100,
        T=THEMES[a.get("theme", "bordo")], K=K, L=L, d=dd, deadline=f"{dl.day} {L['months'][dl.month - 1]} {dl.year}" if dl else a.get("deadline"),
        photo=photo, photo_h=photo_h, body_top=body_top, title_size=title_size, show_text=show_text and bool(a.get("text")),
        qr=render.qr_svg)


def produce(aid, fmt):
    a = load(aid)
    d = _dir(aid).resolve()
    W, H = FORMATS[fmt][:2]
    page = d / f"_{fmt}.html"
    page.write_text(html(a, fmt), encoding="utf-8")
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    stem = re.sub(r"[^a-z0-9]+", "-", (a.get("title") or "duyuru").translate(tr).lower())[:40].strip("-") or "duyuru"
    if fmt == "afis":
        out = d / f"{stem}-afis.pdf"
        subprocess.run([render.CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True)
    else:
        out = d / f"{stem}-{fmt}.png"
        subprocess.run([render.CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={W},{H}", f"--screenshot={out}", page.as_uri()], check=True, capture_output=True)
    page.unlink(missing_ok=True)
    return out


def caption(a):
    """Telegram / sosyal medya metni."""
    L = LABELS[a.get("lang", "tr")]
    icon = {"etkinlik": "📅", "duyuru": "📢", "ilan": "📌", "haber": "📰", "kutlama": "🇹🇷", "anma": "🕊"}[a["kind"]]
    if a["kind"] in ("kutlama", "anma"):  # tebrik / anma metni: tarih ve yer satırları yok
        body = [f"{icon} {a.get('title', '').strip()}", ""] + [x.strip() for x in (a.get("subtitle"), a.get("text")) if x]
        return "\n".join(body + ["", L["office_full"]]).strip()[:1024]
    lines = [f"{icon} {a.get('title', '').strip()}"]
    if a.get("subtitle"):
        lines.append(a["subtitle"].strip())
    lines.append("")
    d1 = _fmt_date(a.get("date"), a["lang"])
    if d1:
        when = f"{d1.day} {L['months'][d1.month - 1]} {d1.year}"
        d2 = _fmt_date(a.get("date_end"), a["lang"])
        if d2 and d2 != d1:
            when += f" – {d2.day} {L['months'][d2.month - 1]} {d2.year}"
        lines.append(f"🗓 {when}" + (f" · {a['time']}" if a.get("time") else ""))
    if a.get("place"):
        lines.append(f"📍 {a['place']}")
    dl = _fmt_date(a.get("deadline"), a["lang"])
    if dl:
        lines.append(f"⏳ {L['deadline']}: {dl.day} {L['months'][dl.month - 1]} {dl.year}")
    if a.get("text"):
        lines += ["", a["text"].strip()]
    if a.get("contact"):
        lines += ["", f"✉ {a['contact']}"]
    if a.get("link"):
        lines.append(f"🔗 {a['link']}")
    lines += ["", L["office_full"]]
    return "\n".join(lines).strip()[:1024]


def translate_copy(aid, lang):
    """Duyurunun başka dilde kopyasını oluşturur (Claude anahtarı varsa Claude, yoksa ücretsiz çeviri)."""
    from bot import translate
    a = load(aid)
    b = new(a["kind"], lang)
    texts = [a.get(k) or "" for k in ("title", "subtitle", "text", "place", "tag")]
    tr = translate.translate_many([t for t in texts if t], a.get("lang", "tr"), lang, limit=10)
    vals = {k: (tr.get(a.get(k)) or a.get(k) or "") for k in ("title", "subtitle", "text", "place", "tag")}
    vals.update({k: a.get(k) for k in ("date", "date_end", "time", "deadline", "link", "contact", "theme")})
    if a.get("photo"):
        shutil.copy(_dir(aid) / a["photo"], _dir(b["id"]) / a["photo"])
        vals["photo"] = a["photo"]
    return update(b["id"], vals)


def set_photo(aid, data=None, name=None, from_path=None):
    import base64
    a = load(aid)
    d = _dir(aid)
    for old in d.glob("foto.*"):
        old.unlink()
    if from_path:
        ext = Path(from_path).suffix or ".jpg"
        shutil.copy(from_path, d / f"foto{ext}")
    elif data:
        ext = Path(name or "x.jpg").suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValueError("Yalnızca JPG, PNG veya WEBP görsel yüklenebilir.")
        (d / f"foto{ext}").write_bytes(base64.b64decode(data.split(",", 1)[-1]))
    else:
        return update(aid, {"photo": None})
    return update(aid, {"photo": f"foto{ext}"})


# ---------------------------------------------------------------- özel günler (kutlama / anma)
SPECIAL = Path("config/ozel_gunler.json")


def special_days(lang="tr", within=None):
    """Takvim: bir sonraki tarih ve yıl dönümü sayısıyla. Tarihi değişen bayramlarda date = None."""
    today = date.today()
    out = []
    for d in json.loads(SPECIAL.read_text(encoding="utf-8")):
        nxt = None
        if d.get("month"):
            nxt = date(today.year, d["month"], d["day"])
            if nxt < today:
                nxt = date(today.year + 1, d["month"], d["day"])
        year = nxt.year if nxt else today.year
        n = year - d["base"] if d.get("base") else None
        t = d.get(lang) or d["tr"]
        fill = lambda x: x.replace("{n}", str(n or "")).replace("{year}", str(year))
        item = {"key": d["key"], "kind": d["kind"], "country": d.get("country"), "date": nxt.isoformat() if nxt else None,
                "days_left": (nxt - today).days if nxt else None, "n": n,
                "title": fill(t["title"]), "greeting": fill(t["greeting"]), "text": fill(t.get("text", ""))}
        if within is None or (item["days_left"] is not None and item["days_left"] <= within):
            out.append(item)
    return sorted(out, key=lambda x: (x["days_left"] is None, x["days_left"] or 0))


def from_special(key, lang="tr"):
    d = next(x for x in special_days(lang) if x["key"] == key)
    a = new(d["kind"], lang)
    return update(a["id"], {"title": d["title"], "subtitle": d["greeting"], "text": d["text"], "date": d["date"] or "",
                            "theme": "anma" if d["kind"] == "anma" else "bayram", "tag": ""})
