"""Dobór felg i opon po aucie – dane wheel-size.com (przez funkcję serwera „wheel-size”, klucz zostaje w Supabase).

Moduł bez okna i bez sieci: zamienia odpowiedzi API na proste słowniki dla Panelu i ocenia, czy felga z xPartner pasuje
do wybranego auta (rozstaw śrub, otwór centralny, średnica, ET). Decyzje właściciela 2026-11-27: ET ±5 mm = pasuje,
do ±15 mm = ostrzeżenie (Ustawienia → Felgi), dobór w felgach i w ofercie opon, auto na PDF z przełącznikiem.
"""
import re


def _n(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _t(v):
    return "" if v is None else str(v).strip()


def lista(dane):
    """makes / models / years -> [{slug, name}] (rok jako tekst)."""
    out = []
    for x in (dane or {}).get("data") or []:
        if isinstance(x, dict) and x.get("slug") not in (None, ""):
            out.append({"slug": str(x["slug"])[:60], "name": _t(x.get("name") or x["slug"])[:80]})
    return out


def moc(p):
    """{"kW": 110, "PS": 150, "hp": 148} -> „110 kW (150 KM)”."""
    if not isinstance(p, dict):
        return ""
    kw, ps = _n(p.get("kW") or p.get("kw")), _n(p.get("PS") or p.get("ps"))
    if kw and ps:
        return "%d kW (%d KM)" % (round(kw), round(ps))
    return "%d kW" % round(kw) if kw else ("%d KM" % round(ps) if ps else "")


def wersje(dane):
    """modifications -> [{slug, name}] z czytelną nazwą: silnik, moc, generacja, lata."""
    out = []
    for x in (dane or {}).get("data") or []:
        if not isinstance(x, dict) or not x.get("slug"):
            continue
        e = x.get("engine") or {}
        g = x.get("generation") or {}
        lata = "%s–%s" % (x.get("start_year") or g.get("start") or "", x.get("end_year") or g.get("end") or "")
        czesci = [_t(x.get("name") or x.get("trim")), moc(e.get("power")), _t(e.get("fuel"))]
        nazwa = " ".join(c for c in czesci[:2] if c) or _t(e.get("capacity")) or "wersja"
        if czesci[2]:
            nazwa += " · " + czesci[2]
        if g.get("name"):
            nazwa += " · " + _t(g["name"])
        if lata.strip("–"):
            nazwa += " (%s)" % lata
        out.append({"slug": str(x["slug"])[:40], "name": nazwa[:120]})
    return out


def _kolo(k):
    if not isinstance(k, dict):
        return None
    sred, szer, et = _n(k.get("rim_diameter")), _n(k.get("rim_width")), _n(k.get("rim_offset"))
    opona = _t(k.get("tire_full") or k.get("tire"))
    li, si = _t(k.get("load_index")), _t(k.get("speed_index"))
    cis = k.get("tire_pressure") if isinstance(k.get("tire_pressure"), dict) else {}
    return {"sred": sred, "szer": szer, "et": et, "felga": _t(k.get("rim")), "opona": opona,
            "opona_txt": (opona + (" " + li + si if li or si else "")).strip(), "cisn": _n(cis.get("bar"))}


def rozmiar_opony(txt):
    """„225/40ZR18” -> „225/40 R18” (do szybkiego polecenia ofert opon)."""
    m = re.search(r"(\d{3})\s*/\s*(\d{2})\s*Z?R\s*F?\s*(\d{2}(?:\.5)?)(C?)", (txt or "").upper())
    return "%s/%s R%s%s" % m.groups() if m else ""


def auto(dane, slug=""):
    """search/by_model -> dane auta: nazwa, rozstaw, otwór, mocowanie, moment, lista kół (fabryczne i zamienniki)."""
    rek = [x for x in (dane or {}).get("data") or [] if isinstance(x, dict)]
    if slug:
        rek = [x for x in rek if x.get("slug") == slug] or rek
    if not rek:
        return None
    x = rek[0]
    t = x.get("technical") or {}
    mk, md, g, e = x.get("make") or {}, x.get("model") or {}, x.get("generation") or {}, x.get("engine") or {}
    mocow = t.get("wheel_fasteners") or {}
    kola = []
    for w in x.get("wheels") or []:
        if not isinstance(w, dict):
            continue
        p = _kolo(w.get("front"))
        if not p or not p["sred"]:
            continue
        r = None if w.get("showing_fp_only") else _kolo(w.get("rear"))
        if r and (not r["sred"] or (r["opona"] == p["opona"] and r["felga"] == p["felga"])):
            r = None
        kola.append({"oe": bool(w.get("is_stock")), "przod": p, "tyl": r, "zima": bool(w.get("is_recommended_for_winter")),
                     "rf": bool(w.get("is_runflat_tires")), "xl": bool(w.get("is_extra_load_tires")),
                     "stal": bool(w.get("is_pressed_steel_rims"))})
    kola.sort(key=lambda k: (not k["oe"], k["przod"]["sred"] or 0, k["przod"]["szer"] or 0))
    nazwa = " ".join(c for c in (_t(mk.get("name")), _t(md.get("name")), _t(g.get("name")), _t(x.get("name") or x.get("trim")),
                                 moc(e.get("power"))) if c)
    pcd = _t(t.get("bolt_pattern")).lower().replace(" ", "")
    return {"nazwa": nazwa[:160], "pcd": "" if pcd in ("n/a", "") else pcd, "cb": _n(t.get("centre_bore")),
            "gwint": _t(mocow.get("thread_size")), "mocowanie": MOCOWANIE.get(_t(mocow.get("type")).lower(), _t(mocow.get("type"))),
            "moment": _t(t.get("wheel_tightening_torque")), "lata": "%s–%s" % (x.get("start_year") or "", x.get("end_year") or ""),
            "kola": kola[:40]}


MOCOWANIE = {"lug bolts": "śruby", "bolts": "śruby", "bolt": "śruby", "lug nuts": "nakrętki", "nuts": "nakrętki", "nut": "nakrętki",
             "center lock": "centralna nakrętka"}


def _pcd(v):
    m = re.match(r"(\d)\s*x\s*(\d{2,3}(?:[.,]\d+)?)", _t(v).lower())
    return "%sx%g" % (m.group(1), float(m.group(2).replace(",", "."))) if m else ""


def ocena(f, a, et_ok=5, et_ostrz=15):
    """Czy felga pasuje do auta: (klasa, tekst). Klasy: ok (fabrycznie), zm (zamiennik / z pierścieniem), uw (sprawdź), nie."""
    if not a:
        return "", ""
    if a.get("pcd") and _pcd(f.get("pcd")) and _pcd(f.get("pcd")) != _pcd(a["pcd"]):
        return "nie", "inny rozstaw śrub (auto: %s)" % a["pcd"]
    otw, cb = _n(f.get("otwor")), _n(a.get("cb"))
    if otw and cb and otw < cb - 0.05:
        return "nie", "otwór %g mm – za mały (auto %g)" % (otw, cb)
    pierscien = " · pierścień %g→%g" % (otw, cb) if otw and cb and otw > cb + 0.05 else ""
    sred, szer, et = _n(f.get("sred")), _n(f.get("szer")), _n(f.get("et"))
    kola = [k["przod"] for k in a.get("kola") or [] if k["przod"]["sred"] == sred] if sred else []
    if not kola:
        return "uw", ("średnicy R%g nie ma w danych auta" % sred if sred else "brak średnicy w danych felgi") + pierscien
    if et is None:
        return "uw", "brak ET w danych felgi" + pierscien
    oe = [k for k in a["kola"] if k["oe"] and k["przod"]["sred"] == sred]
    best = min(kola, key=lambda k: (abs((k["et"] if k["et"] is not None else 999) - et), abs((k["szer"] or 0) - (szer or 0))))
    d = abs((best["et"] if best["et"] is not None else 999) - et)
    szer_ok = not szer or not best["szer"] or abs(best["szer"] - szer) <= 1.0
    if d <= et_ok and szer_ok:
        fabr = any(k["przod"] is best for k in oe) and d <= 1 and abs((best["szer"] or 0) - (szer or 0)) <= 0.5 and not pierscien
        return ("ok", "pasuje fabrycznie") if fabr else ("zm", "pasuje (jak %s)" % (best["felga"] or "zamiennik") + pierscien)
    if d <= et_ostrz and (szer_ok or not szer):
        return "uw", "ET %g – o %g mm inne niż %s, sprawdź" % (et, d, best["felga"] or "fabryczne") + pierscien
    if not szer_ok and d <= et_ostrz:
        return "uw", "szerokość %g\" inna niż %s, sprawdź" % (szer, best["felga"]) + pierscien
    return "nie", "ET %g – za daleko od %s" % (et, best["felga"] or "fabrycznego")
