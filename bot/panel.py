"""Editör paneli: genel bakış, haber akışı, kaynaklar, bülten editörü, görsel stüdyo, PDF'ler.

Yalnızca bu bilgisayardan erişilir (127.0.0.1). Bağımlılık yok: standart http.server.
  python run.py panel   ->  http://127.0.0.1:8765
"""
import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import threading
import traceback
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import fitz  # PyMuPDF: PDF sayfalarını görüntüye çevirir

from bot import announce, auth, charts, demo, haber, inbox, vercel, collect, render, settings, telegram, translate, tts, verify, video, writer
from bot.reports import ai as report_ai, builder as reports

STATIC = Path("static")
CONFIG = Path("config/sources.json")
LANGS = ["tr", "en", "ru", "uz"]
LOCK = threading.Lock()
REPORT_LOCK = threading.Lock()
UPLOADS = Path("data/uploads")
INST_CFG = Path("config/institutions.json")
INST_MSG = Path("data/kurum_mesajlari.json")
VIDEO_JOB = {}
DECK_JOB = {}
WEB_JOB = {}
SCAN = {"last": None, "next": None, "added": None, "running": False}


def latest_issue_dir():
    dirs = sorted(p for p in Path("data").iterdir()
                  if p.is_dir() and (p / "candidates.json").exists())
    if not dirs:
        raise SystemExit("Henüz sayı yok - önce 'python run.py all' çalıştırın.")
    return dirs[-1]


def safe_name(name):
    return Path(unquote(name)).name  # klasör dışına çıkılamaz


def resolve(ref, issue):
    """Dosya referansı -> yol. 'issue:ad.pdf', 'report:<id>/ad.pdf', 'upload:ad.pdf', 'img:ad.png'"""
    kind, _, rest = unquote(ref or "").partition(":")
    if kind == "issue":
        p = issue.dir / safe_name(rest)
    elif kind == "report":
        rid, _, name = rest.partition("/")
        p = reports.path(rid) / safe_name(name)
    elif kind == "upload":
        p = UPLOADS / safe_name(rest)
    elif kind == "img":
        p = issue.img_dir / safe_name(rest)
    elif kind == "video":
        p = issue.dir / "video" / safe_name(rest)
    elif kind == "slide":
        p = issue.dir / "video" / "slides" / safe_name(rest)
    elif kind == "deck":
        p = issue.dir / "sunum" / safe_name(rest)
    elif kind == "ann":
        aid, _, name = rest.partition("/")
        p = announce._dir(aid) / safe_name(name)
    elif kind == "sub":
        sid, _, name = rest.partition("/")
        p = inbox._dir(sid) / safe_name(name)
    elif kind == "sample":
        p = Path("data/cache") / safe_name(rest)
    else:
        raise ValueError("Geçersiz dosya referansı")
    if not p.exists():
        raise ValueError(f"Dosya bulunamadı: {p.name}")
    return p


class Issue:
    def __init__(self, out_dir):
        self.dir = out_dir
        y, m, d = out_dir.name.split("-")
        self.date = f"{d}.{m}.{y}"
        self.img_dir = out_dir / "img"
        self.last_scan = None

    def _read(self, name, default=None):
        p = self.dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    def _write(self, name, data):
        (self.dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                     encoding="utf-8")

    @staticmethod
    def content_hash(drafts):
        """Çeviriyi etkileyen içerik (görseller hariç)."""
        core = [[it["headline"], it["paragraphs"], it["sources"]] for it in drafts["items"]]
        return hashlib.sha1(json.dumps(core, ensure_ascii=False).encode()).hexdigest()[:12]

    @staticmethod
    def approval_hash(drafts):
        """Onayı etkileyen içerik (görseller dahil)."""
        core = [[it["headline"], it["paragraphs"], it["sources"], it.get("image"), it.get("image_caption"),
                 it.get("photo"), it.get("videos")] for it in drafts["items"]]
        return hashlib.sha1(json.dumps(core, ensure_ascii=False).encode()).hexdigest()[:12]

    def drafts(self):
        return self._read("drafts.json", {"items": []})

    def meta(self):
        meta = self._read("meta.json")
        if meta is None:  # ilk açılış: mevcut çevirileri güncel kabul et
            h = self.content_hash(self.drafts())
            meta = {"translations": {l: h for l in LANGS[1:]
                                     if (self.dir / f"drafts.{l}.json").exists()},
                    "approved": None, "history": []}
            self._write("meta.json", meta)
        return meta

    def log(self, who, action):
        meta = self.meta()
        meta["history"].append({"at": datetime.now().isoformat(timespec="seconds"),
                                "who": who, "action": action})
        self._write("meta.json", meta)

    def state(self):
        drafts, meta = self.drafts(), self.meta()
        cands = self._read("candidates.json", [])
        verify.check(drafts, cands)
        h = self.content_hash(drafts)
        appr = meta.get("approved")
        raw = collect.load_raw()
        return {
            "issue": self.date,
            "drafts": drafts,
            "candidates": cands,
            "hash": h,
            "approved": appr if appr and appr["hash"] == self.approval_hash(drafts) else None,
            "translations": {l: ("güncel" if meta["translations"].get(l) == h else
                                 "eski" if l in meta["translations"] else "yok")
                             for l in LANGS[1:]},
            "files": self.pdfs(),
            "videos": self.videos(),
            "decks": self.decks(),
            "autoscan": {**json.loads(CONFIG.read_text(encoding="utf-8")).get("autoscan", {}), **SCAN},
            "settings": settings.status(),
            "inbox_new": sum(1 for x in inbox.list_all() if x["status"] == "yeni"),
            "slides": sorted(p.name for p in (self.dir / "video" / "slides").glob("*.png")) if (self.dir / "video" / "slides").exists() else [],
            "images": sorted(p.name for p in self.img_dir.glob("*.png")) if self.img_dir.exists() else [],
            "api": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "history": meta.get("history", [])[-30:],
            "stats": {
                "raw_total": len(raw),
                "raw_week": sum(1 for it in raw.values() if self._in_week(it)),
                "last_fetch": max((it["fetched_at"] for it in raw.values()), default=None),
            },
            "sources": self.sources(raw),
        }

    @staticmethod
    def _in_week(it, days=7):
        return datetime.fromisoformat(it["published"]) >= datetime.now(timezone.utc) - timedelta(days=days)

    def sources(self, raw=None):
        raw = raw if raw is not None else collect.load_raw()
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]
        cands = self._read("candidates.json", [])
        used = {s["name"] for it in self.drafts()["items"] for s in it["sources"]}
        out = []
        for s in cfg:
            rows = [it for it in raw.values() if it["source"] == s["name"]]
            out.append({**s,
                        "total": len(rows),
                        "week": sum(1 for it in rows if self._in_week(it)),
                        "candidates": sum(1 for c in cands if c["source"] == s["name"]),
                        "in_bulletin": s["name"] in used,
                        "last_published": max((it["published"] for it in rows), default=None),
                        "site": re.sub(r"^(https?://[^/]+).*", r"\1", s["url"])})
        return out

    def _row(self, it, cands, used, trc=None):
        cid = cands.get(it["url"])
        # Türkçe başlık ve özet yalnızca Claude çevirisinden gelir (haber.py; rakamlar aslıyla denetlenmiş)
        return {"id": it["id"], "source": it["source"], "group": it.get("group", ""), "lang": it["lang"],
                "url": it["url"], "title": it["title"], "title_tr": None, "publisher": it.get("publisher"),
                "summary": it["summary"][:400], "published": it["published"],
                "video": it.get("video"), "thumb": it.get("thumb"),
                "status": "bülten" if cid in used or it["url"] in used else "aday" if cid else "", "cid": cid,
                **haber.row_extra(it, trc if trc is not None else haber.cache())}

    def feed(self):
        cands = {c["url"]: c["cid"] for c in self._read("candidates.json", [])}
        items = self.drafts()["items"]
        used = {cid for it in items for cid in it["candidate_ids"]} | {s["url"] for it in items for s in it["sources"]}
        trc = haber.cache()
        return [self._row(it, cands, used, trc)
                for it in sorted(collect.load_raw().values(), key=lambda x: x["published"], reverse=True)]

    STOP = {"ve", "ile", "için", "bir", "olan", "veya", "gibi", "the", "and", "for", "with", "of", "in",
            "и", "в", "на", "для", "с", "по"}

    def search(self, q, limit=60):
        """Türkçe sorgu -> EN/RU'ya çevrilir, tüm dillerde aranır, sonuç başlıkları Türkçeye çevrilir."""
        variants = {"tr": q.strip()}
        for lang in ("en", "ru", "uz"):
            t = translate.translate(variants["tr"], "tr", lang)
            if t:
                variants[lang] = t

        def toks(text):
            words = re.findall(r"[0-9a-zçğıöşüа-яё]+", collect.tr_lower(text))
            return [w[:5] for w in words if len(w) >= 3 and w not in self.STOP]
        tokens = {l: toks(v) for l, v in variants.items()}
        scored = []
        for it in collect.load_raw().values():
            text = collect.tr_lower(it["title"] + " " + it["summary"])
            best = 0
            for l, tk in tokens.items():
                if not tk:
                    continue
                hits = sum(1 for w in tk if w in text)
                if hits == len(tk):
                    best = max(best, hits + 1)
                elif hits >= max(1, round(len(tk) * 0.6)):  # kısmi eşleşme, daha düşük puan
                    best = max(best, hits - 0.5)
            if best:
                scored.append((best, it["published"], it))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        hits = [it for *_, it in scored[:limit]]
        for lang in {it["lang"] for it in hits} - {"tr"}:
            translate.translate_many([it["title"] for it in hits if it["lang"] == lang], lang, "tr", limit=40)
        cands = {c["url"]: c["cid"] for c in self._read("candidates.json", [])}
        used = {cid for it in self.drafts()["items"] for cid in it["candidate_ids"]}
        return {"query": variants, "provider": translate.provider(), "total": len(scored),
                "results": [self._row(it, cands, used) for it in hits]}

    def pdfs(self):
        groups = [("bülten", "issue:", self.dir.glob("*.pdf")),
                  ("yüklenen", "upload:", UPLOADS.glob("*.pdf") if UPLOADS.exists() else [])]
        for r in reports.list_reports():
            groups.append(("rapor", f"report:{r['id']}/", reports.path(r["id"]).glob("*.pdf")))
        out = []
        for group, prefix, paths in groups:
            for p in paths:
                with fitz.open(p) as d:
                    pages = d.page_count
                out.append({"name": p.name, "ref": prefix + p.name, "group": group, "pages": pages,
                            "size_kb": round(p.stat().st_size / 1024),
                            "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                            "editor": "EDITOR" in p.name})
        return sorted(out, key=lambda f: f["modified"], reverse=True)

    def pdf_page_png(self, ref, page, width):
        pdf = resolve(ref, self)
        key = hashlib.sha1(str(pdf).encode()).hexdigest()[:8]
        cache = self.dir / ".thumbs" / f"{key}-{page}-{width}-{int(pdf.stat().st_mtime)}.png"
        if not cache.exists():
            cache.parent.mkdir(exist_ok=True)
            with fitz.open(pdf) as d:
                pg = d[page]
                pix = pg.get_pixmap(matrix=fitz.Matrix(width / pg.rect.width, width / pg.rect.width))
                pix.save(cache)
        return cache.read_bytes()

    def save(self, items, who="editör"):
        for it in items:
            it.pop("warnings", None)
            it.pop("n", None)
            it["paragraphs"] = [p.strip() for p in it["paragraphs"] if p.strip()]
        drafts = {"items": items}
        from bot import media
        media.attach(drafts, self._read("candidates.json", []), self.img_dir)  # yeni eklenen haberlerin görseli
        self._write("drafts.json", drafts)
        self.log(who, f"kaydedildi ({len(items)} haber)")

    def save_image(self, data_url, name):
        self.img_dir.mkdir(exist_ok=True)
        name = re.sub(r"[^\w-]+", "-", name).strip("-")[:40] or "gorsel"
        fname = f"{name}-{datetime.now():%H%M%S}.png"
        (self.img_dir / fname).write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
        return fname

    def translate(self, lang, who):
        drafts = self.drafts()
        writer.translate(drafts, lang, self.dir)
        meta = self.meta()
        meta["translations"][lang] = self.content_hash(drafts)
        self._write("meta.json", meta)
        self.log(who, f"{lang.upper()} çevirisi güncellendi")

    def lang_drafts(self, lang):
        tr = self.drafts()
        if lang == "tr":
            return tr
        d = self._read(f"drafts.{lang}.json")
        if d:  # görseller dile bağlı değil: Türkçe taslaktan aynı sırayla al
            for a, b in zip(d["items"], tr["items"]):
                for k in ("image", "image_caption", "photo", "videos"):
                    a[k] = b.get(k)
        return d

    def approve(self, who):
        st = self.state()
        blockers = [f"{i}. haber: {w}" for i, it in enumerate(st["drafts"]["items"], 1)
                    for w in it.get("warnings", [])]
        if blockers:
            raise ValueError("Rakam uyarıları çözülmeden onaylanamaz:\n" + "\n".join(blockers))
        files = []
        for lang in LANGS:
            if lang != "tr" and st["translations"][lang] != "güncel":
                continue  # eski çeviri yayınlanmaz
            files.append(render.render(self.lang_drafts(lang), self.date, lang, self.dir).name)
        meta = self.meta()
        meta["approved"] = {"hash": self.approval_hash(self.drafts()), "by": who, "files": files,
                            "at": datetime.now().isoformat(timespec="seconds")}
        self._write("meta.json", meta)
        self.log(who, "onaylandı: " + ", ".join(files))
        return files

    def videos(self):
        vdir = self.dir / "video"
        return [{"name": p.name, "ref": "video:" + p.name, "size_kb": round(p.stat().st_size / 1024),
                 "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
                for p in sorted(vdir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)] if vdir.exists() else []

    def decks(self):
        ddir = self.dir / "sunum"
        return [{"name": p.name, "ref": "deck:" + p.name, "size_kb": round(p.stat().st_size / 1024),
                 "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
                for p in sorted(ddir.glob("*.p*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if p.suffix in (".pdf", ".pptx")] if ddir.exists() else []

    def start_deck(self, lang, who):
        if DECK_JOB.get("state") == "çalışıyor":
            raise ValueError("Bir sunum zaten hazırlanıyor.")
        drafts = self.lang_drafts(lang)
        if not drafts:
            raise ValueError(f"{lang.upper()} çevirisi yok; önce çeviri yapın.")
        DECK_JOB.clear()
        DECK_JOB.update(state="çalışıyor", step=0, total=1, message="Başlıyor", lang=lang)

        def job():
            try:
                pdf, pptx = video.build_deck(drafts, self.date, lang, self.dir,
                                             progress=lambda i, n, m: DECK_JOB.update(step=i, total=n, message=m))
                DECK_JOB.update(state="bitti", message="Sunum hazır", files=[pdf.name, pptx.name])
                self.log(who, f"sunum bülteni üretildi: {pdf.name}, {pptx.name}")
            except Exception as e:
                traceback.print_exc()
                DECK_JOB.update(state="hata", message=f"{type(e).__name__}: {e}")
        threading.Thread(target=job, daemon=True).start()
        return dict(DECK_JOB)

    def start_video(self, lang, voice, seconds, who, voice_id=None):
        if VIDEO_JOB.get("state") == "çalışıyor":
            raise ValueError("Bir video zaten hazırlanıyor.")
        drafts = self.lang_drafts(lang)
        if not drafts:
            raise ValueError(f"{lang.upper()} çevirisi yok; önce çeviri yapın.")
        VIDEO_JOB.clear()
        VIDEO_JOB.update(state="çalışıyor", step=0, total=1, message="Başlıyor", lang=lang)

        def progress(i, n, msg):
            VIDEO_JOB.update(step=i, total=n, message=msg)

        def job():
            try:
                out = video.build(drafts, self.date, lang, self.dir, voice=voice, seconds=seconds, progress=progress,
                                  voice_id=voice_id)
                VIDEO_JOB.update(state="bitti", message="Video hazır", file=out.name)
                self.log(who, f"video bülten üretildi: {out.name}")
            except Exception as e:
                traceback.print_exc()
                VIDEO_JOB.update(state="hata", message=f"{type(e).__name__}: {e}")
        threading.Thread(target=job, daemon=True).start()
        return dict(VIDEO_JOB)

    # ---------------------------------------------------------------- temsilcilikler
    def institutions(self, days=365):
        insts = json.loads(INST_CFG.read_text(encoding="utf-8"))
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]
        raw = collect.load_raw()
        since = datetime.now(timezone.utc) - timedelta(days=days)
        msgs = json.loads(INST_MSG.read_text(encoding="utf-8")) if INST_MSG.exists() else []
        feed = []
        for it in raw.values():
            if it.get("institution") and datetime.fromisoformat(it["published"]) >= since:
                tt = it["title"] if it["lang"] == "tr" else (translate.cached(it["title"], it["lang"], "tr") or it["title"])
                feed.append({"id": it["id"], "inst": it["institution"], "source": it["source"], "publisher": it.get("publisher"),
                             "title": tt, "summary": (it.get("text") or it["summary"])[:600], "url": it["url"],
                             "date": it["published"], "thumb": it.get("thumb"), "manual": False})
        for m in msgs:
            feed.append({**m, "inst": m["institution"], "source": "Elle eklendi", "date": m["date"] + "T12:00:00+05:00",
                         "summary": m.get("text", ""), "url": m.get("link"), "manual": True})
        feed.sort(key=lambda x: x["date"], reverse=True)
        out = []
        for ins in insts:
            srcs = [{"name": x["name"], "kind": x.get("kind", "rss"), "url": x.get("url"), "enabled": x.get("enabled", True)}
                    for x in cfg if x.get("institution") == ins["key"]]
            mine = [f for f in feed if f["inst"] == ins["key"]]
            recent = [f for f in mine if f["date"] >= (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()]
            out.append({**ins, "sources": srcs, "total": len(mine), "month": len(recent),
                        "last": mine[0]["date"] if mine else None})
        return {"institutions": out, "feed": feed[:300]}

    def inst_message(self, data, who):
        msgs = json.loads(INST_MSG.read_text(encoding="utf-8")) if INST_MSG.exists() else []
        if data.get("op") == "delete":
            msgs = [m for m in msgs if m["id"] != data["id"]]
        else:
            if not (data.get("title") or "").strip():
                raise ValueError("Başlık gerekli.")
            m = {"id": "m" + datetime.now().strftime("%Y%m%d%H%M%S"), "institution": data["institution"],
                 "title": data["title"].strip(), "date": data.get("date") or date.today().isoformat(),
                 "text": (data.get("text") or "").strip(), "link": (data.get("link") or "").strip() or None,
                 "attachment": data.get("attachment"), "who": who}
            msgs.append(m)
        INST_MSG.parent.mkdir(parents=True, exist_ok=True)
        INST_MSG.write_text(json.dumps(msgs, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log(who, "temsilcilik mesajı " + ("silindi" if data.get("op") == "delete" else "eklendi"))
        return self.institutions()

    def _inst_item(self, iid):
        return next((f for f in self.institutions(days=3650)["feed"] if f["id"] == iid), None)

    def inst_to_bulletin(self, iid, who):
        f = self._inst_item(iid)
        if not f:
            raise ValueError("Kayıt bulunamadı.")
        ins = {i["key"]: i["name"] for i in json.loads(INST_CFG.read_text(encoding="utf-8"))}
        drafts = self.drafts()
        text = re.sub(r"\s+", " ", f["summary"] or "").strip()
        drafts["items"].append({"headline": f["title"].rstrip(".") + ".", "paragraphs": [text] if text else [""],
                                "category": "diğer", "candidate_ids": [], "source_text": f["title"] + " " + (f["summary"] or ""),
                                "sources": [{"name": f.get("publisher") or ins.get(f["inst"], f["source"]), "url": f.get("url") or ""}]})
        self._write("drafts.json", drafts)
        self.log(who, f"temsilcilik haberi bültene eklendi: {f['title'][:60]}")
        return len(drafts["items"])

    def inst_to_ann(self, iid, who):
        f = self._inst_item(iid)
        if not f:
            raise ValueError("Kayıt bulunamadı.")
        a = announce.new("duyuru", "tr")
        vals = {"title": f["title"][:140], "text": (f["summary"] or "")[:700], "link": f.get("url") or "",
                "tag": next((i["short"] for i in json.loads(INST_CFG.read_text(encoding="utf-8")) if i["key"] == f["inst"]), "")}
        a = announce.update(a["id"], vals)
        if f.get("thumb"):
            try:
                import requests as rq
                r = rq.get(f["thumb"], headers=collect.UA, timeout=20)
                if r.ok and r.headers.get("Content-Type", "").startswith("image/"):
                    a = announce.set_photo(a["id"], base64.b64encode(r.content).decode(), "foto.jpg")
            except Exception:
                pass
        self.log(who, f"temsilcilik haberi duyuruya dönüştürüldü: {f['title'][:60]}")
        return a

    # ---------------------------------------------------------------- gelen kutusu
    def _inst_name(self, key):
        return next((i["name"] for i in json.loads(INST_CFG.read_text(encoding="utf-8")) if i["key"] == key), key or "Birim")

    def _first_image(self, sub):
        return next((f for f in sub["files"] if Path(f).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")), None)

    def sub_to_bulletin(self, sid, who):
        sub = inbox.load(sid)
        paras = [p.strip() for p in re.split(r"\n\s*\n", sub["text"]) if p.strip()] or [""]
        item = {"headline": sub["title"].rstrip(".") + ".", "paragraphs": paras, "category": "diğer", "candidate_ids": [],
                "source_text": sub["title"] + " " + sub["text"],
                "sources": [{"name": self._inst_name(sub["institution"]), "url": sub.get("link") or ""}]}
        img = self._first_image(sub)
        if img:
            self.img_dir.mkdir(exist_ok=True)
            fname = f"gelen-{sid}{Path(img).suffix.lower()}"
            shutil.copy(inbox._dir(sid) / img, self.img_dir / fname)
            item["photo"] = {"file": fname, "credit": self._inst_name(sub["institution"]), "url": "", "show": True}
        drafts = self.drafts()
        drafts["items"].append(item)
        self._write("drafts.json", drafts)
        inbox.set_status(sid, "yayina_alindi", None, who)
        inbox.add_history(sid, who, f"bültene {len(drafts['items'])}. haber olarak eklendi")
        self.log(who, f"gelen bilgi bültene eklendi: {sub['title'][:60]}")
        return len(drafts["items"])

    def sub_to_ann(self, sid, who):
        sub = inbox.load(sid)
        kind = {"etkinlik": "etkinlik", "duyuru": "duyuru", "haber": "haber"}.get(sub["type"], "duyuru")
        a = announce.new(kind, sub.get("lang") or "tr")
        a = announce.update(a["id"], {k: sub.get(k) or "" for k in ("title", "text", "date", "date_end", "time", "place",
                                                                     "deadline", "link", "contact")}
                            | {"tag": self._inst_name(sub["institution"]).split()[0]})
        img = self._first_image(sub)
        if img:
            a = announce.set_photo(a["id"], from_path=inbox._dir(sid) / img)
        inbox.set_status(sid, "inceleniyor", None, who)
        inbox.add_history(sid, who, "duyuru tasarımı hazırlanıyor")
        self.log(who, f"gelen bilgi duyuruya dönüştürüldü: {sub['title'][:60]}")
        return a

    # ---------------------------------------------------------------- web (Vercel önizleme)
    def web_info(self):
        out = demo.OUT
        files = [p for p in out.rglob("*") if p.is_file()] if out.exists() else []
        built = datetime.fromtimestamp((out / "index.html").stat().st_mtime).isoformat(timespec="seconds") if (out / "index.html").exists() else None
        return {"built": built, "files": len(files), "mb": round(sum(p.stat().st_size for p in files) / 1048576, 1),
                "job": dict(WEB_JOB), "settings": settings.status()}

    def web_build(self, who):
        r = demo.build(self, lambda ref: resolve(ref, self))
        self.log(who, f"web önizlemesi hazırlandı ({r['files']} dosya, {r['mb']} MB)")
        return self.web_info()

    def web_deploy(self, project, who):
        if WEB_JOB.get("state") == "çalışıyor":
            raise ValueError("Yayın zaten sürüyor.")
        token = os.environ.get("VERCEL_TOKEN")
        if not token:
            raise ValueError("Önce Vercel jetonunu girin.")
        project = re.sub(r"[^a-z0-9-]", "-", (project or "taskentticaret").lower()).strip("-")[:52] or "taskentticaret"
        settings.update({"vercel_project": project})
        WEB_JOB.clear()
        WEB_JOB.update(state="çalışıyor", step=0, total=1, message="Başlıyor")

        def job():
            try:
                if not (demo.OUT / "index.html").exists():
                    WEB_JOB.update(message="Önizleme hazırlanıyor")
                    demo.build(self, lambda ref: resolve(ref, self))
                r = vercel.deploy(token, project, demo.OUT, lambda i, n, m: WEB_JOB.update(step=i, total=n, message=m))
                settings.update({"vercel_url": r["url"]})
                WEB_JOB.update(state="bitti", message="Yayında", **r)
                self.log(who, f"web önizlemesi Vercel'de yayınlandı: {r['url']}")
            except Exception as e:
                traceback.print_exc()
                WEB_JOB.update(state="hata", message=str(e))
        threading.Thread(target=job, daemon=True).start()
        return self.web_info()

    def scan(self, who):
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        before = len(collect.load_raw())
        after = len(collect.collect(cfg["sources"]))
        self.log(who, f"kaynaklar tarandı: {after - before} yeni haber")
        if after > before:  # yeni haberlerin Türkçe başlık ve özetleri arka planda hazırlanır
            threading.Thread(target=lambda: _safe(haber.translate_new), daemon=True).start()
        return after - before


def make_handler(issue):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        # ------------------------------------------------ kimlik ve yetki
        def _cookie(self, name):
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == name:
                    return v
            return None

        def _user(self):
            u = auth.user_for(self._cookie("sid"))
            return u if auth.PUBLIC else (u or auth.OPEN_ADMIN)  # yerelde şifre istenmez; sunucuda herkes girer

        def _ip(self):
            if auth.PUBLIC:  # Caddy arkasında: gerçek istemci adresi X-Forwarded-For'un son halkası
                fwd = (self.headers.get("X-Forwarded-For") or "").split(",")[-1].strip()
                if fwd:
                    return fwd
            return self.client_address[0]

        def _redirect(self, to):
            self.send_response(302)
            self.send_header("Location", to)
            self.send_header("Content-Length", "0")
            self.end_headers()

        BIRIM_GET = ("/gonder", "/api/me", "/api/sub/mine", "/file", "/static/gonder.html", "/static/i18n-uz.js")
        BIRIM_POST = ("/api/sub/new", "/api/logout")
        # editör: haber seçer, bülten/rapor hazırlar ve üretir; anahtar, kullanıcı ve tarama ayarları yöneticidedir
        ADMIN_POST = ("/api/settings", "/api/users", "/api/sources/update")

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/giris", "/static/giris.html"):
                return self._send(200, (STATIC / "giris.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/setup-status":
                return self._send(200, {"needed": auth.PUBLIC and not auth.has_admin()})
            user = self._user()
            if not user:
                return self._redirect("/giris") if not path.startswith("/api/") else self._send(401, {"error": "Giriş gerekli."})
            self.user = user
            if path == "/api/me":
                return self._send(200, {**user, "inst_name": issue._inst_name(user.get("institution"))})
            if user["role"] == "birim":
                if path == "/":
                    return self._redirect("/gonder")
                if path not in self.BIRIM_GET:
                    return self._send(403, {"error": "Bu sayfaya erişim yetkiniz yok."})
                if path == "/file":  # birim yalnızca kendi eklerini açabilir
                    ref = parse_qs(urlparse(self.path).query).get("ref", [""])[0]
                    if not ref.startswith("sub:") or inbox.load(ref[4:].split("/")[0])["sender"] != user["username"]:
                        return self._send(403, {"error": "Yetkisiz."})
            if path == "/gonder":
                return self._send(200, (STATIC / "gonder.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/sub/mine":
                return self._send(200, inbox.list_all(user))
            if path == "/api/sub/all":
                return self._send(200, {"items": inbox.list_all(), "statuses": inbox.STATUSES, "types": inbox.TYPES})
            if path == "/api/users":
                if user["role"] != "yonetici":
                    return self._send(403, {"error": "Kullanıcıları yalnızca yönetici görür."})
                return self._send(200, {"public": auth.PUBLIC, "users": auth.list_users(), "network": auth.network(), "ip": auth.lan_ip(),
                                        "port": self.server.server_address[1], "bound": self.server.server_address[0]})
            return self._get()

        def do_POST(self):
            path = urlparse(self.path).path
            n = int(self.headers.get("Content-Length") or 0)
            if n > 40 * 1024 * 1024:
                return self._send(413, {"error": "İstek çok büyük."})
            body = self.rfile.read(n) or b"{}"
            try:
                data = json.loads(body)
            except ValueError:
                return self._send(400, {"error": "Geçersiz istek."})
            if path in ("/api/login", "/api/setup"):
                try:
                    if path == "/api/setup":
                        token = auth.first_setup(data.get("code"), data.get("username", ""), data.get("password", ""),
                                                 data.get("name", ""), self._ip())
                        issue.log(data.get("name") or data.get("username"), "ilk kurulum: yönetici hesabı oluşturuldu")
                    else:
                        token = auth.login(data.get("username"), data.get("password"), self._ip())
                        if auth.user_for(token)["role"] == "birim":  # Gelen Kutusu / Bilgi Gönder kaldırıldı (22.10.2026)
                            raise PermissionError("Birim girişi kapatıldı; panel yalnızca Ticaret Müşavirliği yöneticileri içindir.")
                except (PermissionError, ValueError) as e:
                    return self._send(401, {"error": str(e)})
                u = auth.user_for(token)
                self.send_response(200)
                self.send_header("Set-Cookie", f"sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={auth.SESSION_HOURS * 3600}"
                                 + ("; Secure" if auth.PUBLIC else ""))
                body = json.dumps({"role": u["role"], "go": "/gonder" if u["role"] == "birim" else "/"}).encode()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            user = self._user()
            if not user:
                return self._send(401, {"error": "Giriş gerekli."})
            self.user = user
            if user["role"] == "birim" and path not in self.BIRIM_POST:
                return self._send(403, {"error": "Bu işlem için yetkiniz yok."})
            if user["role"] != "yonetici" and (path in self.ADMIN_POST or path.startswith(("/api/telegram", "/api/web"))):
                return self._send(403, {"error": "Bu ayarı yalnızca yönetici değiştirebilir."})
            if user is not auth.OPEN_ADMIN:
                data["who"] = user.get("name") or user["username"]  # birim hesabında adı oturum belirler
            try:
                if path == "/api/logout":
                    auth.logout(self._cookie("sid"))
                    return self._send(200, {"ok": True})
                if path == "/api/sub/new":
                    s = inbox.create(user, data)
                    issue.log(user.get("name"), f"yeni bilgi gönderdi: {s['title'][:60]}")
                    return self._send(200, s)
                if path == "/api/sub/status":
                    return self._send(200, inbox.set_status(data["id"], data["status"], data.get("note"), data["who"] if "who" in data else "yönetici"))
                if path == "/api/sub/to-bulletin":
                    with LOCK:
                        n = issue.sub_to_bulletin(data["id"], data.get("who", "yönetici"))
                    return self._send(200, {"n": n, "state": issue.state()})
                if path == "/api/sub/to-ann":
                    return self._send(200, issue.sub_to_ann(data["id"], data.get("who", "yönetici")))
                if path == "/api/users":
                    op = data.get("op")
                    if op == "add":
                        auth.create_user(data["username"], data["password"], data.get("role", "editor"), data.get("institution") or "ticaret", data.get("name", ""))
                    elif op == "password":
                        auth.set_password(data["username"], data["password"])
                    elif op == "delete":
                        auth.guard_delete(data["username"], user["username"])
                        auth.delete_user(data["username"])
                    elif op == "network":
                        auth.set_network(data.get("lan"))
                    issue.log(data.get("who", "yönetici"), f"kullanıcı/ağ ayarı: {op}")
                    return self._send(200, {"users": auth.list_users(), "network": auth.network(), "ip": auth.lan_ip(),
                                            "port": self.server.server_address[1], "bound": self.server.server_address[0]})
            except (ValueError, KeyError, FileNotFoundError) as e:
                return self._send(400, {"error": str(e)})
            self._body = data
            return self._post()

        def _get(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            arg = lambda k, d=None: q.get(k, [d])[0]
            try:
                if url.path == "/":
                    return self._send(200, (STATIC / "panel.html").read_bytes(),
                                      "text/html; charset=utf-8")
                if url.path.startswith("/static/"):
                    sp = (STATIC / unquote(url.path[8:])).resolve()
                    if STATIC.resolve() in sp.parents and sp.is_file():  # yalnızca static/ içi
                        ctype = mimetypes.guess_type(sp.name)[0] or "application/octet-stream"
                        return self._send(200, sp.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype.endswith("javascript") else ""))
                if url.path == "/api/state":
                    return self._send(200, issue.state())
                if url.path == "/api/feed":
                    return self._send(200, issue.feed())
                if url.path == "/api/search":
                    return self._send(200, issue.search(arg("q", "")))
                if url.path == "/api/rates":
                    return self._send(200, {"today": charts.today_rates(),
                                            "USD": charts.history("USD"),
                                            "TRY": charts.history("TRY")})
                if url.path == "/preview":
                    lang = arg("lang", "tr")
                    d = issue.lang_drafts(lang)
                    if d is None:
                        return self._send(404, f"{lang.upper()} çevirisi henüz yok.",
                                          "text/plain; charset=utf-8")
                    if lang == "tr":
                        verify.check(d, issue._read("candidates.json", []))
                    html = render.build_html(d, issue.date, lang, review=lang == "tr")
                    return self._send(200, html, "text/html; charset=utf-8")
                if url.path == "/pdfpage":
                    png = issue.pdf_page_png(arg("ref"), int(arg("page", 0)), min(int(arg("w", 600)), 1600))
                    return self._send(200, png, "image/png")
                if url.path == "/file":
                    p = resolve(arg("ref"), issue)
                    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                    rng = self.headers.get("Range")
                    if rng and rng.startswith("bytes="):
                        size = p.stat().st_size
                        a, _, b = rng[6:].partition("-")
                        a = int(a or 0)
                        b = min(int(b) if b else size - 1, a + 4 * 1024 * 1024, size - 1)
                        with p.open("rb") as f:
                            f.seek(a)
                            chunk = f.read(b - a + 1)
                        self.send_response(206)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
                        self.send_header("Content-Length", str(len(chunk)))
                        self.end_headers()
                        self.wfile.write(chunk)
                        return
                    return self._send(200, p.read_bytes(), ctype)
                if url.path == "/api/video/status":
                    return self._send(200, dict(VIDEO_JOB))
                if url.path == "/api/deck/status":
                    return self._send(200, dict(DECK_JOB))
                if url.path == "/api/web":
                    return self._send(200, issue.web_info())
                if url.path.startswith("/onizleme/") or url.path == "/onizleme":
                    rel = unquote(url.path[len("/onizleme/"):]) or "index.html"
                    fp = (demo.OUT / rel).resolve()
                    if demo.OUT.resolve() in fp.parents and fp.is_file():
                        ct = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"
                        return self._send(200, fp.read_bytes(), ct + ("; charset=utf-8" if ct.startswith("text") or "json" in ct or "javascript" in ct else ""))
                    if url.path == "/onizleme":
                        return self._redirect("/onizleme/")
                if url.path == "/api/inst":
                    return self._send(200, issue.institutions())
                if url.path == "/api/ann/special":
                    return self._send(200, announce.special_days(arg("lang", "tr")))
                if url.path == "/api/ann/list":
                    return self._send(200, announce.list_all())
                if url.path == "/ann-preview":
                    a = announce.load(arg("id"))
                    purl = f"/file?ref=ann:{a['id']}/{a['photo']}&t={a.get('updated', '')}" if a.get("photo") else None
                    return self._send(200, announce.html(a, arg("fmt", "kare"), photo_url=purl), "text/html; charset=utf-8")
                if url.path == "/api/voices":
                    return self._send(200, tts.voices(arg("lang", "tr")))
                if url.path == "/api/settings":
                    return self._send(200, settings.status())
                if url.path == "/api/telegram":
                    return self._send(200, telegram.status())
                if url.path == "/api/report-types":
                    return self._send(200, reports.types())
                if url.path == "/api/reports":
                    return self._send(200, reports.list_reports())
                if url.path == "/api/report":
                    return self._send(200, reports.load(arg("id")))
                if url.path == "/report-preview":
                    return self._send(200, reports.build_html(reports.load(arg("id"))), "text/html; charset=utf-8")
                if url.path.startswith("/img/"):
                    p = issue.img_dir / safe_name(url.path[5:])
                    if p.exists():
                        return self._send(200, p.read_bytes(), "image/png")
                if url.path.startswith("/files/"):
                    p = issue.dir / safe_name(url.path[7:])
                    if p.suffix in (".pdf", ".html") and p.exists():
                        return self._send(200, p.read_bytes(),
                                          mimetypes.guess_type(p.name)[0] or "application/pdf")
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
            return self._send(404, {"error": "bulunamadı"})

        def _post(self):
            data = self._body
            who = (data.get("who") or "editör")[:40]
            try:
                if self.path.startswith("/api/telegram"):
                    return self._send(200, self.telegram(data, who))
                if self.path == "/api/web/build":
                    return self._send(200, issue.web_build(who))
                if self.path == "/api/web/deploy":
                    return self._send(200, issue.web_deploy(data.get("project"), who))
                if self.path == "/api/inst/message":
                    return self._send(200, issue.inst_message(data, who))
                if self.path == "/api/inst/to-bulletin":
                    with LOCK:
                        n = issue.inst_to_bulletin(data["id"], who)
                    return self._send(200, {"n": n, "state": issue.state()})
                if self.path == "/api/inst/to-ann":
                    return self._send(200, issue.inst_to_ann(data["id"], who))
                if self.path.startswith("/api/ann/"):
                    with REPORT_LOCK:
                        return self._send(200, self.ann(data, who))
                if self.path.startswith("/api/report"):
                    with REPORT_LOCK:
                        return self._send(200, self.report(data, who))
                if self.path == "/api/upload":
                    UPLOADS.mkdir(parents=True, exist_ok=True)
                    name = safe_name(data["name"])
                    if Path(name).suffix.lower() not in (".pdf", ".png", ".jpg", ".jpeg", ".mp4"):
                        raise ValueError("Yalnızca PDF, görsel ve MP4 yüklenebilir.")
                    (UPLOADS / name).write_bytes(base64.b64decode(data["data"].split(",", 1)[-1]))
                    issue.log(who, f"dosya yüklendi: {name}")
                    return self._send(200, {"ref": "upload:" + name, "state": issue.state()})
                if self.path == "/api/feed/translate":
                    return self._send(200, haber.translate_ids(list(data.get("ids", []))))
                if self.path == "/api/feed/to-items":
                    with LOCK:
                        items = haber.to_items(issue, list(data.get("ids", [])))
                    issue.log(who, f"haber akışından bültene eklendi ({len(items)} haber)")
                    return self._send(200, {"items": items})
                with LOCK:
                    if self.path == "/api/save":
                        issue.save(data["items"], who)
                    elif self.path == "/api/editor-pdf":
                        render.render(issue.drafts(), issue.date, "tr", issue.dir, review=True)
                        issue.log(who, "editör PDF'i üretildi")
                    elif self.path == "/api/video/start":
                        return self._send(200, issue.start_video(data.get("lang", "tr"), bool(data.get("voice", True)),
                                                                 float(data.get("seconds", 7)), who, data.get("voice_id")))
                    elif self.path == "/api/deck/start":
                        return self._send(200, issue.start_deck(data.get("lang", "tr"), who))
                    elif self.path == "/api/tts/sample":
                        lang = data.get("lang", "tr")
                        text = {"tr": "Merhaba, bu hafta Özbekistan ekonomisinden öne çıkan haberleri sizin için derledik.",
                                "uz": "Assalomu alaykum, ushbu haftaning asosiy iqtisodiy yangiliklarini taqdim etamiz.",
                                "en": "Hello, here are this week's top economic headlines from Uzbekistan.",
                                "ru": "Здравствуйте, представляем главные экономические новости недели."}[lang]
                        out = Path("data/cache") / f"ornek-{re.sub(r'[^a-zA-Z0-9-]', '-', data['voice'])}.wav"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        tts.synthesize(text, data["voice"], out)
                        return self._send(200, {"ref": "sample:" + out.name})
                    elif self.path == "/api/settings":
                        st = settings.update(data)
                        issue.log(who, "ayarlar güncellendi")
                        return self._send(200, st)
                    elif self.path == "/api/sources/update":
                        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
                        if "autoscan" in data:
                            cfg["autoscan"] = {"enabled": bool(data["autoscan"].get("enabled")),
                                               "minutes": max(15, int(data["autoscan"].get("minutes", 60)))}
                        if "toggle" in data:
                            for src in cfg["sources"]:
                                if src["name"] == data["toggle"]:
                                    src["enabled"] = not (src.get("enabled", True))
                        if "remove" in data:
                            cfg["sources"] = [x for x in cfg["sources"] if x["name"] != data["remove"]]
                        if "add" in data:
                            a = data["add"]
                            name = (a.get("name") or "").strip()
                            if not name or any(x["name"] == name for x in cfg["sources"]):
                                raise ValueError("Kaynak adı boş ya da zaten var.")
                            if a.get("kind") == "telegram":
                                h = re.sub(r"^(https?://)?t\.me/(s/)?|^@", "", a["url"].strip()).strip("/")
                                if not collect.telegram_posts(h):
                                    raise ValueError("Bu Telegram kanalının herkese açık gönderileri okunamadı.")
                                src = {"name": name, "group": "Telegram", "lang": a.get("lang", "uz"), "kind": "telegram",
                                       "handle": h, "url": f"https://t.me/s/{h}"}
                            else:
                                import feedparser, requests as rq
                                f = feedparser.parse(rq.get(a["url"], headers=collect.UA, timeout=20).content)
                                if not f.entries:
                                    raise ValueError("Bu adreste RSS akışı bulunamadı.")
                                src = {"name": name, "group": a.get("group") or "Diğer", "lang": a.get("lang", "tr"), "url": a["url"]}
                            if a.get("institution"):
                                src["institution"] = a["institution"]
                            if a.get("only_uz"):
                                src["filter"] = ["özbek", "taşkent", "semerkant", "buhara", "fergana", "mirziyoyev", "uzbek"]
                            cfg["sources"].append(src)
                        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                        issue.log(who, "kaynak ayarları değiştirildi")
                    elif self.path == "/api/scan":
                        added = issue.scan(who)
                        return self._send(200, {"added": added, "state": issue.state()})
                    elif self.path == "/api/image":
                        fname = issue.save_image(data["data"], data.get("name", "gorsel"))
                        issue.log(who, f"görsel kaydedildi: {fname}")
                        return self._send(200, {"file": fname, "state": issue.state()})
                    elif self.path == "/api/translate":
                        if not os.environ.get("ANTHROPIC_API_KEY"):
                            raise ValueError("Çeviri için ANTHROPIC_API_KEY tanımlı olmalı.")
                        issue.translate(data["lang"], who)
                    elif self.path == "/api/write-item":
                        if not os.environ.get("ANTHROPIC_API_KEY"):
                            raise ValueError("Otomatik yazım için ANTHROPIC_API_KEY tanımlı olmalı.")
                        cand = next(c for c in issue._read("candidates.json")
                                    if c["cid"] == data["cid"])
                        return self._send(200, {"item": writer.write_single(cand)})
                    elif self.path == "/api/approve":
                        issue.approve(who)
                    else:
                        return self._send(404, {"error": "bulunamadı"})
                    return self._send(200, issue.state())
            except (ValueError, KeyError) as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})

        def telegram(self, data, who):
            if self.path == "/api/telegram/connect":
                return telegram.connect(data["token"])
            if self.path == "/api/telegram/disconnect":
                return telegram.disconnect()
            if self.path == "/api/telegram/channel":
                return telegram.add_channel(data["chat_id"])
            if self.path == "/api/telegram/channel-update":
                return telegram.update_channel(data["id"], data.get("enabled"), data.get("remove", False))
            if self.path == "/api/telegram/send":
                results = telegram.publish(resolve(data["ref"], issue), data.get("caption", ""),
                                           data.get("channels"), who)
                ok = sum(r["ok"] for r in results)
                issue.log(who, f"Telegram: {data['ref'].split(':', 1)[-1]} -> {ok}/{len(results)} kanal")
                return {"results": results, "status": telegram.status()}
            raise ValueError("bilinmeyen işlem")

        def ann(self, data, who):
            op = self.path.rsplit("/", 1)[-1]
            if op == "new":
                a = announce.new(data.get("kind", "etkinlik"), data.get("lang", "tr"))
                issue.log(who, f"yeni {data.get('kind', 'etkinlik')} oluşturuldu")
                return a
            if op == "save":
                return announce.update(data["id"], data)
            if op == "delete":
                announce.delete(data["id"])
                issue.log(who, "duyuru silindi")
                return {"ok": True}
            if op == "photo":
                src = resolve(data["from_ref"], issue) if data.get("from_ref") else None
                return announce.set_photo(data["id"], data.get("data"), data.get("name"), src)
            if op == "produce":
                outs = [announce.produce(data["id"], f).name for f in data.get("fmts", ["kare"])]
                issue.log(who, "duyuru tasarımı üretildi: " + ", ".join(outs))
                return {"files": announce.outputs(data["id"])}
            if op == "special":
                a = announce.from_special(data["key"], data.get("lang", "tr"))
                issue.log(who, f"özel gün kartı oluşturuldu: {a['title'][:50]}")
                return a
            if op == "translate":
                b = announce.translate_copy(data["id"], data["lang"])
                issue.log(who, f"duyuru {data['lang'].upper()} diline çevrildi")
                return b
            raise ValueError("bilinmeyen işlem")

        def report(self, data, who):
            if self.path == "/api/report/create":
                return reports.create(data["type"], data.get("params", {}), who)
            rep = reports.load(data["id"])
            if self.path == "/api/report/save":
                edits = {s["id"]: s for s in data["sections"]}
                for s in rep["sections"]:
                    if s["id"] in edits:
                        for k in ("title", "text", "status"):
                            if k in edits[s["id"]]:
                                s[k] = edits[s["id"]][k]
                reports.log(rep, who, f"kaydedildi ({len(edits)} bölüm)")
                reports.save(rep)
            elif self.path == "/api/report/refresh":
                errs = reports.refresh(rep, data.get("sid"), who)
                if errs and data.get("sid"):
                    raise ValueError("Veri alınamadı: " + "; ".join(errs))
            elif self.path == "/api/report/import":
                n, m = reports.import_pdf(rep, base64.b64decode(data["data"].split(",", 1)[-1]), who)
            elif self.path == "/api/report/render":
                reports.render(rep, who)
            elif self.path == "/api/report/ai":
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    raise ValueError("Claude ile güncelleme için ANTHROPIC_API_KEY tanımlı olmalı.")
                sec = next(s for s in rep["sections"] if s["id"] == data["sid"])
                report_ai.update_section(rep, sec)
                reports.log(rep, who, f"{sec['id']} Claude ile güncellendi")
                reports.save(rep)
            else:
                raise ValueError("bilinmeyen işlem")
            return reports.load(rep["id"])

    return Handler


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        traceback.print_exc()


def refresh_reports(who="otomatik veri taraması"):
    """Raporlardaki veri tablolarını resmî kaynaklardan (UN Comtrade, Dünya Bankası, SIAT) yeniler."""
    n = 0
    for r in reports.list_reports():
        try:
            reports.refresh(reports.load(r["id"]), None, who)
            n += 1
        except Exception:
            traceback.print_exc()
    return n


def autoscan_loop(issue):
    """Kaynakları ayarlanan aralıkla (varsayılan saatte bir) otomatik tarar."""
    import time
    while True:
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8")).get("autoscan", {})
            minutes = max(15, int(cfg.get("minutes", 60)))
            now = datetime.now()
            if cfg.get("enabled", True) and (SCAN["next"] is None or now >= datetime.fromisoformat(SCAN["next"])):
                if SCAN["last"] is not None:  # ilk açılışta hemen tarama; sonra aralıkla
                    SCAN["running"] = True
                    SCAN["added"] = issue.scan("otomatik tarama")
                SCAN["running"] = False
                SCAN["last"] = now.isoformat(timespec="seconds")
                SCAN["next"] = (now + timedelta(minutes=minutes)).isoformat(timespec="seconds")
            # rapor veri tabloları günde bir kez kendiliğinden yenilenir
            if cfg.get("enabled", True) and (SCAN.get("reports") is None or now - datetime.fromisoformat(SCAN["reports"]) >= timedelta(hours=24)):
                SCAN["reports"] = now.isoformat(timespec="seconds")
                threading.Thread(target=refresh_reports, daemon=True).start()
            elif not cfg.get("enabled", True):
                SCAN["next"] = None
        except Exception:
            SCAN["running"] = False
            traceback.print_exc()
        time.sleep(30)


def serve(port=8765):
    settings.apply()
    if auth.PUBLIC:
        code = auth.setup_code()
        if code:
            print(f"İLK KURULUM KODU: {code}  (giriş ekranında yönetici hesabı oluşturmak için)", flush=True)
    else:
        auth.SETUP_CODE.unlink(missing_ok=True)
    issue = Issue(latest_issue_dir())
    threading.Thread(target=autoscan_loop, args=(issue,), daemon=True).start()
    print(f"Editör paneli: http://127.0.0.1:{port}  (sayı {issue.date})")
    host = os.environ.get("PANEL_HOST") or ("0.0.0.0" if auth.network().get("lan") else "127.0.0.1")
    if host == "0.0.0.0":
        print(f"Ağ erişimi açık: http://{auth.lan_ip()}:{port}  (ağdan girişte kullanıcı adı/şifre istenir)")
    ThreadingHTTPServer((host, port), make_handler(issue)).serve_forever()
