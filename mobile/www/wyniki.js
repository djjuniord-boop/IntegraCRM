// WYNIKI – port app/wyniki/dane.py (te same wzory; zgodność sprawdza mobile/test/zgodnosc.py). Tylko odczyt.
(function (root) {
  const W = {};
  W.ODDZIALY = [["wroclaw", "Wrocław"], ["opole", "Opole"]];
  W.ODDZIAL_KONTA = { "Latex Wrocław": "wroclaw", "Latex Opole": "opole" };
  W.zl = (v) => (v === null || v === undefined ? "—" : Math.round(+v).toLocaleString("pl-PL").replace(/\s/g, " ") + " zł");
  const iso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const dzien = (v) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v || "")); return m ? m[1] + "-" + m[2] + "-" + m[3] : null; };
  // znacznik czasu z bazy (UTC) -> data lokalna (zapis o 0:30 to już nowy dzień)
  const dzienLokalny = (v) => { if (!v) return null; const t = new Date(String(v).replace(" ", "T")); return isNaN(t) ? dzien(v) : (/[zZ]|[+-]\d\d:?\d\d$/.test(String(v)) ? iso(t) : dzien(v)); };

  W.dni_sprzedazowe = function (year, month, holidays) {
    const sw = new Set((holidays || []).map(dzien).filter(Boolean)), n = new Date(year, month, 0).getDate(), out = [];
    for (let d = 1; d <= n; d++) { const dt = new Date(year, month - 1, d); if (dt.getDay() !== 0 && !sw.has(iso(dt))) out.push(iso(dt)); }
    return out;
  };
  W.podsumowanie = function (row, today) {
    const t = today || iso(new Date()), ty = +t.slice(0, 4), tm = +t.slice(5, 7);
    const year = +row.year, month = +row.month;
    const cel = row.target !== null && row.target !== undefined ? +row.target : null;
    const zrob = row.done !== null && row.done !== undefined ? +row.done : null;
    const dni = W.dni_sprzedazowe(year, month, row.holidays), dni_all = dni.length;
    const biezacy = year === ty && month === tm;
    const dzien_dzis = biezacy ? dni.filter((d) => d <= t).length : null;
    let dni_min;
    if (biezacy) { const upd = dzienLokalny(row.updated_at); dni_min = dni.filter((d) => (upd !== null && upd >= t ? d <= t : d < t)).length; }
    else if (year < ty || (year === ty && month < tm)) dni_min = dni_all;
    else dni_min = 0;
    const dni_zost = dni_all - dni_min;
    const r = { label: row.label || String(month).padStart(2, "0") + "." + year, year, month, cel, zrobione: zrob, biezacy, dni_all, dni_minelo: dni_min,
      dzien_dzis, dni_zostalo: dni_zost, pct: null, plan_dzis: null, tempo: null, prognoza: null, brakuje: null, potrzeba_dziennie: null, srednio_dziennie: null,
      updated_at: row.updated_at || null };
    if (cel && cel > 0 && zrob !== null) { r.pct = (zrob / cel) * 100; r.brakuje = Math.max(cel - zrob, 0); }
    if (cel && cel > 0 && dni_all) { r.plan_dzis = (cel * dni_min) / dni_all; if (zrob !== null && dni_min) r.tempo = (zrob / r.plan_dzis) * 100; }
    if (zrob !== null && dni_min) { r.srednio_dziennie = zrob / dni_min; if (dni_all) r.prognoza = (zrob / dni_min) * dni_all; }
    if (r.brakuje !== null && dni_zost) r.potrzeba_dziennie = r.brakuje / dni_zost;
    return r;
  };
  const key = (r) => +r.year * 100 + +r.month;
  W.wybierz_miesiac = function (rows, today) {
    const t = today || iso(new Date()), k = +t.slice(0, 4) * 100 + +t.slice(5, 7);
    for (const r of rows) if (key(r) === k) return r;
    const past = rows.filter((r) => r.done !== null && r.done !== undefined && key(r) <= k);
    return past.length ? past.reduce((a, b) => (key(b) > key(a) ? b : a)) : null;
  };
  W.poprzednie = function (rows, biezacy) {
    if (!biezacy) return [];
    return rows.filter((r) => key(r) < key(biezacy) && ((r.target !== null && r.target !== undefined) || (r.done !== null && r.done !== undefined))).sort((a, b) => key(b) - key(a));
  };
  W.punkty_wykresu = function (row, runs, today) {
    const t = today || iso(new Date()), year = +row.year, month = +row.month;
    const dni = W.dni_sprzedazowe(year, month, row.holidays);
    if (!dni.length) return [];
    const idx = (d) => dni.filter((x) => x <= d).length, per = new Map();
    for (const r of [...runs].sort((a, b) => String(a.run_at || "").localeCompare(String(b.run_at || "")))) {
      if (r.done === null || r.done === undefined) continue;
      const d = dzien(r.run_at); if (!d || +d.slice(0, 4) !== year || +d.slice(5, 7) !== month) continue;
      per.set(idx(d), +r.done);
    }
    if (row.done !== null && row.done !== undefined && year === +t.slice(0, 4) && month === +t.slice(5, 7))
      per.set(Math.max(idx(t), Math.max(0, ...per.keys())), +row.done);
    return [...per.entries()].sort((a, b) => a[0] - b[0]);
  };
  // oddziały widoczne dla konta (admin i MARŻA – oba); resztę i tak pilnuje baza (can_see_marza)
  W.oddzialy = function (p) {
    if (p.role === "admin" || (p.modules || []).includes("marza")) return W.ODDZIALY.map((x) => x[0]);
    const mine = new Set((p.branches || []).map((b) => W.ODDZIAL_KONTA[b]));
    return W.ODDZIALY.map((x) => x[0]).filter((k) => mine.has(k));
  };
  root.Wyniki = W;
  if (typeof module !== "undefined") module.exports = W;
})(typeof window !== "undefined" ? window : globalThis);
