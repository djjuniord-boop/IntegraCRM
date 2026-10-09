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
        import analyze
        a = analyze.run(str(d / "integra.pdf"), str(d / "crm.png"), tess)
        integra, crm, missing, uncertain = a["integra"], a["crm"], a["missing"], a["uncertain"]
        res["layout_ok"] = a["layout_ok"]
        res["warnings"] = a["warnings"]
        subj, body = mailer.compose(missing, uncertain)
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        res.update(integra=integra, crm=crm, missing=missing, uncertain=uncertain,
                   subject=subj, seconds=round(time.time() - t0, 1))
        import history
        import vault
        enc = vault.protect("abcd efgh ijkl mnop")
        res["vault_encrypted"] = enc.startswith(vault.PREFIX) or os.name != "nt"
        res["vault_error"] = getattr(vault, "LAST_ERROR", "")
        res["vault_roundtrip"] = vault.unprotect(enc) == "abcd efgh ijkl mnop"
        i = history.add_check("test.pdf", len(integra), len(crm), missing, uncertain)
        history.mark_sent(i, ["test@example.com"], missing)
        res["history_rows"] = len(history.read_all())
        res["reported"] = sorted(history.reported())
        subj2, body2 = mailer.compose(missing, uncertain, history.reported())
        res["mail_marks_reported"] = "zgłaszany już" in body2
        res["ok"] = (sorted(missing) == sorted(exp["missing"]) and not uncertain and a["layout_ok"]
                     and sorted(integra) == sorted(exp["integra"]) and not a["warnings"] and res["vault_encrypted"]
                     and res["vault_roundtrip"] and res["history_rows"] >= 1
                     and res["reported"] == sorted(missing) and res["mail_marks_reported"])
    except Exception:
        res["error"] = traceback.format_exc()
    (d / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(run(os.environ.get("INTEGRA_SELFTEST") or sys.argv[1]))
