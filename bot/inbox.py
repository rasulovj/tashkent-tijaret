"""Birimlerden gelen bilgiler (gelen kutusu).

Her gönderi data/gelen/<id>/gonderi.json + ekleri. Durumlar:
yeni -> inceleniyor -> yayina_alindi | reddedildi
"""
import base64
import json
import re
from datetime import datetime
from pathlib import Path

STORE = Path("data/gelen")
STATUSES = {"yeni": "Yeni", "inceleniyor": "İnceleniyor", "yayina_alindi": "Yayına alındı", "reddedildi": "Reddedildi"}
TYPES = {"haber": "Haber", "duyuru": "Duyuru", "etkinlik": "Etkinlik", "mesaj": "Mesaj / bilgi"}
MAX_BYTES = 25 * 1024 * 1024
ALLOWED = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx", ".xlsx", ".mp4")


def _dir(sid):
    return STORE / Path(sid).name


def _save(s):
    d = _dir(s["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "gonderi.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s


def load(sid):
    return json.loads((_dir(sid) / "gonderi.json").read_text(encoding="utf-8"))


def create(user, data):
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Başlık gerekli.")
    if data.get("type") not in TYPES:
        raise ValueError("Geçersiz tür.")
    sid = datetime.now().strftime("%Y%m%d-%H%M%S-") + re.sub(r"[^a-z0-9]", "", user["username"])[:12]
    d = _dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    files, total = [], 0
    for f in data.get("files") or []:
        name = re.sub(r"[^\w.\-]+", "_", Path(f.get("name", "ek")).name)[:80]
        if Path(name).suffix.lower() not in ALLOWED:
            raise ValueError(f"Bu dosya türü kabul edilmiyor: {name}")
        raw = base64.b64decode(f["data"].split(",", 1)[-1])
        total += len(raw)
        if total > MAX_BYTES:
            raise ValueError("Ekler toplamda 25 MB'ı geçemez.")
        (d / name).write_bytes(raw)
        files.append(name)
    s = {"id": sid, "type": data["type"], "title": title[:200], "text": (data.get("text") or "").strip()[:8000],
         "date": data.get("date") or "", "date_end": data.get("date_end") or "", "time": (data.get("time") or "")[:40],
         "place": (data.get("place") or "")[:200], "deadline": data.get("deadline") or "", "link": (data.get("link") or "").strip()[:500],
         "contact": (data.get("contact") or "").strip()[:200], "lang": data.get("lang") or "tr",
         "wants": [w for w in (data.get("wants") or []) if w in ("bulten", "telegram", "duyuru")],
         "files": files, "institution": user.get("institution"), "sender": user["username"], "sender_name": user.get("name"),
         "status": "yeni", "note": "", "created": datetime.now().isoformat(timespec="seconds"), "history": []}
    s["history"].append({"at": s["created"], "who": user.get("name"), "action": "gönderildi"})
    return _save(s)


def list_all(user=None):
    out = []
    for p in STORE.glob("*/gonderi.json"):
        s = json.loads(p.read_text(encoding="utf-8"))
        if user and s["sender"] != user["username"]:
            continue
        out.append(s)
    return sorted(out, key=lambda s: s["created"], reverse=True)


def set_status(sid, status, note, who):
    if status not in STATUSES:
        raise ValueError("Geçersiz durum.")
    s = load(sid)
    s["status"] = status
    if note is not None:
        s["note"] = note.strip()[:1000]
    s["history"].append({"at": datetime.now().isoformat(timespec="seconds"), "who": who,
                         "action": STATUSES[status] + (f" – {note.strip()}" if note else "")})
    return _save(s)


def add_history(sid, who, action):
    s = load(sid)
    s["history"].append({"at": datetime.now().isoformat(timespec="seconds"), "who": who, "action": action})
    return _save(s)
