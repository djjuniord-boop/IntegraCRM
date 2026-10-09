"""Test całej ścieżki (PDF → OCR wycinka → porównanie → mail) bez okna.

Uruchamiany w GitHub Actions na gotowym IntegraCRM.exe:  INTEGRA_SELFTEST=<folder>
W folderze muszą być: integra.pdf, crm.png, expected.json  {"missing": [...]}.
Wynik zapisuje do <folder>/result.json, kod wyjścia 0 = OK.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path


def run(folder: str) -> int:
    d = Path(folder)
    res = {"ok": False}
    try:
        import extract
        import mailer
        import paths
        import plates

        t0 = time.time()
        tess = paths.find_tesseract("")
        res["tesseract"] = tess
        res["root"] = str(paths.ROOT)
        integra = plates.extract_plates(extract.text_from_pdf(str(d / "integra.pdf"), tess))
        texts = extract.ocr_variants(str(d / "crm.png"), tess)
        crm = []
        for t in texts:
            for p in plates.extract_crm_plates(t):
                if p not in crm:
                    crm.append(p)
        missing, uncertain = plates.compare(integra, crm)
        subj, body = mailer.compose(missing, uncertain)
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        res.update(integra=integra, crm=crm, missing=missing, uncertain=uncertain,
                   subject=subj, seconds=round(time.time() - t0, 1))
        res["ok"] = sorted(missing) == sorted(exp["missing"]) and not uncertain
    except Exception:
        res["error"] = traceback.format_exc()
    (d / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(run(os.environ.get("INTEGRA_SELFTEST") or sys.argv[1]))
