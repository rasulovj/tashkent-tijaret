"""Göstergeler: Özbekistan Merkez Bankası (cbu.uz) resmi kurları + SVG çizgi grafik."""
import json
from datetime import date, timedelta
from pathlib import Path

import requests

API = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
CACHE = Path("data/rates.json")


def today_rates(ccys=("USD", "EUR", "RUB", "TRY")):
    rows = requests.get(API, timeout=20).json()
    return [{"ccy": r["Ccy"], "rate": float(r["Rate"]), "diff": float(r["Diff"]),
             "date": r["Date"]} for r in rows if r["Ccy"] in ccys]


def history(ccy, days=30):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    series = cache.setdefault(ccy, {})
    for i in range(days, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        if d in series:
            continue
        try:
            r = requests.get(f"{API}{ccy}/{d}/", timeout=15).json()
            series[d] = float(r[0]["Rate"])
        except (requests.RequestException, ValueError, IndexError, KeyError):
            pass
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=0))
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return sorted((d, v) for d, v in series.items() if d >= cutoff)


def line_svg(points, title, w=520, h=150, color="#8B1A1A", decimals=0):
    """Bağımlılıksız küçük SVG çizgi grafik (PDF'te keskin görünür)."""
    if len(points) < 2:
        return ""
    pl, pr, pt, pb = 46, 12, 26, 22
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.15 or 1
    lo, hi = lo - pad, hi + pad
    x = lambda i: pl + i * (w - pl - pr) / (len(points) - 1)
    y = lambda v: pt + (hi - v) * (h - pt - pb) / (hi - lo)
    fmt = lambda v: f"{v:,.{decimals}f}".replace(",", " ").replace(".", ",")
    path = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}"
                    for i, (_, v) in enumerate(points))
    grid = ""
    for k in range(3):
        gv = lo + (hi - lo) * (k + 0.5) / 3
        grid += (f'<line x1="{pl}" x2="{w-pr}" y1="{y(gv):.1f}" y2="{y(gv):.1f}" '
                 f'stroke="#ddd" stroke-width="0.6"/>'
                 f'<text x="{pl-4}" y="{y(gv)+3:.1f}" text-anchor="end">{fmt(gv)}</text>')
    d0, d1 = points[0][0], points[-1][0]
    last = points[-1][1]
    return f"""<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart">
<style>text{{font:9px Helvetica,Arial,sans-serif;fill:#555}} .t{{font-weight:bold;fill:#222;font-size:10.5px}}</style>
<text x="{pl}" y="13" class="t">{title}</text>{grid}
<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
<circle cx="{x(len(points)-1):.1f}" cy="{y(last):.1f}" r="2.6" fill="{color}"/>
<text x="{x(len(points)-1)-4:.1f}" y="{y(last)-6:.1f}" text-anchor="end" fill="{color}">{fmt(last)}</text>
<text x="{pl}" y="{h-6}">{d0[8:10]}.{d0[5:7]}</text>
<text x="{w-pr}" y="{h-6}" text-anchor="end">{d1[8:10]}.{d1[5:7]}</text>
</svg>"""
