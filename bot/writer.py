"""3. adım: Claude ile haber seçimi, Türkçe bülten metni ve çeviri.

ANTHROPIC_API_KEY tanımlıysa API çağrılır. Değilse istem (prompt) dosyaya yazılır;
çıktı elle ya da başka bir araçla data/<sayı>/drafts.json olarak konabilir.
"""
import json
import os
import time
from pathlib import Path

import anthropic

# Ekonomik kullanım (23.10.2026): haber çevirisi Haiku, bülten yazımı Sonnet. Aylık harcama
# data/cache/ai_usage.json'da tutulur; AI_MONTHLY_LIMIT_USD (varsayılan 5) aşılınca çağrı yapılmaz.
MODELS = {"cevir": ("claude-haiku-5-5", "medium"), "yaz": ("claude-sonnet-5-5", "medium")}
MODEL = MODELS["yaz"][0]
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
USAGE = Path("data/cache/ai_usage.json")


def _usage():
    try:
        return json.loads(USAGE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def month_cost():
    return round(_usage().get(time.strftime("%Y-%m"), {}).get("usd", 0.0), 2)


def monthly_limit():
    try:
        return float(os.environ.get("AI_MONTHLY_LIMIT_USD") or 5)
    except ValueError:
        return 5.0


def _record(model, usage):
    u, m = _usage(), time.strftime("%Y-%m")
    pin, pout = PRICES.get(model, PRICES["claude-opus-5-5"])
    inp = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * 1.25 \
        + (getattr(usage, "cache_read_input_tokens", 0) or 0) * 0.1
    cost = inp * pin / 1e6 + (usage.output_tokens or 0) * pout / 1e6
    row = u.setdefault(m, {"usd": 0.0, "calls": 0})
    row["usd"] += cost
    row["calls"] += 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(u), encoding="utf-8")

STYLE_GUIDE = """Sen T.C. Taşkent Büyükelçiliği Ticaret Müşavirliği'nin haftalık
"Ekonomi, Ticaret ve Yatırım ile İlgili Haber Başlıkları" bültenini hazırlayan editörsün.
Okuyucu: Özbekistan'da faaliyet gösteren veya göstermek isteyen Türk iş insanları.

Kurallar:
- Adaylar arasından Türk iş dünyası için en önemli haberleri seç: makro göstergeler,
  uluslararası kuruluş tahminleri, büyük yatırım/ihale projeleri, mevzuat değişiklikleri,
  vergi/gümrük düzenlemeleri, enerji, lojistik, Türkiye-Özbekistan ilişkileri.
  Asayiş, spor, kültür, turistik haberler alınmaz.
- Başlık: Bülten üslubunda, Her Kelimenin İlk Harfi Büyük, sonunda nokta.
  Örnek: "IMF, Özbekistan İçin 2026 Yılında %7,8 Büyüme Öngörüyor."
- Metin: resmi, nesnel, 2-4 paragraf. Kaynakta olmayan hiçbir bilgi, rakam veya yorum
  ekleme. Rakamları kaynaktaki gibi aktar (ondalık ayırıcı virgül: %7,8; para:
  "356 milyon ABD Doları"). Kurum adlarının Türkçe yerleşik karşılıklarını kullan.
- Her haberin kaynaklarını (site adı + URL) belirt.
- Türkiye ile ilgili haberleri önemli say, ama yalnızca gerçekten ilgiliyse.
"""

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "paragraphs": {"type": "array", "items": {"type": "string"}},
                    "category": {"type": "string", "enum": [
                        "makro", "ticaret", "yatırım", "enerji", "lojistik",
                        "mevzuat", "finans", "türkiye", "diğer"]},
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "sources": {"type": "array", "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "url": {"type": "string"}},
                        "required": ["name", "url"],
                        "additionalProperties": False}},
                },
                "required": ["headline", "paragraphs", "category", "candidate_ids", "sources"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def build_prompt(candidates, target_items):
    body = "\n\n".join(
        f"<aday id=\"{c['cid']}\" kaynak=\"{c['source']}\" dil=\"{c['lang']}\" "
        f"tarih=\"{c['published']}\" url=\"{c['url']}\">\n"
        f"BAŞLIK: {c['title']}\n{c['text']}\n</aday>"
        for c in candidates)
    return (f"Bu haftanın aday haberleri aşağıda. En önemli {target_items} haberi seç, "
            f"önem sırasına diz ve bülten metnini yaz. Aynı olayı anlatan adayları tek "
            f"haberde birleştir.\n\n{body}")


def _call(system, prompt, schema, kind="yaz"):
    if month_cost() >= monthly_limit():
        raise RuntimeError(f"Bu ayın Claude harcama sınırına ({monthly_limit():g} $) ulaşıldı; "
                           "haberler toplanmaya devam eder, çeviri ve yazım gelecek ay açılır.")
    model, effort = MODELS[kind]
    client = anthropic.Anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=32000,
        system=system,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    _record(model, msg.usage)
    if msg.stop_reason == "refusal":
        raise RuntimeError("Model isteği reddetti: %s" % msg.stop_details)
    return json.loads(next(b.text for b in msg.content if b.type == "text"))


def write_drafts(candidates, cfg, out_dir):
    prompt = build_prompt(candidates, cfg["target_items"])
    if not os.environ.get("ANTHROPIC_API_KEY"):
        (out_dir / "prompt.md").write_text(STYLE_GUIDE + "\n\n" + prompt, encoding="utf-8")
        print(f"  ANTHROPIC_API_KEY yok: istem {out_dir/'prompt.md'} dosyasına yazıldı.\n"
              f"  drafts.json elle eklendikten sonra 'python run.py render' çalıştırın.")
        return None
    drafts = _call(STYLE_GUIDE, prompt, DRAFT_SCHEMA)
    from bot import media
    media.attach(drafts, candidates, out_dir / "img")
    (out_dir / "drafts.json").write_text(
        json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(drafts['items'])} haber yazıldı -> drafts.json")
    return drafts


GLOSSARY = """Terim sözlüğü (her zaman bu karşılıkları kullan):
Yeni Taşkent = New Tashkent = Новый Ташкент = Yangi Toshkent
Ticaret Müşavirliği = Commercial Counsellor's Office = Торговое представительство
Dünya Bankası = World Bank = Всемирный банк = Jahon banki
"""


def translate(drafts, lang, out_dir):
    """Onaylanmış Türkçe metni hedef dile çevirir (aynı şema)."""
    names = {"en": "İngilizce", "ru": "Rusça", "uz": "Özbekçe (Latin alfabesi)"}
    system = (f"Türkçe ekonomi bülteni metinlerini {names[lang]} diline resmi ve doğru "
              f"biçimde çevir. Rakam, tarih ve kaynakları aynen koru; ekleme yapma.\n"
              + GLOSSARY)
    out = _call(system, json.dumps(drafts, ensure_ascii=False), DRAFT_SCHEMA)
    (out_dir / f"drafts.{lang}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def write_single(candidate):
    """Panelde aday havuzundan eklenen tek haber için Türkçe metin yazar."""
    prompt = build_prompt([candidate], 1) + "\nBu adayı mutlaka yaz (1 haber)."
    return _call(STYLE_GUIDE, prompt, DRAFT_SCHEMA)["items"][0]
