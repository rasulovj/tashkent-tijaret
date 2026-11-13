"""Videolu bülten: bülten taslağından seslendirmeli MP4 üretir.

Slaytlar (1920x1080) HTML şablondan Chrome ile görüntüye çevrilir, macOS `say` (Türkçe ses: Yelda)
ile seslendirilir, ffmpeg ile birleştirilir. Çıktı: data/<sayı>/video/<ad>.mp4
"""
import wave
import re
import shutil
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from jinja2 import Environment, FileSystemLoader

from bot import render

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICES = {"tr": "Yelda", "en": "Samantha", "ru": "Milena", "uz": None}  # macOS'ta Özbekçe ses yok
NARR = {
    "tr": {"cover": "Taşkent Ticaret Müşavirliği. {issue} tarihli ekonomi, ticaret ve yatırım haberleri.",
           "rates": "Özbekistan Merkez Bankası resmî kurlarına göre bir ABD doları {usd} som, bir Türk lirası {try_} som.",
           "end": "Bültenin tamamına ve kaynaklara PDF bültenimizden ulaşabilirsiniz. İyi çalışmalar."},
    "en": {"cover": "Commercial Counsellor's Office in Tashkent. Economic news of {issue}.",
           "rates": "According to the Central Bank of Uzbekistan, one US dollar equals {usd} soums and one Turkish lira {try_} soums.",
           "end": "The full bulletin and sources are available in our PDF edition."},
    "ru": {"cover": "Торговое представительство в Ташкенте. Экономические новости за {issue}.",
           "rates": "По данным Центрального банка, один доллар США стоит {usd} сумов, турецкая лира {try_} сумов.",
           "end": "Полная версия бюллетеня доступна в формате PDF."},
    "uz": {"cover": "Toshkentdagi Savdo maslahatchiligi. {issue} sanasidagi iqtisodiy yangiliklar.",
           "rates": "Markaziy bank rasmiy kursi bo‘yicha bir AQSh dollari {usd} so‘m, bir turk lirasi {try_} so‘m.",
           "end": "Byulletenning to‘liq matni va manbalar PDF nashrimizda."},
}


def _say_text(text, lang):
    if lang == "tr":
        text = re.sub(r"%\s?(\d+(?:,\d+)?)", r"yüzde \1", text)
        text = text.replace("ABD Doları", "ABD doları").replace("milyar som", "milyar som")
    return text


def summary(it, limit=330):
    p = (it.get("paragraphs") or [""])[0]
    out = ""
    for sent in re.split(r"(?<=[.!?])\s+", p):
        if len(out) + len(sent) > limit and out:
            break
        out += (" " if out else "") + sent
    return out


def _duration(wav):
    with wave.open(str(wav)) as a:
        return a.getnframes() / float(a.getframerate())


def make_slides(drafts, issue, lang, out_dir, work, progress=lambda *a: None):
    """Bülten taslağından slaytları (HTML + 1920x1080 PNG) üretir; video ve sunum ortak kullanır."""
    L = render.LABELS[lang]
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    tpl = env.get_template("video_slide.html")
    img_dir = (Path(out_dir) / "img").resolve()
    items = drafts["items"]
    rates, svgs = render.indicators(L)
    rate = {r["ccy"]: r["rate_fmt"] for r in rates}

    slides = [{"kind": "cover", "say": NARR[lang]["cover"].format(issue=issue), "foot": f"{len(items)}"}]
    for n, it in enumerate(items, 1):
        photo = it.get("photo")
        slides.append({"kind": "news", "it": it, "n": n, "summary": summary(it), "foot": ", ".join(s["name"] for s in it["sources"]),
                       "photo": (img_dir / photo["file"]).as_uri() if photo and photo.get("show") else None,
                       "say": f"{it['headline']} {summary(it)}"})
    if rates:
        slides.append({"kind": "rates", "rates": rates, "chart": svgs[0] if svgs else "", "foot": rates[0]["date"],
                       "say": NARR[lang]["rates"].format(usd=rate.get("USD", ""), try_=rate.get("TRY", ""))})
    slides.append({"kind": "end", "say": NARR[lang]["end"], "foot": issue})

    out = []
    for i, sl in enumerate(slides, 1):
        progress(i, len(slides), f"Slayt {i}/{len(slides)} hazırlanıyor")
        html = work / f"s{i:02d}.html"
        html.write_text(tpl.render(L={**L, "end_note": NARR[lang]["end"]}, issue=issue, items=items, total=len(items),
                                   qr=render.qr_svg, **sl), encoding="utf-8")
        png = work / f"s{i:02d}.png"
        subprocess.run([render.CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--window-size=1920,1080", f"--screenshot={png}", html.as_uri()],
                       check=True, capture_output=True)
        out.append({"html": html, "png": png, "say": sl["say"]})
    return out


def build(drafts, issue, lang, out_dir, voice=True, seconds=7, progress=lambda *a: None, voice_id=None):
    from bot import tts
    L = render.LABELS[lang]
    voice_id = (voice_id or tts.default_voice(lang)) if voice else None
    voice = bool(voice_id)
    work = (Path(out_dir) / "video" / f"work-{lang}").resolve()
    slides = make_slides(drafts, issue, lang, out_dir, work, progress)
    segs = []
    total = len(slides)
    for i, sl in enumerate(slides, 1):
        progress(i, total, f"Slayt {i}/{total} seslendiriliyor")
        png = sl["png"]
        seg = work / f"s{i:02d}.mp4"
        if voice:
            aiff = work / f"s{i:02d}.wav"
            tts.synthesize(_say_text(sl["say"], lang), voice_id, aiff)
            dur = _duration(aiff) + 1.2
            audio = ["-i", str(aiff)]
        else:
            dur = seconds
            audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
        subprocess.run([FFMPEG, "-y", "-loop", "1", "-framerate", "25", "-i", str(png), *audio,
                        "-t", f"{dur:.2f}", "-vf", "fade=t=in:st=0:d=0.4,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-r", "25",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1", "-shortest", str(seg)],
                       check=True, capture_output=True)
        segs.append(seg)
    progress(total, total, "Video birleştiriliyor")
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segs))
    out = (Path(out_dir) / "video" / f"{L['doc_title']}-{issue}-{lang}.mp4").resolve()
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    "-movflags", "+faststart", str(out)], check=True, capture_output=True, cwd=work)
    thumbs = Path(out_dir) / "video" / "slides"
    shutil.rmtree(thumbs, ignore_errors=True)
    thumbs.mkdir()
    for sl in slides:
        shutil.copy(sl["png"], thumbs / sl["png"].name)
    return out


def build_deck(drafts, issue, lang, out_dir, progress=lambda *a: None):
    """Aynı slaytlardan sunum bülteni: 16:9 PDF (seçilebilir metin) + PowerPoint (konuşmacı notlarıyla)."""
    import fitz
    from pptx import Presentation
    from pptx.util import Emu

    L = render.LABELS[lang]
    deck_dir = (Path(out_dir) / "sunum").resolve()
    work = deck_dir / f"work-{lang}"
    slides = make_slides(drafts, issue, lang, out_dir, work, progress)
    stem = f"{L['doc_title']}-{issue}-{lang}-sunum"

    progress(len(slides), len(slides), "PDF sunum hazırlanıyor")
    pdf = fitz.open()
    for sl in slides:
        one = sl["html"].with_suffix(".pdf")
        subprocess.run([render.CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={one}", sl["html"].as_uri()], check=True, capture_output=True)
        with fitz.open(one) as d:
            pdf.insert_pdf(d, from_page=0, to_page=0)
    pdf_path = deck_dir / f"{stem}.pdf"
    pdf.save(pdf_path, garbage=3, deflate=True)
    render.compress_pdf(pdf_path)

    progress(len(slides), len(slides), "PowerPoint hazırlanıyor")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 16:9
    blank = prs.slide_layouts[6]
    for sl in slides:
        s = prs.slides.add_slide(blank)
        s.shapes.add_picture(str(sl["png"]), 0, 0, prs.slide_width, prs.slide_height)
        s.notes_slide.notes_text_frame.text = sl["say"]  # konuşmacı notu = seslendirme metni
    pptx_path = deck_dir / f"{stem}.pptx"
    prs.save(pptx_path)
    shutil.rmtree(work, ignore_errors=True)
    return pdf_path, pptx_path
