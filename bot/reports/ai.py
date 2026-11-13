"""Claude ile rapor bölümü güncelleme: geçen yılın metni + güncel veri tablosu -> güncel metin."""
import json

from bot import writer

SYSTEM = """Sen T.C. Taşkent Ticaret Müşavirliği adına resmî pazar/ülke raporu yazan bir uzmansın.
Görev: verilen bölümün geçen yılki metnini güncelle.
- Güncel veri tablosu varsa metindeki rakamları ve yılları tablodaki değerlerle değiştir.
- Tabloda karşılığı olmayan rakam veya bilgiyi değiştirme; güncelliği şüpheli ifadeleri [KONTROL] ile işaretle.
- Yeni bilgi uydurma. Resmî, nesnel Türkçe kullan. Paragrafları boş satırla ayır, madde işareti için "- " kullan.
- notes alanında editöre neyi değiştirdiğini ve neyi kontrol etmesi gerektiğini kısaca yaz."""

SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}, "notes": {"type": "string"}},
          "required": ["text", "notes"], "additionalProperties": False}


def update_section(rep, sec):
    data = sec.get("data") or {}
    table = "\n".join(" | ".join(map(str, r)) for r in [data.get("columns", [])] + data.get("rows", []))
    prompt = (f"Rapor: {rep['title']}\nBölüm: {sec['id']} {sec['title']}\n\n"
              f"<gecen_yil_metni>\n{sec.get('text') or '(boş)'}\n</gecen_yil_metni>\n\n"
              f"<guncel_veri kaynak=\"{data.get('note', '')}\">\n{table or '(veri tablosu yok)'}\n</guncel_veri>")
    out = writer._call(SYSTEM, prompt, SCHEMA)
    sec["text"] = out["text"]
    sec["ai_notes"] = out["notes"]
    sec["status"] = "taslak"
    return json.dumps(out, ensure_ascii=False)
