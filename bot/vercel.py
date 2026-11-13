"""Önizleme sitesini Vercel'e yükler (resmî REST API: /v2/files + /v13/deployments).

Jeton: vercel.com → Account Settings → Tokens. Yalnızca bu bilgisayarda config/keys.json içinde saklanır.
"""
import hashlib
import time
from pathlib import Path

import requests

API = "https://api.vercel.com"


class VercelError(RuntimeError):
    pass


def _check(r):
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message") or r.text[:200]
        except ValueError:
            msg = r.text[:200]
        if r.status_code in (401, 403):
            msg = "Vercel jetonu geçersiz veya yetkisiz. " + msg
        raise VercelError(f"Vercel hatası {r.status_code}: {msg}")
    return r


def deploy(token, project, folder, progress=lambda i, n, m: None):
    folder = Path(folder)
    head = {"Authorization": f"Bearer {token}"}
    files = [p for p in sorted(folder.rglob("*")) if p.is_file()]
    if not files:
        raise VercelError("Önce önizleme sitesini hazırlayın.")
    manifest = []
    for i, p in enumerate(files, 1):
        data = p.read_bytes()
        sha = hashlib.sha1(data).hexdigest()
        progress(i, len(files) + 2, f"Yükleniyor {i}/{len(files)}: {p.name[:40]}")
        _check(requests.post(f"{API}/v2/files", data=data, timeout=120,
                             headers={**head, "Content-Type": "application/octet-stream",
                                      "x-vercel-digest": sha, "Content-Length": str(len(data))}))
        manifest.append({"file": p.relative_to(folder).as_posix(), "sha": sha, "size": len(data)})
    progress(len(files) + 1, len(files) + 2, "Yayın oluşturuluyor")
    body = {"name": project, "files": manifest, "target": "production",
            "projectSettings": {"framework": None, "buildCommand": None, "installCommand": None,
                                "outputDirectory": None, "devCommand": None}}
    dep = _check(requests.post(f"{API}/v13/deployments?skipAutoDetectionConfirmation=1", json=body,
                               headers=head, timeout=120)).json()
    for _ in range(90):  # en fazla ~3 dakika bekle
        st = _check(requests.get(f"{API}/v13/deployments/{dep['id']}", headers=head, timeout=30)).json()
        state = st.get("readyState") or st.get("status")
        if state == "READY":
            aliases = st.get("alias") or []
            main = next((a for a in aliases if a.endswith(".vercel.app") and "-" not in a.split(".")[0][len(project):]), None)
            return {"url": f"https://{main or (aliases[0] if aliases else st['url'])}", "deployment": f"https://{st['url']}",
                    "aliases": [f"https://{a}" for a in aliases]}
        if state in ("ERROR", "CANCELED"):
            raise VercelError(f"Vercel yayını başarısız: {st.get('errorMessage') or state}")
        progress(len(files) + 2, len(files) + 2, f"Vercel hazırlıyor ({state})")
        time.sleep(2)
    raise VercelError("Vercel yayını zamanında tamamlanmadı; Vercel panelinden kontrol edin.")
