"""Kılavuz ekran görüntülerini panelden otomatik çeker ve kılavuz PDF'ini üretir.
Panel çalışırken: .venv/bin/python tools/make_guide.py
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
from bot.render import CHROME  # noqa: E402

BASE = "http://127.0.0.1:8765/"
OUT = Path("static/guide")
SHOTS = {
    "home": "#home", "editor": "#editor", "feed": "#feed", "search": "#feed/tekstil%20ihracat%C4%B1",
    "sources": "#sources", "studio": "#studio", "video": "#video", "pdfs": "#pdfs",
    "pdfview": "#pdfview/issue%3AEkonomi%20Haberleri-21.10.2026.pdf",
    "reports": "#reports", "report": "#report/sektor-ozbekistan-mobilya-2025",
    "telegram": "#telegram", "uz": "?ui=uz#home", "settings": "#settings",
    "city": "#report/sehir-ozbekistan-semerkant-tekstil-2026", "ann": "#ann", "inst": "#inst", "inbox": "#inbox", "giris": "giris",
}


def shot(name, frag):
    OUT.mkdir(parents=True, exist_ok=True)
    url = BASE + (frag if frag.startswith("?") else "" + frag)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1440,900",
                    "--virtual-time-budget=9000", f"--screenshot={(OUT / (name + '.png')).resolve()}", url],
                   check=True, capture_output=True, timeout=120)


if __name__ == "__main__":
    only = [] if sys.argv[1:] == ["--pdf"] else (sys.argv[1:] or list(SHOTS))
    for n in only:
        shot(n, SHOTS[n])
        print("  ", n)
    html = Path("static/kilavuz.html").resolve()
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={(OUT / 'Kullanim-Kilavuzu.pdf').resolve()}", html.as_uri()],
                   check=True, capture_output=True, timeout=120)
    print("  PDF:", OUT / "Kullanim-Kilavuzu.pdf")
    birim = Path("static/birim-kilavuzu.html").resolve()
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={(OUT / 'Birim-Kilavuzu.pdf').resolve()}", birim.as_uri()],
                   check=True, capture_output=True, timeout=120)
    print("  PDF:", OUT / "Birim-Kilavuzu.pdf")
