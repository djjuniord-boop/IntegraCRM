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


# ---------- auto z szybkiego polecenia felg („audi a4 b9 2021 alu”) ----------
ALIASY = {"vw": "volkswagen", "mercedes": "mercedes-benz", "mb": "mercedes-benz", "merc": "mercedes-benz", "citroen": "citroen",
          "skoda": "skoda", "alfa": "alfa-romeo", "land": "land-rover", "range": "land-rover", "mini": "mini"}


def _k(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower().replace("ë", "e").replace("š", "s").replace("ö", "o"))


def slowa(txt):
    return [w for w in re.split(r"[\s,;/]+", (txt or "").lower()) if w]


def znajdz_marke(txt, marki):
    """Słowo z polecenia -> slug marki z listy wheel-size (z aliasami: vw, mercedes, alfa…)."""
    by = {_k(m["slug"]): m["slug"] for m in marki}
    by.update({_k(m["name"]): m["slug"] for m in marki})
    for i, w in enumerate(slowa(txt)):
        for kand in (ALIASY.get(w, w),):
            if _k(kand) in by and len(_k(kand)) >= 2:
                return by[_k(kand)], i
    return "", -1


def znajdz_model(txt, start, modele):
    """Słowa po marce -> slug modelu (najdłuższe dopasowanie: „a4 allroad”, „3 series”, „golf”)."""
    sl = slowa(txt)[start + 1:start + 4]
    by = {}
    for m in modele:
        for k in (_k(m["slug"]), _k(m["name"])):
            by.setdefault(k, m["slug"])
    for n in (3, 2, 1):
        if len(sl) >= n and _k("".join(sl[:n])) in by:
            return by[_k("".join(sl[:n]))], sl[:n]
    return "", []


def rok(txt):
    m = re.search(r"(?:^|\s)((?:19[89]|20[0-4])\d)(?=\s|$)", txt or "")
    return m.group(1) if m else ""


RZYMSKIE = {"1": "i", "2": "ii", "3": "iii", "4": "iv", "5": "v", "6": "vi", "7": "vii", "8": "viii", "9": "ix", "10": "x"}


def pasuje_gen(slowo, nazwa):
    """Czy słowo z polecenia wskazuje generację: „7” → „Mk7 (5G)” / „VII”, „b9” → „B9”, „mk7”, „5g”, „f30”."""
    w = _k(slowo)
    if not w or not nazwa:
        return False
    tokeny = [_k(t) for t in re.split(r"[\s()/,\-\[\]]+", str(nazwa)) if _k(t)]
    kand = {w}
    if w.isdigit():
        kand |= {"mk" + w, RZYMSKIE.get(w, w)}
    elif w.startswith("mk") and w[2:].isdigit():
        kand |= {w[2:], RZYMSKIE.get(w[2:], w)}
    return any(t in kand for t in tokeny)


def auto_wiele(dane, nazwa="", generacja="", wskazowki=()):
    """search/by_model bez wersji silnika (marka, model, rok albo generacja): wspólne dane i wszystkie rozmiary kół.
    wskazowki – słowa z polecenia („7” w „golf 7 2013”): gdy rok obejmuje dwie generacje, zostaje ta wskazana."""
    rek = [x for x in (dane or {}).get("data") or [] if isinstance(x, dict)]
    if generacja:
        rek = [x for x in rek if _k(generacja) in _k((x.get("generation") or {}).get("name"))] or rek
    for w in wskazowki or ():
        tylko = [x for x in rek if pasuje_gen(w, (x.get("generation") or {}).get("name"))]
        if tylko:
            rek = tylko
            break
    if not rek:
        return None
    wszystkie = [auto({"data": [x]}) for x in rek]
    wszystkie = [a for a in wszystkie if a]
    if not wszystkie:
        return None
    a = dict(wszystkie[0])
    widziane, kola = set(), []
    for b in wszystkie:
        for k in b["kola"]:
            klucz = (k["przod"]["felga"], k["przod"]["opona"], (k["tyl"] or {}).get("felga"))
            if klucz not in widziane:
                widziane.add(klucz)
                kola.append(k)
    kola.sort(key=lambda k: (not k["oe"], k["przod"]["sred"] or 0, k["przod"]["szer"] or 0))
    gens = []
    for x in rek:
        n = (x.get("generation") or {}).get("name") or ""
        if n and n not in gens:
            gens.append(n)
    g = " / ".join(gens[:3])   # rok na przełomie generacji (Golf 2013: Mk6 i Mk7) – widać obie
    a.update(kola=kola[:60], nazwa=(nazwa + (" " + g if g and _k(g) not in _k(nazwa) else "")).strip(),
             wersji=len(wszystkie), pcd=wszystkie[0]["pcd"], cb=wszystkie[0]["cb"])
    if len({b["pcd"] for b in wszystkie}) > 1:   # różne rozstawy w roczniku (rzadko) – bez rozstawu, ocena zawęzi
        a["pcd"] = ""
    return a
