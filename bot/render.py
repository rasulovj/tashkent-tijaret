"""5. adım: HTML şablonu + Chrome (headless) ile PDF üretimi, her dil için."""
import io
import os
import subprocess
import time
from pathlib import Path

import qrcode
import qrcode.image.svg
from jinja2 import Environment, FileSystemLoader

from bot import charts

CHROME = os.environ.get("CHROME_PATH") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

LABELS = {
    "tr": {
        "doc_title": "Ekonomi Haberleri",
        "office_1": "T.C. TAŞKENT BÜYÜKELÇİLİĞİ", "office_2": "TİCARET MÜŞAVİRLİĞİ",
        "office_short": "T.C. Taşkent Büyükelçiliği Ticaret Müşavirliği",
        "address_html": "<b>Adres</b>: Akademik Yahya Gulyamov<br>Ko’chasi No:87 Taşkent/Özbekistan<br><b>Tel</b>: +998 71 233 29 19",
        "headlines_title": "Ekonomi, Ticaret ve Yatırım ile İlgili Haber Başlıkları",
        "indicators_title": "Haftanın Göstergeleri – Resmî Döviz Kurları (UZS)",
        "rates_source": "Kaynak: Özbekistan Cumhuriyeti Merkez Bankası",
        "chart_usd": "USD/UZS – son 30 gün", "chart_try": "TRY/UZS – son 30 gün",
        "note": "NOT: İşbu haber metinleri ve diğer çalışmalar tarafımızca yapılan gayri resmi çeviri olup Özbekistan’da faaliyet gösteren iş insanlarımızı bilgilendirme amacıyla hazırlanmaktadır.",
        "page": "", "photo": "Görsel", "video": "Video",
    },
    "en": {
        "doc_title": "Economic News",
        "office_1": "EMBASSY OF THE REPUBLIC OF TÜRKİYE IN TASHKENT", "office_2": "COMMERCIAL COUNSELLOR'S OFFICE",
        "office_short": "Commercial Counsellor's Office, Embassy of Türkiye in Tashkent",
        "address_html": "<b>Address</b>: Akademik Yahya Gulyamov<br>Ko’chasi No:87 Tashkent/Uzbekistan<br><b>Tel</b>: +998 71 233 29 19",
        "headlines_title": "Headlines on Economy, Trade and Investment",
        "indicators_title": "Indicators of the Week – Official Exchange Rates (UZS)",
        "rates_source": "Source: Central Bank of the Republic of Uzbekistan",
        "chart_usd": "USD/UZS – last 30 days", "chart_try": "TRY/UZS – last 30 days",
        "note": "NOTE: These news texts are unofficial translations prepared by our office to inform business people operating in Uzbekistan.",
        "page": "", "photo": "Photo", "video": "Video",
    },
    "ru": {
        "doc_title": "Экономические новости",
        "office_1": "ПОСОЛЬСТВО ТУРЕЦКОЙ РЕСПУБЛИКИ В ТАШКЕНТЕ", "office_2": "ТОРГОВОЕ ПРЕДСТАВИТЕЛЬСТВО",
        "office_short": "Торговое представительство Посольства Турции в Ташкенте",
        "address_html": "<b>Адрес</b>: ул. Академика Яхьи Гулямова, 87<br>Ташкент/Узбекистан<br><b>Тел</b>: +998 71 233 29 19",
        "headlines_title": "Заголовки новостей экономики, торговли и инвестиций",
        "indicators_title": "Показатели недели – официальные курсы валют (UZS)",
        "rates_source": "Источник: Центральный банк Республики Узбекистан",
        "chart_usd": "USD/UZS – последние 30 дней", "chart_try": "TRY/UZS – последние 30 дней",
        "note": "ПРИМЕЧАНИЕ: Данные тексты являются неофициальным переводом и подготовлены для информирования предпринимателей, работающих в Узбекистане.",
        "page": "", "photo": "Фото", "video": "Видео",
    },
    "uz": {
        "doc_title": "Iqtisodiy yangiliklar",
        "office_1": "TURKIYA RESPUBLIKASINING TOSHKENTDAGI ELCHIXONASI", "office_2": "SAVDO MASLAHATCHILIGI",
        "office_short": "Turkiya Elchixonasi Savdo maslahatchiligi, Toshkent",
        "address_html": "<b>Manzil</b>: Akademik Yahyo G‘ulomov<br>ko‘chasi, 87, Toshkent/O‘zbekiston<br><b>Tel</b>: +998 71 233 29 19",
        "headlines_title": "Iqtisodiyot, savdo va investitsiyalarga oid yangiliklar sarlavhalari",
        "indicators_title": "Haftaning ko‘rsatkichlari – Rasmiy valyuta kurslari (UZS)",
        "rates_source": "Manba: O‘zbekiston Respublikasi Markaziy banki",
        "chart_usd": "USD/UZS – so‘nggi 30 kun", "chart_try": "TRY/UZS – so‘nggi 30 kun",
        "note": "IZOH: Ushbu yangiliklar matnlari tomonimizdan tayyorlangan norasmiy tarjima bo‘lib, O‘zbekistonda faoliyat yuritayotgan tadbirkorlarimizni xabardor qilish maqsadida tayyorlanadi.",
        "page": "", "photo": "Rasm", "video": "Video",
    },
}


def fmt(v, dec):
    return f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")


_CACHE = {}


def indicators(L):
    """Kur verisi + grafikler; panelde sık önizleme için 30 dk önbelleklenir."""
    key = L["chart_usd"]
    if key in _CACHE and time.time() - _CACHE[key][0] < 1800:
        return _CACHE[key][1]
    try:
        rates = charts.today_rates()
        usd = charts.history("USD")
        tr = charts.history("TRY")
    except Exception as e:  # gösterge alınamazsa bülten yine çıkar
        print(f"  ! kur verisi alınamadı: {e}")
        return [], []
    for r in rates:
        dec = 2 if r["rate"] < 1000 else 0
        r["rate_fmt"] = fmt(r["rate"], dec)
        r["diff_fmt"] = fmt(abs(r["diff"]), 2)
    order = {"USD": 0, "EUR": 1, "RUB": 2, "TRY": 3}
    rates.sort(key=lambda r: order[r["ccy"]])
    result = (rates, [charts.line_svg(usd, L["chart_usd"]),
                      charts.line_svg(tr, L["chart_try"], color="#C0392B", decimals=2)])
    _CACHE[key] = (time.time(), result)
    return result


def compress_pdf(path):
    """Gömülü görselleri ~130 dpi JPEG'e indirir (ör. 11 MB -> 0,7 MB); metin ve vektörler aynen kalır."""
    import fitz
    path = Path(path)
    tmp = path.with_suffix(".tmp.pdf")
    with fitz.open(path) as d:
        if not any(pg.get_images() for pg in d):
            return path  # fotoğraf yoksa dokunma (renk geçişleri bozulmasın)
        d.rewrite_images(dpi_threshold=160, dpi_target=130, quality=72, lossy=True, lossless=True,
                         bitonal=False, color=True, gray=True)
        d.save(tmp, garbage=4, deflate=True)
    tmp.replace(path)
    return path


def qr_svg(url):
    """Video bağlantısı için PDF'e gömülü, keskin QR kodu."""
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode().split("?>", 1)[-1]


def build_html(drafts, issue_date, lang, review=False):
    L = LABELS[lang]
    rates, svgs = indicators(L)
    items = drafts["items"]
    for n, it in enumerate(items, 1):
        it["n"] = n
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    return env.get_template("bulten.html").render(
        L=L, lang=lang, issue_date=issue_date, items=items, rates=rates,
        charts=svgs, review=review, qr=qr_svg)


def render(drafts, issue_date, lang, out_dir, review=False):
    html = build_html(drafts, issue_date, lang, review)
    stem = f"{LABELS[lang]['doc_title']}-{issue_date}" + ("-EDITOR" if review else "")
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = out_dir / f"{stem}.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path.resolve()}", html_path.resolve().as_uri()],
                   check=True, capture_output=True)
    compress_pdf(pdf_path)
    return pdf_path
