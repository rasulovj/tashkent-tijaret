"""Telegram yayın bağlantısı (resmî Bot API).

Kurulum: @BotFather'dan bot oluşturulur, jeton panele girilir, bot her kanala yönetici
olarak eklenir ("Mesaj gönderme" yetkisiyle). Sonra PDF/görsel tek tıkla tüm kanallara gider.
Jeton yalnızca bu bilgisayarda config/telegram.json içinde saklanır; panele hiç geri gönderilmez.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import requests

CONFIG = Path("config/telegram.json")
LOG = Path("data/telegram_log.json")
API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_MAX = 1024


class TelegramError(ValueError):
    pass


def _load():
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {"channels": []}


def _save(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    CONFIG.chmod(0o600)  # jeton: yalnızca bu kullanıcı okuyabilir


def _call(token, method, data=None, files=None, timeout=60):
    try:
        r = requests.post(API.format(token=token, method=method), data=data, files=files, timeout=timeout)
        j = r.json()
    except (requests.RequestException, ValueError) as e:
        raise TelegramError(f"Telegram'a ulaşılamadı: {e}")
    if not j.get("ok"):
        raise TelegramError(j.get("description", "Telegram hatası"))
    return j["result"]


def status():
    cfg = _load()
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    return {"connected": bool(cfg.get("token")), "bot": cfg.get("bot"),
            "channels": cfg.get("channels", []), "log": log[-30:]}


def connect(token):
    token = token.strip()
    me = _call(token, "getMe")
    cfg = _load()
    cfg.update(token=token, bot={"username": me.get("username"), "name": me.get("first_name")})
    _save(cfg)
    return status()


def disconnect():
    cfg = _load()
    cfg.pop("token", None)
    cfg.pop("bot", None)
    _save(cfg)
    return status()


def add_channel(chat_id):
    cfg = _load()
    if not cfg.get("token"):
        raise TelegramError("Önce bot jetonuyla bağlanın.")
    chat_id = re.sub(r"^(https?://)?t\.me/", "", chat_id.strip())
    if not chat_id.startswith(("@", "-")):
        chat_id = "@" + chat_id
    chat = _call(cfg["token"], "getChat", {"chat_id": chat_id})
    me = _call(cfg["token"], "getMe")
    member = _call(cfg["token"], "getChatMember", {"chat_id": chat["id"], "user_id": me["id"]})
    can_post = member.get("status") == "creator" or (member.get("status") == "administrator"
                                                     and member.get("can_post_messages", True))
    if not can_post:
        raise TelegramError(f"Bot \"{chat.get('title')}\" kanalında mesaj gönderme yetkisine sahip yönetici değil.")
    ch = {"id": chat["id"], "handle": chat_id, "title": chat.get("title") or chat_id,
          "type": chat.get("type"), "enabled": True}
    cfg["channels"] = [c for c in cfg.get("channels", []) if c["id"] != ch["id"]] + [ch]
    _save(cfg)
    return status()


def update_channel(chat_id, enabled=None, remove=False):
    cfg = _load()
    chans = []
    for c in cfg.get("channels", []):
        if str(c["id"]) == str(chat_id):
            if remove:
                continue
            if enabled is not None:
                c["enabled"] = bool(enabled)
        chans.append(c)
    cfg["channels"] = chans
    _save(cfg)
    return status()


def publish(file_path, caption="", channel_ids=None, who="editör"):
    """Dosyayı seçili (yoksa etkin olan tüm) kanallara gönderir. PNG/JPG fotoğraf olarak gider."""
    cfg = _load()
    if not cfg.get("token"):
        raise TelegramError("Telegram bağlantısı yok.")
    chans = [c for c in cfg.get("channels", [])
             if (str(c["id"]) in map(str, channel_ids) if channel_ids else c.get("enabled"))]
    if not chans:
        raise TelegramError("Gönderilecek kanal seçilmedi.")
    caption = (caption or "").strip()
    if len(caption) > CAPTION_MAX:
        raise TelegramError(f"Açıklama {CAPTION_MAX} karakteri aşamaz ({len(caption)}).")
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    method, field = (("sendPhoto", "photo") if suffix in (".png", ".jpg", ".jpeg")
                     else ("sendVideo", "video") if suffix == ".mp4" else ("sendDocument", "document"))
    results = []
    for c in chans:
        try:
            with file_path.open("rb") as f:
                extra = {"supports_streaming": "true"} if method == "sendVideo" else {}
                msg = _call(cfg["token"], method, {"chat_id": c["id"], "caption": caption, **extra},
                            {field: (file_path.name, f)}, timeout=180)
            handle = (msg.get("chat") or {}).get("username")
            link = f"https://t.me/{handle}/{msg['message_id']}" if handle else None
            results.append({"channel": c["title"], "ok": True, "link": link})
        except TelegramError as e:
            results.append({"channel": c["title"], "ok": False, "error": str(e)})
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    log.append({"at": datetime.now().isoformat(timespec="seconds"), "who": who, "file": file_path.name,
                "caption": caption[:120], "results": results})
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return results
