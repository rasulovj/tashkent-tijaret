"""Veri bölümleri: her blok türü bir tablo (+ isteğe bağlı grafik) üretir.

Dönüş: {"columns": [...], "rows": [[...]], "note": "...", "chart": {...} | None}
"""
from collections import defaultdict
from datetime import datetime

from bot.reports import sources as src


def fmt(v, dec=1):
    if v is None or v == "":
        return "-"
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def hs_codes6(hs):
    """'94' -> fasıl 94 altındaki tüm 6'lı GTİP kodları (Comtrade referansından)."""
    src.hs_desc("000000")  # referansı yükle
    for level in (6, 4):  # geniş sektörlerde (ör. tekstil) 6'lı kod sayısı API sınırını aşar -> 4'lü düzey
        out = sorted(c for c in src._hs_ref
                     if len(c) == level and any(c.startswith(h) for h in hs if len(h) <= level))
        out += [h for h in hs if len(h) > level]  # zaten daha ayrıntılı verilmiş kodlar
        if out and len(out) <= 140:
            return out
    return hs


def _agg(rows, key):
    acc = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        acc[r[key]][0] += r.get("primaryValue") or 0
        acc[r[key]][1] += r.get("netWgt") or 0
    return acc


def top_partners(b, p, cmd=None):
    cmd = cmd or ",".join(p["hs"])
    year = src.latest_year(p["reporter"], cmd, p["yil"])
    agg = _agg(src.comtrade(p["reporter"], b["flow"], year, cmd), "partnerCode")
    total = agg.pop(0, [sum(v[0] for v in agg.values()), 0])[0] or 1
    top = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)[: b.get("n", 10)]
    rows = [[i, src.partner_name(c), fmt(v / 1e6, 1), fmt(w / 1000, 0) if w else "-", fmt(v / total * 100, 0)]
            for i, (c, (v, w)) in enumerate(top, 1)]
    rows.append(["", "TOPLAM", fmt(total / 1e6, 1), "", "100"])
    word = "İthalat" if b["flow"] == "M" else "İhracat"
    return {"columns": ["Sıra", "Ülke", f"{word} Değeri (milyon $) ({year})", "Miktar (ton)", "Pay (%)"],
            "rows": rows, "year": year,
            "note": f"Kaynak: UN Comtrade, {p['ulke']} beyanı, {year} yılı.",
            "chart": {"type": "hbar", "labels": [r[1] for r in rows[:-1]],
                      "values": [v / 1e6 for _, (v, _) in top], "unit": "milyon $"} if b.get("chart") else None}


def top_partners_total(b, p):
    return top_partners(b, p, cmd="TOTAL")


def top_products(b, p):
    cmd = ",".join(p["hs"])
    year = src.latest_year(p["reporter"], cmd, p["yil"])
    codes = hs_codes6(p["hs"])
    agg = _agg(src.comtrade(p["reporter"], b["flow"], year, ",".join(codes), 0), "cmdCode")
    total = sum(r.get("primaryValue") or 0 for r in src.comtrade(p["reporter"], b["flow"], year, cmd, 0)) or 1
    top = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)[: b.get("n", 10)]
    rows = [[i, c, src.hs_desc(c), fmt(v / 1e6, 2), fmt(v / total * 100, 1)] for i, (c, (v, _)) in enumerate(top, 1)]
    word = "İthalat" if b["flow"] == "M" else "İhracat"
    return {"columns": ["Sıra", "GTİP", "Ürün", f"{word} (milyon $) ({year})", "Pay (%)"], "rows": rows,
            "year": year, "note": f"Kaynak: UN Comtrade, {p['ulke']} beyanı, {year} yılı, HS 6'lı düzey.",
            "chart": None}


def tr_exports(b, p):
    codes = hs_codes6(p["hs"])
    years = list(range(p["yil"] - b.get("years", 5) + 1, p["yil"] + 1))
    data = {}
    for y in years:
        rows = src.comtrade(792, "X", y, ",".join(codes), p["reporter"])
        if rows:
            data[y] = _agg(rows, "cmdCode")
    years = [y for y in years if y in data]
    if not years:
        return {"columns": [], "rows": [], "note": "Türkiye verisi henüz yayımlanmamış.", "chart": None}
    idx = 0 if b["measure"] == "value" else 1
    last = years[-1]
    ranked = sorted(data[last].items(), key=lambda kv: kv[1][idx], reverse=True)[: b.get("n", 10)]
    conv = (lambda v: fmt(v, 0)) if idx == 0 else (lambda v: fmt(v / 1000, 1))
    rows = [[i, c, src.hs_desc(c)] + [conv(data[y][c][idx]) if c in data[y] else "-" for y in years]
            for i, (c, _) in enumerate(ranked, 1)]
    totals = [sum(v[idx] for v in data[y].values()) for y in years]
    rows.append(["", "", "TOPLAM (fasıl)"] + [conv(t) for t in totals])
    unit = "$" if idx == 0 else "ton"
    return {"columns": ["Sıra", "GTİP", "Ürün"] + [str(y) for y in years], "rows": rows, "unit": unit,
            "note": f"Değerler {unit}. Kaynak: UN Comtrade, Türkiye beyanı (Türkiye'nin {p['ulke']}'a ihracatı).",
            "chart": {"type": "line", "labels": [str(y) for y in years], "values": [t / 1e6 for t in totals],
                      "unit": "milyon $", "title": f"Türkiye'nin {p['ulke']}'a {p.get('sektor', '')} ihracatı"}
            if b.get("chart") and idx == 0 else None}


def wb_series(b, p):
    y1 = int(p["yil"])
    series = {ind: src.worldbank(p["iso3"], ind, y1 - 12, y1) for ind, *_ in b["indicators"]}
    have = sorted({y for s in series.values() for y in s})
    years = have[-b.get("years", 5):]
    rows = [[label] + [fmt(series[ind].get(y) * scale, dec) if series[ind].get(y) is not None else "-" for y in years]
            for ind, label, scale, dec in b["indicators"]]
    ind, label, scale, _ = b["indicators"][b.get("chart_row", 0)]
    pts = [(str(y), series[ind][y] * scale) for y in years if series[ind].get(y) is not None]
    return {"columns": ["Gösterge"] + [str(y) for y in years], "rows": rows,
            "note": "Kaynak: Dünya Bankası, Dünya Kalkınma Göstergeleri (WDI).",
            "chart": {"type": "line", "labels": [a for a, _ in pts], "values": [v for _, v in pts], "title": label}
            if b.get("chart") and len(pts) > 1 else None}


def trade_total(b, p):
    ys = list(range(int(p["yil"]) - b.get("years", 5), int(p["yil"]) + 1))
    vals = {}
    for y in ys:
        m = sum(r.get("primaryValue") or 0 for r in src.comtrade(p["reporter"], "M", y, "TOTAL", 0))
        x = sum(r.get("primaryValue") or 0 for r in src.comtrade(p["reporter"], "X", y, "TOTAL", 0))
        if m and x:
            vals[y] = (x / 1e9, m / 1e9)
    ys = sorted(vals)[-b.get("years", 5):]
    if not ys:
        return {"columns": [], "rows": [], "note": "Comtrade'de veri bulunamadı.", "chart": None}
    line = lambda f: [fmt(f(*vals[y]), 1) for y in ys]
    chg = lambda f: fmt((f(*vals[ys[-1]]) / f(*vals[ys[-2]]) - 1) * 100, 0) if len(ys) > 1 and f(*vals[ys[-2]]) else "-"
    fns = [("Dış Ticaret Hacmi", lambda x, m: x + m), ("İhracat", lambda x, m: x), ("İthalat", lambda x, m: m),
           ("Denge", lambda x, m: x - m)]
    rows = [[n] + line(f) + [chg(f) if n != "Denge" else "-"] for n, f in fns]
    return {"columns": ["Milyar $"] + [str(y) for y in ys] + ["Değişim (%)"], "rows": rows,
            "note": f"Kaynak: UN Comtrade, {p['ulke']} beyanı (mal ticareti).",
            "chart": {"type": "bars", "labels": [str(y) for y in ys],
                      "series": {"İhracat": [vals[y][0] for y in ys], "İthalat": [vals[y][1] for y in ys]},
                      "unit": "milyar $"} if b.get("chart") else None}


KINDS = {"top_partners": top_partners, "top_partners_total": top_partners_total, "top_products": top_products,
         "tr_exports": tr_exports, "wb_series": wb_series, "trade_total": trade_total}


def run(block, params):
    out = KINDS[block["kind"]](block, params)
    out["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return out


# ---------------------------------------------------------------- bölge (SIAT) ve bölge haberleri
NATIONAL = "Republic of Uzbekistan"


def siat_region(b, p):
    region = p["region_en"]
    tables = {ind: src.siat_table(ind) for ind, *_ in b["indicators"]}
    years = sorted({y for t in tables.values() for y in t.get(region, {})})[-b.get("years", 5):]
    rows, chart_series = [], {}
    for ind, label, dec in b["indicators"]:
        t = tables[ind]
        reg, nat = t.get(region, {}), t.get(NATIONAL, {})
        last = max((y for y in years if y in reg), default=None)
        share = fmt(reg[last] / nat[last] * 100, 1) if last and nat.get(last) else "-"
        others = sorted(((s.get(last) or 0) for n, s in t.items() if n != NATIONAL), reverse=True) if last else []
        rank = (others.index(reg[last]) + 1) if last and reg.get(last) in others else "-"
        rows.append([label, src.siat_unit(ind)] + [fmt(reg.get(y), dec) for y in years] + [share, f"{rank}/{len(others)}" if others else "-"])
        chart_series[label] = [reg.get(y) or 0 for y in years]
    chart = None
    if b.get("chart") == "line" and years:
        first = b["indicators"][0]
        chart = {"type": "line", "labels": [str(y) for y in years], "values": chart_series[first[1]],
                 "title": f"{p['sehir']} – {first[1]}", "unit": src.siat_unit(first[0])}
    elif b.get("chart") == "bars" and years:
        chart = {"type": "bars", "labels": [str(y) for y in years], "series": chart_series,
                 "unit": src.siat_unit(b["indicators"][0][0])}
    return {"columns": ["Gösterge", "Birim"] + [str(y) for y in years] + ["Ülke payı (%)", "Sıra"], "rows": rows,
            "note": f"Kaynak: Özbekistan İstatistik Ajansı (SIAT), {p['sehir']} verileri. Pay ve sıra son yıl içindir.",
            "chart": chart}


def siat_rank(b, p):
    """Bölgenin her göstergede 14 bölge arasındaki sırası ve ülke payı (son yıl)."""
    region = p["region_en"]
    rows = []
    for ind, label, dec in b["indicators"]:
        t = src.siat_table(ind)
        reg = t.get(region, {})
        if not reg:
            continue
        last = max(reg)
        vals = sorted(((s.get(last) or 0, n) for n, s in t.items() if n != NATIONAL), reverse=True)
        rank = next((i for i, (_, n) in enumerate(vals, 1) if n == region), "-")
        nat = t.get(NATIONAL, {}).get(last)
        leader = vals[0][1] if vals else ""
        rows.append([label, str(last), fmt(reg[last], dec), src.siat_unit(ind), f"{rank}/{len(vals)}",
                     fmt(reg[last] / nat * 100, 1) if nat else "-", src.region_tr(leader)])
    return {"columns": ["Gösterge", "Yıl", "Değer", "Birim", "Sıra", "Ülke payı (%)", "Birinci bölge"], "rows": rows,
            "note": "Kaynak: Özbekistan İstatistik Ajansı (SIAT). Sıra: 14 bölge (Karakalpakistan, 12 vilayet, Taşkent şehri).",
            "chart": {"type": "hbar", "labels": [r[0] for r in rows],
                      "values": [float(r[5].replace(".", "").replace(",", ".")) if r[5] != "-" else 0 for r in rows],
                      "unit": "% ülke payı"} if rows else None}


def region_news(b, p):
    from datetime import datetime, timedelta, timezone
    from bot import collect, translate
    from bot.select import score
    kw = [k.lower() for k in p.get("kw", [])]
    sector_kw = [k.lower() for k in p.get("odak_kw", [])] if b.get("sector") else []
    if b.get("sector") and not sector_kw:
        return {"columns": [], "rows": [], "note": "Odak sektör girilmedi.", "chart": None}
    since = datetime.now(timezone.utc) - timedelta(days=b.get("days", 90))
    hits = []
    for it in collect.load_raw().values():
        if datetime.fromisoformat(it["published"]) < since:
            continue
        text = collect.tr_lower(it["title"] + " " + it["summary"])
        if any(k in text for k in kw) and (not sector_kw or any(k in text for k in sector_kw)) and score(it) >= 2:
            hits.append(it)  # yalnızca ekonomiyle ilgili bölge haberleri
    hits.sort(key=lambda x: x["published"], reverse=True)
    hits = hits[: b.get("n", 15)]
    for lang in {h["lang"] for h in hits} - {"tr"}:
        translate.translate_many([h["title"] for h in hits if h["lang"] == lang], lang, "tr", limit=20)
    rows = []
    for h in hits:
        t = h["title"] if h["lang"] == "tr" else (translate.cached(h["title"], h["lang"], "tr") or h["title"])
        rows.append([h["published"][:10], h.get("publisher") or h["source"], {"text": t, "url": h["url"]}])
    return {"columns": ["Tarih", "Kaynak", "Haber"], "rows": rows,
            "note": f"Robotun haber arşivinden, son {b.get('days', 90)} gün. Başlıklar Türkçeye çevrildi.", "chart": None}


KINDS.update(siat_region=siat_region, siat_rank=siat_rank, region_news=region_news)
