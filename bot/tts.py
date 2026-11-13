"""Seslendirme sağlayıcıları.

- macOS `say`: ücretsiz, çevrimdışı. Sistem Ayarları > Erişilebilirlik > Seslendirilen İçerik > Sesleri Yönet'ten
  "Yelda (Gelişmiş/Premium)" indirilirse otomatik o kullanılır.
- Microsoft Azure Neural TTS (resmî API, aylık 500 bin karakter ücretsiz): çok daha canlı Türkçe ve Özbekçe sesler.
"""
import os
import re
import subprocess
from html import escape
from pathlib import Path

import requests

AZURE_VOICES = {
    "tr": [("tr-TR-EmelNeural", "Emel (kadın, canlı)"), ("tr-TR-AhmetNeural", "Ahmet (erkek)")],
    "uz": [("uz-UZ-MadinaNeural", "Madina (kadın)"), ("uz-UZ-SardorNeural", "Sardor (erkek)")],
    "en": [("en-US-AvaNeural", "Ava (female)"), ("en-GB-RyanNeural", "Ryan (male)")],
    "ru": [("ru-RU-SvetlanaNeural", "Светлана"), ("ru-RU-DmitryNeural", "Дмитрий")],
}
MAC_LOCALE = {"tr": "tr_TR", "en": "en_", "ru": "ru_RU", "uz": "uz_"}


def mac_voices(lang):
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return []
    found = []
    for line in out.splitlines():
        m = re.match(r"^(.+?)\s{2,}(\w+)\s+#", line)
        if m and m.group(2).startswith(MAC_LOCALE[lang].rstrip("_")):
            found.append(m.group(1).strip())
    # gelişmiş/premium sesler önce
    return sorted(found, key=lambda n: (0 if re.search(r"Premium|Enhanced|Gelişmiş", n) else 1, n))[:6]


def voices(lang):
    out = []
    azure = bool(os.environ.get("AZURE_SPEECH_KEY"))
    for vid, label in AZURE_VOICES.get(lang, []):
        out.append({"id": "azure:" + vid, "label": f"{label} · Azure", "available": azure,
                    "note": "" if azure else "Ayarlar'dan Azure anahtarı girin"})
    for name in mac_voices(lang):
        enhanced = bool(re.search(r"Premium|Enhanced|Gelişmiş", name))
        out.append({"id": "mac:" + name, "label": f"{name} · Mac{' (gelişmiş)' if enhanced else ' (temel)'}",
                    "available": True, "note": ""})
    return out


def default_voice(lang, preferred=None):
    vs = [v for v in voices(lang) if v["available"]]
    if preferred and any(v["id"] == preferred for v in vs):
        return preferred
    return vs[0]["id"] if vs else None


def synthesize(text, voice_id, out_wav):
    out_wav = Path(out_wav)
    provider, _, name = voice_id.partition(":")
    if provider == "azure":
        region = os.environ.get("AZURE_SPEECH_REGION", "westeurope")
        lang = "-".join(name.split("-")[:2])
        ssml = (f'<speak version="1.0" xml:lang="{lang}"><voice name="{name}">'
                f'<prosody rate="+4%">{escape(text)}</prosody></voice></speak>')
        r = requests.post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                          headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                                   "Content-Type": "application/ssml+xml",
                                   "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                                   "User-Agent": "TaskentTicaretBot"},
                          data=ssml.encode("utf-8"), timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Azure seslendirme hatası {r.status_code}: {r.text[:200]}")
        out_wav.write_bytes(r.content)
    else:
        subprocess.run(["say", "-v", name, "-r", "185", "--file-format=WAVE", "--data-format=LEI16@22050",
                        "-o", str(out_wav), text], check=True)
    return out_wav
