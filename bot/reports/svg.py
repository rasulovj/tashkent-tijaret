"""Rapor grafikleri: bağımlılıksız SVG (PDF'te keskin)."""
from html import escape

RED, ORANGE, SOFT, GRID, INK, MUTED = "#8B1A1A", "#D9822B", "#E9C9BE", "#e4dfda", "#222", "#666"
FONT = "font-family:Helvetica,Arial,sans-serif"


def _num(v, dec=1):
    return f"{v:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def hbar(labels, values, unit="", w=620):
    rowh, left, right = 22, 130, 70
    h = rowh * len(values) + 16
    mx = max(values) or 1
    out = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart" style="{FONT}">']
    for i, (l, v) in enumerate(zip(labels, values)):
        y = 6 + i * rowh
        bw = (w - left - right) * v / mx
        out.append(f'<text x="{left - 8}" y="{y + 14}" text-anchor="end" font-size="11" fill="{INK}">{escape(l)}</text>'
                   f'<rect x="{left}" y="{y + 3}" width="{bw:.1f}" height="{rowh - 8}" rx="3" fill="{RED if i == 0 else SOFT if i > 2 else ORANGE}"/>'
                   f'<text x="{left + bw + 6:.1f}" y="{y + 14}" font-size="10.5" fill="{MUTED}">{_num(v)} {escape(unit)}</text>')
    out.append("</svg>")
    return "".join(out)


def line(labels, values, title="", unit="", w=620, h=210):
    pl, pr, pt, pb = 56, 20, 30, 28
    lo, hi = min(values), max(values)
    pad = (hi - lo) * .2 or abs(hi) * .1 or 1
    lo, hi = lo - pad, hi + pad
    X = lambda i: pl + i * (w - pl - pr) / max(len(values) - 1, 1)
    Y = lambda v: pt + (hi - v) * (h - pt - pb) / (hi - lo)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(values))
    out = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart" style="{FONT}">',
           f'<text x="{pl}" y="16" font-size="12" font-weight="bold" fill="{INK}">{escape(title)}{" (" + escape(unit) + ")" if unit else ""}</text>']
    for k in range(4):
        v = lo + (hi - lo) * (k + .5) / 4
        out.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}"/>'
                   f'<text x="{pl - 6}" y="{Y(v) + 3:.1f}" text-anchor="end" font-size="9.5" fill="{MUTED}">{_num(v)}</text>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="{RED}" stroke-width="2.4" stroke-linejoin="round"/>')
    for i, (l, v) in enumerate(zip(labels, values)):
        out.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.2" fill="{RED}"/>'
                   f'<text x="{X(i):.1f}" y="{Y(v) - 8:.1f}" text-anchor="middle" font-size="9.5" fill="{INK}">{_num(v)}</text>'
                   f'<text x="{X(i):.1f}" y="{h - 8}" text-anchor="middle" font-size="10" fill="{MUTED}">{escape(l)}</text>')
    out.append("</svg>")
    return "".join(out)


def bars(labels, series, unit="", w=620, h=220):
    pl, pr, pt, pb = 50, 16, 34, 26
    names = list(series)
    mx = max(max(v) for v in series.values()) or 1
    gw = (w - pl - pr) / len(labels)
    bw = gw * .7 / len(names)
    colors = [RED, ORANGE, SOFT]
    out = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart" style="{FONT}">']
    for k, n in enumerate(names):
        out.append(f'<rect x="{pl + k * 90}" y="6" width="10" height="10" fill="{colors[k]}"/>'
                   f'<text x="{pl + k * 90 + 14}" y="15" font-size="11" fill="{INK}">{escape(n)}</text>')
    out.append(f'<text x="{w - pr}" y="15" text-anchor="end" font-size="10" fill="{MUTED}">{escape(unit)}</text>')
    for i, l in enumerate(labels):
        for k, n in enumerate(names):
            v = series[n][i]
            bh = (h - pt - pb) * v / mx
            x = pl + i * gw + gw * .15 + k * bw
            out.append(f'<rect x="{x:.1f}" y="{h - pb - bh:.1f}" width="{bw - 2:.1f}" height="{bh:.1f}" fill="{colors[k]}" rx="2"/>'
                       f'<text x="{x + bw / 2:.1f}" y="{h - pb - bh - 4:.1f}" text-anchor="middle" font-size="9" fill="{INK}">{_num(v)}</text>')
        out.append(f'<text x="{pl + i * gw + gw / 2:.1f}" y="{h - 8}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{escape(l)}</text>')
    out.append(f'<line x1="{pl}" x2="{w - pr}" y1="{h - pb}" y2="{h - pb}" stroke="#bbb"/></svg>')
    return "".join(out)


def render(chart):
    if not chart:
        return ""
    t = chart["type"]
    if t == "hbar":
        return hbar(chart["labels"], chart["values"], chart.get("unit", ""))
    if t == "line":
        return line(chart["labels"], chart["values"], chart.get("title", ""), chart.get("unit", ""))
    if t == "bars":
        return bars(chart["labels"], chart["series"], chart.get("unit", ""))
    return ""
