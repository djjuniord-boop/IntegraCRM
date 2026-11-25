/* DEPOZYT – spis opon w przechowalni na telefonie. Wyszukiwanie = port app/depozyt/szukaj.py
   (zmiana w Panelu = ta sama zmiana tutaj; pilnuje test mobile/test/zgodnosc_depozyt.py). */
(function (root) {
  "use strict";
  const D = {};
  const MYLONE = { O: "0", Q: "0", D: "0", I: "1", L: "1", J: "1", Z: "2", S: "5", B: "8", G: "6", T: "7" };
  const DOKLADNE = 100, FRAGMENT = 90, INNE_POLE = 85, LITEROWKA = 60;

  D.norm = (s) => String(s ?? "").toUpperCase().replace(/[\s\-_.]/g, "");
  D.kanon = (s) => [...D.norm(s)].map((c) => MYLONE[c] || c).join("");   // numer bez znaków mylonych (O→0, I→1 …)

  D.lev = function (a, b, limit) {   // odległość edycyjna z przerwaniem (powyżej limitu = limit+1)
    a = [...a]; b = [...b];
    if (Math.abs(a.length - b.length) > limit) return limit + 1;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i].concat(new Array(b.length).fill(0));
      let best = i;
      for (let j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0));
        best = Math.min(best, cur[j]);
      }
      if (best > limit) return limit + 1;
      prev = cur;
    }
    return prev[prev.length - 1];
  };
  D._lev_fragment = function (q, t, limit) {   // wpisano część numeru
    const Q = [...q], T = [...t];
    if (T.length <= Q.length) return D.lev(q, t, limit);
    let best = limit + 1;
    for (let i = 0; i <= T.length - Q.length; i++) {
      best = Math.min(best, D.lev(Q.join(""), T.slice(i, i + Q.length).join(""), limit));
      if (best === 0) break;
    }
    return best;
  };
  D.numery = (poz) => [poz.nr || ""].concat(String(poz.uwagi ?? "").toUpperCase().match(/[A-Z0-9]{5,9}/g) || []);

  D.ocena = function (poz, zapytanie) {   // [punkty, czy_przyblizone]; 0 = brak
    const q_raw = String(zapytanie ?? "").trim().toUpperCase(), qn = D.norm(q_raw), qc = D.kanon(q_raw);
    if (!qn) return [0, false];
    let best = 0, przybl = false;
    for (const p of D.numery(poz)) {
      const pn = D.norm(p), pc = D.kanon(p);
      if (!pn) continue;
      let pkt, fz;
      if (pn === qn) [pkt, fz] = [DOKLADNE, false];
      else if (pn.includes(qn)) [pkt, fz] = [FRAGMENT, false];
      else if (pc === qc) [pkt, fz] = [80, true];
      else if (pc.includes(qc)) [pkt, fz] = [70, true];
      else if ([...qn].length >= 5 && /\p{Nd}/u.test(qn) && /\p{L}/u.test(qn)) {
        const d = D._lev_fragment(qc, pc, [...qn].length >= 7 ? 2 : 1);
        [pkt, fz] = d <= 2 ? [LITEROWKA - d * 10, true] : [0, false];
      } else [pkt, fz] = [0, false];
      if (pkt > best) { best = pkt; przybl = fz; }
    }
    if (best < FRAGMENT) {
      const tekst = ["lok", "marka", "marka2", "uwagi", "komentarz", "rodzaj"].map((k) => String(poz[k] ?? "")).join(" ").toUpperCase();
      if (tekst.includes(q_raw)) { best = Math.max(best, INNE_POLE); przybl = false; }
    }
    return [best, przybl && best < FRAGMENT];
  };
  D.szukaj = function (pozycje, zapytanie) {   // [[pozycja, punkty, czy_przyblizone]] od najlepszego
    const out = [];
    for (const p of pozycje) { const [pkt, fz] = D.ocena(p, zapytanie); if (pkt) out.push([p, pkt, fz]); }
    return out.sort((a, b) => b[1] - a[1]);   // sortowanie stabilne – jak w Pythonie
  };

  // ---- pomocnicze dla ekranu (jak zakladka.py / raport.py)
  const p2 = (n) => String(n).padStart(2, "0");
  D.czas = (iso) => { const t = new Date(iso); return isNaN(t) ? "" : `${p2(t.getDate())}.${p2(t.getMonth() + 1)}.${t.getFullYear()} ${p2(t.getHours())}:${p2(t.getMinutes())}`; };
  D.opis_przywiezienia = (p) => !p.przywiezione ? "" : !p.przywiezione_at ? "wg Excela" : (D.czas(p.przywiezione_at) + "  " + (p.przywiezione_kto || "")).trim();
  D.dzis = (p, teraz) => { const t = new Date(p.przywiezione_at || NaN), n = teraz || new Date(); return !isNaN(t) && t.toDateString() === n.toDateString(); };
  D.statystyki = (rows) => { const pr = rows.filter((p) => p.przywiezione).length; return { wszystkie: rows.length, przywiezione: pr, zostalo: rows.length - pr, dzis: rows.filter((p) => D.dzis(p)).length }; };
  D.sezon_opon = (p) => {   // kolumna rodzaj (LATO, ZIMA?), a gdy pusta – pierwszy wyraz nazwy sezonu spisu
    const r = String(p.rodzaj ?? "").trim().toUpperCase(); if (r) return r;
    const s = String(p.sezon ?? "").trim().toUpperCase().split(" ")[0]; return s === "ZIMA" || s === "LATO" ? s : "";
  };
  D.sezony_widoczne = (rows, ust) => {
    const ukryte = new Set((ust && ust.ukryte_sezony) || []);
    const wsz = [...new Set(rows.map((p) => p.sezon || ""))].sort().reverse();
    const w = wsz.filter((x) => !ukryte.has(x)); return w.length ? w : wsz;
  };
  D.najnowsza_zmiana = (rows) => rows.reduce((m, r) => (String(r.zmieniono || "") > m ? String(r.zmieniono || "") : m), "");

  root.Depozyt = D;
  if (typeof module !== "undefined") module.exports = D;
})(typeof window !== "undefined" ? window : globalThis);
