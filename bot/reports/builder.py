"""Rapor üretimi: rapor oluşturma, veri güncelleme, önceki yılın PDF'inden içe aktarma, PDF çıktısı.

Rapor = config/reports/<tür>.json şablonu + parametreler; data/reports/<id>/report.json'da saklanır.
"""
import json
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

import fitz
from jinja2 import Environment, FileSystemLoader

from bot.render import CHROME
from bot.reports import blocks, svg

TYPES = Path("config/reports")
STORE = Path("data/reports")
LOGO = Path("config/assets/logo.png")


def types():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(TYPES.glob("*.json"))}


def _fill(text, p):
    up = lambda s: str(s).replace("i", "İ").replace("ı", "I").upper()
    return (text.replace("{ulke}", str(p.get("ulke", ""))).replace("{ULKE}", up(p.get("ulke", "")))
            .replace("{sektor}", str(p.get("sektor", ""))).replace("{SEKTOR}", up(p.get("sektor", "")))
            .replace("{yil}", str(p.get("yil", ""))).replace("{sehir}", str(p.get("sehir", "")))
            .replace("{SEHIR}", up(p.get("sehir", ""))).replace("{odak}", str(p.get("odak") or "—")))


def _norm_params(t, raw):
    p = {}
    for spec in t["params"]:
        v = raw.get(spec["key"], spec["default"])
        if isinstance(spec["default"], int):
            v = int(v)
        p[spec["key"]] = v
    if "hs" in p:
        p["hs"] = [h.strip() for h in str(p["hs"]).split(",") if h.strip()]
    if "sehir" in p:  # şehir raporu: SIAT bölge adı ve haber anahtar kelimeleri
        from bot.reports import sources
        reg = sources.regions()[p["sehir"]]
        p["region_en"], p["kw"] = reg["en"], reg["kw"]
        if p.get("odak"):
            from bot import translate
            en = translate.translate(p["odak"], "tr", "en") or ""
            p["odak_kw"] = [w.lower() for w in (p["odak"] + " " + en).replace(",", " ").split() if len(w) > 3]
    return p


def _slug(s):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", s.translate(tr).lower()).strip("-")


def create(type_key, raw_params, who="editör"):
    t = types()[type_key]
    p = _norm_params(t, raw_params)
    title = " ".join(_fill(x, p) for x in t["cover"])
    rid = _slug(f"{type_key}-{p.get('ulke', '')}-{p.get('sehir', '')}-{p.get('sektor', '')}-{p.get('odak', '')}-{p.get('yil', '')}")
    rep = {"id": rid, "type": type_key, "type_name": t["name"], "title": title, "params": p,
           "cover_lines": [_fill(x, p) for x in t["cover"]],
           "created": datetime.now().isoformat(timespec="seconds"), "history": [],
           "sections": [{**s, "title": _fill(s["title"], p), "text": "", "status": "boş"} for s in t["sections"]
                        if not (s["id"] == "odak" and not p.get("odak"))]}  # odak sektör yoksa bölüm eklenmez
    log(rep, who, "rapor oluşturuldu")
    save(rep)
    return rep


def path(rid):
    return STORE / Path(rid).name


def load(rid):
    return json.loads((path(rid) / "report.json").read_text(encoding="utf-8"))


def save(rep):
    path(rep["id"]).mkdir(parents=True, exist_ok=True)
    rep["updated"] = datetime.now().isoformat(timespec="seconds")
    (path(rep["id"]) / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


def log(rep, who, action):
    rep.setdefault("history", []).append({"at": datetime.now().isoformat(timespec="seconds"),
                                          "who": who, "action": action})


def list_reports():
    out = []
    for p in sorted(STORE.glob("*/report.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        secs = [s for s in r["sections"] if s["kind"] != "heading"]
        out.append({"id": r["id"], "title": r["title"], "type": r["type"], "type_name": r["type_name"],
                    "updated": r.get("updated"), "total": len(secs),
                    "filled": sum(1 for s in secs if s["status"] != "boş"),
                    "approved": sum(1 for s in secs if s["status"] == "onaylandı"),
                    "pdfs": sorted(x.name for x in p.parent.glob("*.pdf"))})
    return out


# ---------------------------------------------------------------- veri
def refresh(rep, sid=None, who="editör"):
    errors = []
    for s in rep["sections"]:
        if s["kind"] != "data" or (sid and s["id"] != sid):
            continue
        try:
            s["data"] = blocks.run(s["block"], rep["params"])
            s.pop("data_error", None)
            if s["status"] in ("boş", "önceki rapordan"):
                s["status"] = "veri güncel"
        except Exception as e:
            s["data_error"] = f"{type(e).__name__}: {e}"
            errors.append(f"{s['id']}: {e}")
    log(rep, who, "veriler güncellendi" + (f" ({len(errors)} hata)" if errors else ""))
    save(rep)
    return errors


# ---------------------------------------------------------------- içe aktarma
def _norm(s):
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^0-9a-zçğıöşü]+", "", s)


def _strip_num(s):
    return re.sub(r"^\s*\d+(\.\d+)*\.?\s*[-–]?\s*", "", s)


BULLET = re.compile(r"^\s*[•●▪➢•➢▪-]\s*")


def import_pdf(rep, pdf_bytes, who="editör"):
    """Önceki yılın raporunu bölümlere ayırıp metin bölümlerine taslak olarak yerleştirir."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    secs = [s for s in rep["sections"]]
    targets = [(i, _norm(_strip_num(s["title"]))) for i, s in enumerate(secs)]
    cur, pos, found = None, 0, {}
    body = {i: [] for i in range(len(secs))}
    open_paren = False  # başlık "(Örnek: ..." ile sonraki satırlara taşıyorsa

    def flush(lines):
        if cur is None or not lines:
            return
        para = re.sub(r"-\n(?=[a-zçğıöşü])", "", "\n".join(lines))
        if BULLET.match(para):
            para = "- " + BULLET.sub("", para)
        para = re.sub(r"\s*\n\s*", " ", para).strip()
        letters = [c for c in para if c.isalpha()]
        digits = sum(c.isdigit() for c in para)
        if digits > 0.25 * len(para) or (letters and len(para) < 300
                                          and sum(c.isupper() for c in letters) > 0.6 * len(letters)):
            return  # eski tablo satırları / büyük harfli hücre metinleri
        if len(para) >= 25 or para.endswith(":"):  # kısa parçalar: tablo hücreleri vb.
            body[cur].append(para)

    # Gövde yazı boyutu: başlıklar bundan büyük ya da kalın + numaralı olur
    sizes = {}
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    sizes[round(sp["size"])] = sizes.get(round(sp["size"]), 0) + len(sp["text"])
    body_size = max(sizes, key=sizes.get) if sizes else 12

    def heading_like(text, size, bold):
        return (size >= body_size + 0.8 or (bold and re.match(r"^\d+(\.\d+)*\.?(\s|$)", text))
                or (bold and len(text) > 4 and text == text.upper()))

    for page in doc:
        h = page.rect.height
        for b in page.get_text("dict")["blocks"]:
            x0, y0, x1, y1 = b["bbox"]
            lines = []
            for l in b.get("lines", []):
                t = "".join(sp["text"] for sp in l["spans"]).strip()
                if t:
                    sp = max(l["spans"], key=lambda s: len(s["text"].strip()))
                    lines.append((t, sp["size"], "Bold" in sp["font"] or bool(sp["flags"] & 16)))
            raw = "\n".join(t for t, *_ in lines)
            if not raw or "....." in raw or (y0 < 45 or y1 > h - 35) and len(raw) < 60:
                continue  # üst/alt bilgi, içindekiler
            if re.fullmatch(r"[\d.\s]+", raw) or raw.upper().startswith("TAŞKENT TİCARET MÜŞAVİRLİĞİ"):
                continue
            attrs = lines
            lines = [t for t, *_ in attrs]
            buf, k = [], 0
            while k < len(lines):
                line = lines[k]
                if open_paren:  # başlığın parantez içi devamı
                    open_paren = ")" not in line
                    k += 1
                    continue
                head = _norm(_strip_num(" ".join(lines[k:k + 3])))
                hit = None
                for j in range(pos, min(pos + 6, len(targets)) if heading_like(*attrs[k]) else pos):
                    nt = targets[j][1]
                    n = min(len(nt), 18)
                    if n >= 5 and head.startswith(nt[:n]):
                        hit = j
                        break
                if hit is None:
                    buf.append(line)
                    k += 1
                    continue
                flush(buf)
                buf = []
                cur, pos = targets[hit][0], hit + 1
                found[cur] = True
                acc, nt, consumed = "", targets[hit][1], ""
                while k < len(lines) and len(acc) < len(nt) - 2:  # başlık satırlarını atla
                    consumed += lines[k]
                    acc += _norm(_strip_num(lines[k]))
                    k += 1
                open_paren = consumed.count("(") > consumed.count(")")
            flush(buf)
    n = 0
    for i, s in enumerate(secs):
        if body[i] and s["kind"] != "heading":
            s["text"] = "\n\n".join(body[i])
            s["imported"] = True
            if s["status"] == "boş":
                s["status"] = "önceki rapordan"
            n += 1
    log(rep, who, f"önceki rapordan içe aktarıldı ({n} bölüm, {len(found)} başlık eşleşti)")
    save(rep)
    return n, len(found)


# ---------------------------------------------------------------- çıktı
def _paragraphs(text):
    out = []
    for p in re.split(r"\n\s*\n", text or ""):
        p = p.strip()
        if not p:
            continue
        items = [l[2:].strip() for l in p.splitlines() if l.startswith("- ")]
        out.append({"list": items} if items and len(items) == len(p.splitlines()) else {"p": p})
    return out


def build_html(rep, toc_pages=None):
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    secs = []
    for s in rep["sections"]:
        d = s.get("data")
        secs.append({**s, "paras": _paragraphs(s.get("text")), "chart_svg": svg.render(d.get("chart")) if d else "",
                     "page": (toc_pages or {}).get(s["id"], "")})
    return env.get_template("report.html").render(
        rep=rep, sections=secs, today=date.today().strftime("%d/%m/%Y"),
        logo=LOGO.resolve().as_uri() if LOGO.exists() else None)


def _print(html, out_pdf):
    tmp = out_pdf.with_suffix(".html")
    tmp.write_text(html, encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out_pdf.resolve()}", tmp.resolve().as_uri()],
                   check=True, capture_output=True)


def render(rep, who="editör"):
    """İki geçiş: önce sayfa yerlerini bul, sonra içindekiler sayfa numaralarıyla bas."""
    out = path(rep["id"]) / f"{_slug(rep['title'])}.pdf"
    _print(build_html(rep), out)
    pages = {}
    with fitz.open(out) as doc:
        for s in rep["sections"]:
            key = f"§{s['id']}§"  # şablonda başlığa gömülü görünmez işaret
            for i in range(2, doc.page_count):
                if doc[i].search_for(key):
                    pages[s["id"]] = i + 1
                    break
    _print(build_html(rep, pages), out)

    log(rep, who, f"PDF üretildi: {out.name}")
    save(rep)
    return out
