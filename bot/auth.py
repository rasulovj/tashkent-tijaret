"""Kullanıcılar ve oturumlar.

Roller:
- yonetici: Ticaret Müşavirliği; panelin tamamı (inceleme, düzenleme, yayın, ayarlar)
- birim: diğer birimler (Büyükelçilik, Başkonsolosluk, müşavirlikler); yalnızca "Bilgi Gönder" sayfası

Şifreler PBKDF2-SHA256 ile saklanır (config/users.json, izin 600). Oturumlar bellekte tutulur.
Herkes (paneli çalıştıran bilgisayar dahil) kullanıcı adı ve şifreyle girer. Hiç yönetici yokken
"İlk kurulum" ekranı açılır; bu ekran yalnızca sunucudaki tek kullanımlık kurulum koduyla çalışır.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path

USERS = Path(os.environ.get("PANEL_USERS_FILE", "config/users.json"))  # testlerde ayrı dosya
SETUP_CODE = USERS.with_name("kurulum-kodu.txt")
NETWORK = Path("config/network.json")
SESSION_HOURS = 12
_sessions = {}
_fails = {}


def _load():
    return json.loads(USERS.read_text(encoding="utf-8")) if USERS.exists() else {}


def _save(users):
    USERS.parent.mkdir(parents=True, exist_ok=True)
    USERS.write_text(json.dumps(users, ensure_ascii=False, indent=1), encoding="utf-8")
    USERS.chmod(0o600)


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def list_users():
    return [{"username": u, **{k: v for k, v in d.items() if k not in ("hash", "salt")}} for u, d in sorted(_load().items())]


def create_user(username, password, role, institution, name=""):
    username = username.strip().lower()
    if not username.replace(".", "").replace("_", "").isalnum() or len(username) < 3:
        raise ValueError("Kullanıcı adı en az 3 karakter olmalı; harf, rakam, nokta veya alt çizgi içerebilir.")
    if len(password) < 8:
        raise ValueError("Şifre en az 8 karakter olmalı.")
    if role not in ("yonetici", "editor"):  # birim rolü kaldırıldı (22.10.2026)
        raise ValueError("Geçersiz rol.")
    users = _load()
    if username in users:
        raise ValueError("Bu kullanıcı adı zaten var.")
    salt = secrets.token_hex(16)
    users[username] = {"hash": _hash(password, salt), "salt": salt, "role": role, "institution": institution,
                       "name": name.strip() or username, "created": datetime.now().isoformat(timespec="seconds"),
                       "last_login": None}
    _save(users)


def set_password(username, password):
    if len(password) < 8:
        raise ValueError("Şifre en az 8 karakter olmalı.")
    users = _load()
    if username not in users:
        raise ValueError("Kullanıcı bulunamadı.")
    users[username]["salt"] = secrets.token_hex(16)
    users[username]["hash"] = _hash(password, users[username]["salt"])
    _save(users)
    for t, s in list(_sessions.items()):  # şifre değişince açık oturumlar kapanır
        if s["user"] == username:
            _sessions.pop(t)


def delete_user(username):
    users = _load()
    users.pop(username, None)
    _save(users)
    for t, s in list(_sessions.items()):
        if s["user"] == username:
            _sessions.pop(t)


def login(username, password, ip):
    now = time.time()
    fails = [t for t in _fails.get(ip, []) if now - t < 300]
    if len(fails) >= 5:
        raise PermissionError("Çok fazla hatalı deneme. 5 dakika sonra tekrar deneyin.")
    users = _load()
    u = users.get((username or "").strip().lower())
    if not u or not hmac.compare_digest(u["hash"], _hash(password or "", u["salt"])):
        _fails[ip] = fails + [now]
        raise PermissionError("Kullanıcı adı veya şifre hatalı.")
    _fails.pop(ip, None)
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"user": username.strip().lower(), "exp": now + SESSION_HOURS * 3600}
    u["last_login"] = datetime.now().isoformat(timespec="seconds")
    _save(users)
    return token


def logout(token):
    _sessions.pop(token, None)


def user_for(token):
    s = _sessions.get(token or "")
    if not s or s["exp"] < time.time():
        _sessions.pop(token or "", None)
        return None
    u = _load().get(s["user"])
    return {"username": s["user"], **{k: v for k, v in u.items() if k not in ("hash", "salt")}} if u else None


OPEN_ADMIN = {"username": "yonetici", "name": "Yönetici", "role": "yonetici", "institution": "ticaret"}  # şifresiz giriş
PUBLIC = os.environ.get("PANEL_PUBLIC") == "1"  # internette yayın: şifresiz giriş kapalı, çerez Secure


def has_admin():
    return any(u.get("role") == "yonetici" for u in _load().values())


def setup_code():
    """Hiç yönetici yoksa tek kullanımlık kurulum kodunu üretir/okur (yalnızca sunucudaki dosyada)."""
    if has_admin():
        SETUP_CODE.unlink(missing_ok=True)
        return None
    if not SETUP_CODE.exists():
        SETUP_CODE.parent.mkdir(parents=True, exist_ok=True)
        SETUP_CODE.write_text(secrets.token_hex(3).upper())
        SETUP_CODE.chmod(0o600)
    return SETUP_CODE.read_text().strip()


def first_setup(code, username, password, name, ip):
    if has_admin():
        raise PermissionError("Kurulum zaten yapılmış. Giriş ekranını kullanın.")
    now = time.time()
    fails = [t for t in _fails.get(ip, []) if now - t < 300]
    if len(fails) >= 5:
        raise PermissionError("Çok fazla hatalı deneme. 5 dakika sonra tekrar deneyin.")
    if not hmac.compare_digest((code or "").strip().upper(), setup_code() or ""):
        _fails[ip] = fails + [now]
        raise PermissionError("Kurulum kodu hatalı.")
    create_user(username, password, "yonetici", "ticaret", name)
    SETUP_CODE.unlink(missing_ok=True)
    return login(username, password, ip)


def guard_delete(username, by):
    users = _load()
    if username == by:
        raise ValueError("Kendi hesabınızı silemezsiniz.")
    if users.get(username, {}).get("role") == "yonetici" and sum(u["role"] == "yonetici" for u in users.values()) <= 1:
        raise ValueError("Son yönetici hesabı silinemez.")


def network():
    return json.loads(NETWORK.read_text(encoding="utf-8")) if NETWORK.exists() else {"lan": False}


def set_network(lan):
    NETWORK.parent.mkdir(parents=True, exist_ok=True)
    NETWORK.write_text(json.dumps({"lan": bool(lan)}), encoding="utf-8")


def lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # paket gönderilmez; yalnızca yerel arayüz seçilir
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None
