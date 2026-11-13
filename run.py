"""Bülten robotu - komut satırı.

  python run.py collect          # kaynakları tara (zamanlayıcıyla sık çalıştırılır)
  python run.py select           # haftanın adaylarını seç -> candidates.json
  python run.py write            # Claude ile Türkçe taslak -> drafts.json
  python run.py review           # rakam kontrolü + editör PDF'i (uyarılar sarı)
  python run.py render [tr en]   # onaylı taslaktan PDF (çeviri gerekirse yapılır)
  python run.py all              # collect + select + write + review
  python run.py panel            # editör paneli: http://127.0.0.1:8765
"""
import json
import sys
from datetime import date
from pathlib import Path

from bot import collect, select, verify, writer, render

CFG = json.loads(Path("config/sources.json").read_text(encoding="utf-8"))
ISSUE = date.today().strftime("%d.%m.%Y")
OUT = Path("data") / date.today().isoformat()


def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cmd_collect():
    print("Kaynaklar taranıyor...")
    collect.collect(CFG["sources"])


def cmd_select():
    print("Adaylar seçiliyor...")
    select.select(collect.load_raw(), CFG["issue"], OUT)


def cmd_write():
    print("Taslak yazılıyor...")
    writer.write_drafts(load("candidates.json"), CFG["issue"], OUT)


def cmd_review():
    drafts, cands = load("drafts.json"), load("candidates.json")
    if not drafts:
        sys.exit("drafts.json yok - önce 'write' adımı.")
    print("Rakam kontrolü:")
    for i, head, warns in verify.check(drafts, cands):
        print(f"  {'⚠' if warns else '✓'} {i:2}. {head[:70]}")
        for w in warns:
            print(f"        {w}")
    (OUT / "drafts.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  ->", render.render(drafts, ISSUE, "tr", OUT, review=True))


def cmd_render(langs):
    drafts = load("drafts.json")
    for lang in langs:
        d = drafts if lang == "tr" else (load(f"drafts.{lang}.json")
                                         or writer.translate(drafts, lang, OUT))
        for x, y in zip(d["items"], drafts["items"]):  # görseller dile bağlı değil
            for k in ("image", "image_caption", "photo", "videos"):
                x[k] = y.get(k)
        print("  ->", render.render(d, ISSUE, lang, OUT))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "collect": cmd_collect()
    elif cmd == "select": cmd_select()
    elif cmd == "write": cmd_write()
    elif cmd == "review": cmd_review()
    elif cmd == "render": cmd_render(sys.argv[2:] or ["tr"])
    elif cmd == "panel":
        from bot import panel
        panel.serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "all":
        cmd_collect(); cmd_select(); cmd_write()
        if load("drafts.json"):
            cmd_review()
    else:
        print(__doc__)
