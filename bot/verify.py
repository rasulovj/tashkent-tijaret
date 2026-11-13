"""4. adım: Rakam doğrulama. Taslaktaki her sayının kaynak metinde geçip geçmediğini
kontrol eder; geçmeyenler editöre uyarı olarak gösterilir (uydurmaya karşı güvence).
"""
import re

NUM = re.compile(r"\d+(?:[.,]\d+)*")


def variants(n):
    """'7,8' -> {'7,8','7.8'}; '1.200' -> {'1.200','1,200','1200'}"""
    swapped = n.translate(str.maketrans(",.", ".,"))  # TR '1.072,7' <-> EN '1,072.7'
    out = {n, swapped, n.replace(",", "."), n.replace(".", ","), re.sub(r"[.,]", "", n)}
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", n):  # TR binlik ayırıcı
        out.add(n.replace(".", " "))
    return out


def check(drafts, candidates):
    by_id = {c["cid"]: c for c in candidates}
    report = []
    for i, item in enumerate(drafts["items"], 1):
        src = " ".join(by_id[c]["title"] + " " + by_id[c]["text"]
                       for c in item["candidate_ids"] if c in by_id) + " " + item.get("source_text", "")
        src_norm = re.sub(r"(?<=\d)[\s  ](?=\d{3})", "", src)
        text = item["headline"] + " " + " ".join(item["paragraphs"])
        missing = []
        for n in sorted(set(NUM.findall(text))):
            if len(re.sub(r"\D", "", n)) < 2 and "," not in n:
                continue  # tek haneli sayılar (ör. "beş tesis") atlanır
            if not any(v in src or v in src_norm for v in variants(n)):
                missing.append(n)
        item["warnings"] = [f"'{m}' kaynak metinde bulunamadı" for m in missing]
        report.append((i, item["headline"], item["warnings"]))
    return report
