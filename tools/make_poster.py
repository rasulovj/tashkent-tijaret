"""Tanıtım afişi (TR ve UZ): static/guide/Tanitim-Afisi-<dil>.png / .pdf"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
from jinja2 import Environment, FileSystemLoader  # noqa: E402

from bot.render import CHROME  # noqa: E402

n_src = len(json.loads(Path("config/sources.json").read_text())["sources"])
TEXT = {
 "tr": {
  "office": "T.C. TAŞKENT BÜYÜKELÇİLİĞİ · TİCARET MÜŞAVİRLİĞİ",
  "h1a": "Akıllı Bülten ve", "h1b": "Yayın Platformu",
  "lead": "Haberi bulmaktan yayına kadar her adım tek panelde: otomatik, doğrulanmış, Türkçe ve Özbekçe.",
  "nums": [(n_src, "kaynak"), (4, "dil"), (30, "sektör"), (14, "bölge"), (15, "özel gün"), (6, "kurum")],
  "tiles": [
   ("📰", "Haberleri kendisi toplar", "Özbek ve Türk basını, Telegram kanalları, TRT Avaz — her saat. Türkçe arayın, her dilde sonuç gelsin."),
   ("✍️", "Haftalık bülten hazır", "Taslak, rakam doğrulama, fotoğraf ve QR'lı video bağlantıları; Türkçe, İngilizce, Özbekçe PDF."),
   ("🎬", "Video ve sunum", "Seslendirmeli video bülten ve toplantı için PowerPoint/PDF sunum — tek tıkla."),
   ("🎉", "Duyuru, etkinlik, kutlama", "Fuar, heyet, ihale ilanı; 29 Ekim, Navruz gibi özel günler için hazır kart ve A4 afiş."),
   ("📊", "Raporlar otomatik veriyle", "Sektör, ülke, yatırım ve şehir raporları; UN Comtrade, Dünya Bankası, İstatistik Ajansı."),
   ("🏛", "Temsilcilikler tek çatıda", "Büyükelçilik, Başkonsolosluk ve müşavirlikler bilgi gönderir; yayın kararı Ticaret Müşavirliği'nde."),
   ("✈️", "Tek tıkla yayın", "Telegram kanallarına PDF, video ve kart gönderimi; web önizleme bağlantısı."),
   ("📱", "Her yerden, iki dilde", "Telefon uyumlu panel, Türkçe / Özbekçe arayüz, görsel kılavuz."),
  ],
  "flow": [("Topla", "otomatik"), ("Düzenle", "editör"), ("Doğrula", "rakam kontrolü"), ("Onayla", "yönetim"), ("Yayınla", "PDF · video · Telegram")],
  "foot_name": "Taşkent Ticaret Müşavirliği", "foot_addr": "Akademik Yahya Gulyamov Ko'chasi No:87, Taşkent · +998 71 233 29 19",
  "foot_slogan": "Bülten, rapor ve duyurular<br>artık dakikalar içinde.",
 },
 "uz": {
  "office": "TURKIYA ELCHIXONASI · SAVDO MASLAHATCHILIGI",
  "h1a": "Aqlli byulleten va", "h1b": "nashr platformasi",
  "lead": "Yangilikni topishdan nashrgacha barcha bosqichlar bitta panelda: avtomatik, tekshirilgan, turk va o‘zbek tillarida.",
  "nums": [(n_src, "manba"), (4, "til"), (30, "soha"), (14, "hudud"), (15, "bayram"), (6, "muassasa")],
  "tiles": [
   ("📰", "Yangiliklarni o‘zi yig‘adi", "O‘zbek va turk matbuoti, Telegram kanallari, TRT Avaz — har soatda. Turkcha qidiring, natija barcha tillarda."),
   ("✍️", "Haftalik byulleten tayyor", "Qoralama, raqamlarni tekshirish, rasm va QR-kodli video; turk, ingliz va o‘zbek tilida PDF."),
   ("🎬", "Video va taqdimot", "Ovozli video byulleten hamda yig‘ilish uchun PowerPoint/PDF taqdimot — bir bosishda."),
   ("🎉", "E’lon, tadbir, bayram", "Ko‘rgazma, delegatsiya, tender; Navro‘z, 29-oktabr kabi kunlar uchun tayyor karta va afisha."),
   ("📊", "Avtomatik ma’lumotli hisobotlar", "Soha, mamlakat, investitsiya va hudud hisobotlari; UN Comtrade, Jahon banki, Statistika agentligi."),
   ("🏛", "Barcha vakolatxonalar bir joyda", "Elchixona, Bosh konsullik va maslahatchiliklar ma’lumot yuboradi; nashr qarori Savdo maslahatchiligida."),
   ("✈️", "Bir bosishda nashr", "Telegram kanallariga PDF, video va karta yuborish; veb-ko‘rinish havolasi."),
   ("📱", "Istalgan joydan, ikki tilda", "Telefonga mos panel, turk / o‘zbek interfeysi, ko‘rgazmali qo‘llanma."),
  ],
  "flow": [("Yig‘ish", "avtomatik"), ("Tahrir", "muharrir"), ("Tekshirish", "raqamlar"), ("Tasdiq", "rahbariyat"), ("Nashr", "PDF · video · Telegram")],
  "foot_name": "Toshkent Savdo maslahatchiligi", "foot_addr": "Akademik Yahyo G‘ulomov ko‘chasi, 87, Toshkent · +998 71 233 29 19",
  "foot_slogan": "Byulleten, hisobot va e’lonlar<br>endi bir necha daqiqada.",
 },
}
out = Path("static/guide")
env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
for lang, T in TEXT.items():
    html = Path(f"build/tanitim-{lang}.html")
    html.parent.mkdir(exist_ok=True)
    html.write_text(env.get_template("tanitim_afisi.html").render(T=T), encoding="utf-8")
    png = (out / f"Tanitim-Afisi-{lang}.png").resolve()
    pdf = (out / f"Tanitim-Afisi-{lang}.pdf").resolve()
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1240,1754",
                    f"--screenshot={png}", html.resolve().as_uri()], check=True, capture_output=True)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.resolve().as_uri()], check=True, capture_output=True)
    print(png.name, pdf.name)
