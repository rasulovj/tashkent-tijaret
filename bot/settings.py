"""Panelden girilen anahtarlar ve tercihler (yalnızca bu bilgisayarda, config/keys.json, izin 600)."""
import json
import os
from pathlib import Path

PATH = Path("config/keys.json")
ENV = {"anthropic_api_key": "ANTHROPIC_API_KEY", "azure_speech_key": "AZURE_SPEECH_KEY",
       "azure_speech_region": "AZURE_SPEECH_REGION", "vercel_token": "VERCEL_TOKEN"}


def load():
    return json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}


def apply():
    """Kayıtlı anahtarları süreç ortamına yükler (ortamda zaten varsa ona dokunmaz)."""
    for k, env in ENV.items():
        v = load().get(k)
        if v and not os.environ.get(env):
            os.environ[env] = v


def update(values):
    cur = load()
    for k, v in values.items():
        if k in ENV or k in ("voice_tr", "voice_en", "voice_ru", "voice_uz", "vercel_project", "vercel_url"):
            v = (v or "").strip()
            if v:
                cur[k] = v
                if k in ENV:
                    os.environ[ENV[k]] = v
            elif k in cur and values.get("clear_" + k):
                cur.pop(k)
                os.environ.pop(ENV.get(k, ""), None)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    PATH.chmod(0o600)
    return status()


def status():
    cur = load()
    return {"anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "azure": bool(os.environ.get("AZURE_SPEECH_KEY")),
            "azure_region": os.environ.get("AZURE_SPEECH_REGION", "westeurope"),
            "voices": {l: cur.get("voice_" + l) for l in ("tr", "en", "ru", "uz")},
            "vercel": bool(os.environ.get("VERCEL_TOKEN")), "vercel_project": cur.get("vercel_project") or "taskentticaret",
            "vercel_url": cur.get("vercel_url"), "ai_cost": _ai_cost()}


def _ai_cost():
    from bot import writer
    return {"month": writer.month_cost(), "limit": writer.monthly_limit()}
