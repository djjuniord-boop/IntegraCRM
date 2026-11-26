/**
 * DEPOZYT ↔ arkusz Google (Apps Script). Wklej w arkuszu: Rozszerzenia → Apps Script → Kod.gs.
 *
 * Arkusz → program: zmiana komórki (checkbox PRZYWIEZIONE, NR, LOK, marka, ilość, sezon, uwagi, komentarz)
 *   od razu idzie do bazy funkcją depozyt_zmien – jak w programie, z wpisem w historii.
 *   Nowy wiersz (NR + LOK, bez ID) → depozyt_dodaj.
 * Program → arkusz: baza od razu wysyła każdą zmianę do aplikacji internetowej tego skryptu (doPost, klucz),
 *   a co minutę – na wszelki wypadek – pobierane są pozycje zmienione od ostatniej synchronizacji (`zmieniono`).
 *
 * Konto: osobne konto programu z modułem „depozyt” i oddziałem (np. „Arkusz Google”). E-mail i hasło wpisuje
 * właściciel w menu Depozyt → Ustawienia połączenia (zapisują się we właściwościach skryptu, nie w arkuszu).
 * Bez haseł i danych klientów w tym pliku – jest w publicznym repozytorium.
 */
var URL = 'https://nlrwulrtaocuemfmlfav.supabase.co';
var ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5scnd1bHJ0YW9jdWVtZm1sZmF2Iiwi' +
           'cm9sZSI6ImFub24iLCJpYXQiOjE3OTE4ODY2NTYsImV4cCI6MjEwNzQ2MjY1Nn0.F6Qd7vvYuDZs4Opt_4dnOPmPpsKB8rzAZ5iF47h6gtk';
var ARKUSZ = 'DEPOZYT';
// kolumny (1 = A)
var K = {PRZYW: 1, NR: 2, LOK: 3, MARKA: 4, MARKA2: 5, ILOSC: 6, RODZAJ: 7, UWAGI: 8, KOM: 9, KIEDY: 10, KTO: 11,
         ID: 12};
var NAGLOWKI = ['PRZYWIEZIONE', 'NR REJ.', 'LOK', 'MARKA', 'MARKA 2', 'ILOŚĆ', 'SEZON', 'UWAGI', 'KOMENTARZ',
                'DATA I GODZINA', 'KTO', 'ID (nie zmieniać)'];
var POLE = {}; POLE[K.NR] = 'nr'; POLE[K.LOK] = 'lok'; POLE[K.MARKA] = 'marka'; POLE[K.MARKA2] = 'marka2';
POLE[K.ILOSC] = 'ilosc'; POLE[K.RODZAJ] = 'rodzaj'; POLE[K.UWAGI] = 'uwagi'; POLE[K.KOM] = 'komentarz';
POLE[K.PRZYW] = 'przywiezione';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Depozyt')
    .addItem('Ustawienia połączenia…', 'ustawienia')
    .addItem('Wczytaj cały spis z programu (od nowa)', 'wczytajWszystko')
    .addItem('Synchronizuj teraz', 'synchronizuj')
    .addItem('Włącz automatyczną synchronizację', 'wlaczAutomat')
    .addItem('Natychmiastowe zmiany z programu – dane dla bazy', 'daneDlaBazy')
    .addToUi();
}

function P() { return PropertiesService.getScriptProperties(); }

function ustawienia() {
  var ui = SpreadsheetApp.getUi();
  var pola = [['EMAIL', 'E-mail konta programu (moduł depozyt)'], ['HASLO', 'Hasło tego konta'],
              ['ODDZIAL', 'Oddział (np. Latex Wrocław)'], ['SEZON', 'Sezon spisu (np. ZIMA 2026/27)']];
  for (var i = 0; i < pola.length; i++) {
    var r = ui.prompt('Depozyt – połączenie', pola[i][1] + (pola[i][0] === 'HASLO' ? '' :
                      '\nTeraz: ' + (P().getProperty(pola[i][0]) || '—')), ui.ButtonSet.OK_CANCEL);
    if (r.getSelectedButton() !== ui.Button.OK) return;
    if (r.getResponseText().trim()) P().setProperty(pola[i][0], r.getResponseText().trim());
  }
  P().deleteProperty('TOKEN');
  token_();
  ui.alert('Połączono. Teraz: Depozyt → Wczytaj cały spis z programu, potem Włącz automatyczną synchronizację.');
}

function token_() {
  var t = P().getProperty('TOKEN'), wygasa = Number(P().getProperty('TOKEN_DO') || 0);
  if (t && Date.now() < wygasa - 120000) return t;
  var odsw = P().getProperty('REFRESH');
  var odp = odsw ? http_('post', '/auth/v1/token?grant_type=refresh_token', {refresh_token: odsw}, true, null) : null;
  if (!odp || !odp.access_token) {
    odp = http_('post', '/auth/v1/token?grant_type=password',
                {email: P().getProperty('EMAIL'), password: P().getProperty('HASLO')}, false, null);
  }
  if (!odp || !odp.access_token) throw new Error('Nie udało się zalogować – sprawdź Depozyt → Ustawienia połączenia.');
  P().setProperties({TOKEN: odp.access_token, REFRESH: odp.refresh_token,
                     TOKEN_DO: String(Date.now() + (odp.expires_in || 3600) * 1000)});
  return odp.access_token;
}

function http_(metoda, sciezka, body, cicho, tok) {
  var opt = {method: metoda, muteHttpExceptions: true, contentType: 'application/json',
             headers: {apikey: ANON, Authorization: 'Bearer ' + (tok || ANON), Prefer: 'return=representation'}};
  if (body) opt.payload = JSON.stringify(body);
  var r = UrlFetchApp.fetch(URL + sciezka, opt);
  var kod = r.getResponseCode(), txt = r.getContentText();
  if (kod >= 300) {
    if (cicho) return null;
    var msg = txt;
    try { var j = JSON.parse(txt); msg = j.message || j.error_description || j.msg || txt; } catch (e) {}
    throw new Error(msg);
  }
  return txt ? JSON.parse(txt) : null;
}

function api_(metoda, sciezka, body) {
  var odp = http_(metoda, sciezka, body, false, token_());
  return (sciezka.indexOf('/rpc/') >= 0 && Array.isArray(odp)) ? odp[0] : odp;   // funkcja zwraca jeden wiersz
}

function filtr_() {
  return 'branch=eq.' + encodeURIComponent(P().getProperty('ODDZIAL')) +
         '&sezon=eq.' + encodeURIComponent(P().getProperty('SEZON'));
}

function pobierz_(dodatkowy) {
  var out = [], off = 0;
  while (true) {
    var rows = api_('get', '/rest/v1/depozyt?select=*&' + filtr_() + (dodatkowy || '') +
                    '&order=id&limit=1000&offset=' + off) || [];
    out = out.concat(rows);
    if (rows.length < 1000) return out;
    off += 1000;
  }
}

function czas_(iso) {
  if (!iso) return '';
  return Utilities.formatDate(new Date(iso), 'Europe/Warsaw', 'dd.MM.yyyy HH:mm');
}

function wiersz_(p) {
  var w = [];
  w[K.PRZYW - 1] = !!p.przywiezione; w[K.NR - 1] = p.nr; w[K.LOK - 1] = p.lok; w[K.MARKA - 1] = p.marka;
  w[K.MARKA2 - 1] = p.marka2; w[K.ILOSC - 1] = p.ilosc; w[K.RODZAJ - 1] = p.rodzaj; w[K.UWAGI - 1] = p.uwagi;
  w[K.KOM - 1] = p.komentarz;
  w[K.KIEDY - 1] = p.przywiezione ? (p.przywiezione_at ? czas_(p.przywiezione_at) : 'wg Excela') : '';
  w[K.KTO - 1] = p.przywiezione ? (p.przywiezione_kto || '') : '';
  w[K.ID - 1] = p.id;
  return w;
}

function arkusz_() {
  var ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(ARKUSZ) || ss.insertSheet(ARKUSZ, 0);
}

/** Buduje zakładkę DEPOZYT od nowa z bazy (pozostałe zakładki zostają bez zmian). */
function wczytajWszystko() {
  var rows = pobierz_('');
  var sh = arkusz_();
  sh.clear();
  sh.clearConditionalFormatRules();
  sh.getProtections(SpreadsheetApp.ProtectionType.RANGE).forEach(function (x) { x.remove(); });
  sh.getRange(1, 1, 1, NAGLOWKI.length).setValues([NAGLOWKI]).setFontWeight('bold')
    .setBackground('#1d2330').setFontColor('#ffffff');
  if (rows.length) sh.getRange(2, 1, rows.length, NAGLOWKI.length).setValues(rows.map(wiersz_));
  var n = Math.max(rows.length + 300, 500);   // zapas na nowe wiersze
  if (sh.getMaxRows() < n + 1) sh.insertRowsAfter(sh.getMaxRows(), n + 1 - sh.getMaxRows());
  sh.getRange(2, K.PRZYW, n, 1).insertCheckboxes();
  var caly = sh.getRange(2, 1, n, NAGLOWKI.length);
  sh.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2=TRUE').setBackground('#ff9999')
      .setRanges([caly]).build()]);
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);
  sh.getRange(2, K.KIEDY, n, 2).setFontColor('#990000');
  sh.getRange(1, K.ID, n + 1, 1).setFontColor('#999999');
  sh.getRange(1, K.KIEDY, n + 1, 2).protect().setDescription('Wypełnia program').setWarningOnly(true);
  sh.getRange(1, K.ID, n + 1, 1).protect().setDescription('Łączy wiersz z programem – nie zmieniać').setWarningOnly(true);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.getRange(1, 1, n + 1, NAGLOWKI.length).createFilter();
  [110, 100, 70, 120, 100, 60, 70, 180, 220, 130, 120, 80].forEach(function (w, i) { sh.setColumnWidth(i + 1, w); });
  P().setProperty('OSTATNIO', new Date().toISOString());
  SpreadsheetApp.getActive().toast('Wczytano ' + rows.length + ' pozycji z programu.', 'Depozyt');
}

/** Program → arkusz: tylko pozycje zmienione od ostatniej synchronizacji. */
function synchronizuj() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return;
  try {
    var od = P().getProperty('OSTATNIO') || '1970-01-01T00:00:00Z';
    var start = new Date().toISOString();
    var rows = pobierz_('&zmieniono=gt.' + encodeURIComponent(od));
    if (!rows.length) { P().setProperty('OSTATNIO', start); return; }
    var sh = arkusz_();
    var ostatni = Math.max(sh.getLastRow(), 1);
    var ids = ostatni > 1 ? sh.getRange(2, K.ID, ostatni - 1, 1).getValues().map(function (r) { return String(r[0]); }) : [];
    rows.forEach(function (p) {
      var i = ids.indexOf(String(p.id));
      if (i >= 0) {
        sh.getRange(i + 2, 1, 1, NAGLOWKI.length).setValues([wiersz_(p)]);
      } else {
        ostatni += 1;
        sh.getRange(ostatni, 1, 1, NAGLOWKI.length).setValues([wiersz_(p)]);
        ids.push(String(p.id));
      }
    });
    var maks = rows.reduce(function (m, p) { return p.zmieniono > m ? p.zmieniono : m; }, od);
    P().setProperty('OSTATNIO', maks > start ? maks : start);
  } finally {
    lock.releaseLock();
  }
}

/** Arkusz → program: wyzwalacz „Przy edycji” (instalowany – ma dostęp do sieci). */
function przyEdycji(e) {
  if (!e || !e.range) return;
  var sh = e.range.getSheet();
  if (sh.getName() !== ARKUSZ || e.range.getRow() < 2) return;
  var r0 = e.range.getRow(), c0 = e.range.getColumn();
  var nr = e.range.getNumRows(), nc = e.range.getNumColumns();
  if (nr * nc > 200) {
    SpreadsheetApp.getActive().toast('Zmieniono naraz zbyt dużo komórek – wysyłam tylko do 200. Użyj programu do zmian hurtowych.',
                                     'Depozyt', 8);
  }
  var bledy = [];
  for (var r = r0; r < r0 + nr && r < r0 + 200; r++) {
    var wiersz = sh.getRange(r, 1, 1, NAGLOWKI.length).getValues()[0];
    var id = wiersz[K.ID - 1];
    try {
      if (!id) {   // nowy wiersz: dodaj, gdy jest numer i lokalizacja
        if (wiersz[K.NR - 1] && wiersz[K.LOK - 1]) {
          var p = api_('post', '/rest/v1/rpc/depozyt_dodaj', {
            p_branch: P().getProperty('ODDZIAL'), p_sezon: P().getProperty('SEZON'), p_nr: String(wiersz[K.NR - 1]),
            p_lok: String(wiersz[K.LOK - 1]), p_marka: String(wiersz[K.MARKA - 1] || ''),
            p_ilosc: String(wiersz[K.ILOSC - 1] || ''), p_rodzaj: String(wiersz[K.RODZAJ - 1] || ''),
            p_uwagi: String(wiersz[K.UWAGI - 1] || '')});
          if (p && p.id) sh.getRange(r, 1, 1, NAGLOWKI.length).setValues([wiersz_(p)]);
        }
        continue;
      }
      for (var c = c0; c < c0 + nc; c++) {
        var pole = POLE[c];
        if (!pole) continue;   // DATA, KTO, ID – wypełnia program
        var v = wiersz[c - 1];
        var wart = pole === 'przywiezione' ? (v === true ? '1' : '0') : String(v);
        var nowy = api_('post', '/rest/v1/rpc/depozyt_zmien', {p_id: Number(id), p_pole: pole, p_wartosc: wart});
        if (nowy && nowy.id) sh.getRange(r, 1, 1, NAGLOWKI.length).setValues([wiersz_(nowy)]);
      }
    } catch (err) {
      bledy.push('wiersz ' + r + ': ' + err.message);
      try {   // odrzucona zmiana (np. cofnięcie tylko dla administratora) – przywróć stan z programu
        var teraz = id ? api_('get', '/rest/v1/depozyt?select=*&id=eq.' + Number(id)) : null;
        if (teraz && teraz.length) sh.getRange(r, 1, 1, NAGLOWKI.length).setValues([wiersz_(teraz[0])]);
      } catch (e2) {}
    }
  }
  if (bledy.length) SpreadsheetApp.getActive().toast('Nie zapisano w programie:\n' + bledy.slice(0, 5).join('\n'), 'Depozyt', 10);
}

function wlaczAutomat() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('przyEdycji').forSpreadsheet(SpreadsheetApp.getActive()).onEdit().create();
  ScriptApp.newTrigger('synchronizuj').timeBased().everyMinutes(1).create();
  SpreadsheetApp.getUi().alert('Automatyczna synchronizacja włączona: zmiany z arkusza idą od razu, ' +
                               'zmiany z programu pojawiają się w ciągu minuty.');
}

/** Adres aplikacji internetowej i klucz do wpisania w bazie (plik SQL od Claude). */
function daneDlaBazy() {
  var klucz = P().getProperty('KLUCZ');
  if (!klucz) {
    klucz = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    P().setProperty('KLUCZ', klucz);
  }
  var url = ScriptApp.getService().getUrl();
  var html = HtmlService.createHtmlOutput(
    '<div style="font:13px Arial">' + (url ? '' : '<p style="color:#b00"><b>Najpierw wdróż skrypt jako aplikację ' +
    'internetową</b> (Wdróż → Nowe wdrożenie → Aplikacja internetowa; wykonuj jako: Ja; dostęp: Każdy).</p>') +
    '<p>Adres:</p><textarea style="width:100%;height:60px" onclick="this.select()">' + (url || '') + '</textarea>' +
    '<p>Klucz:</p><textarea style="width:100%;height:40px" onclick="this.select()">' + klucz + '</textarea>' +
    '<p>Wklej oba do pliku SQL od Claude (zamiast ADRES i KLUCZ).</p></div>').setWidth(520).setHeight(300);
  SpreadsheetApp.getUi().showModalDialog(html, 'Depozyt – dane dla bazy');
}

/** Powiadomienie z bazy o zmianie jednej pozycji (aplikacja internetowa). */
function doPost(e) {
  var d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return ContentService.createTextOutput('zly json'); }
  if (!d || d.klucz !== P().getProperty('KLUCZ') || !d.wiersz) return ContentService.createTextOutput('odmowa');
  var p = d.wiersz;
  if (p.branch !== P().getProperty('ODDZIAL') || p.sezon !== P().getProperty('SEZON')) {
    return ContentService.createTextOutput('inny spis');
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var sh = arkusz_();
    var ostatni = Math.max(sh.getLastRow(), 1);
    var ids = ostatni > 1 ? sh.getRange(2, K.ID, ostatni - 1, 1).getValues().map(function (r) { return String(r[0]); }) : [];
    var i = ids.indexOf(String(p.id));
    var r = i >= 0 ? i + 2 : ostatni + 1;
    sh.getRange(r, 1, 1, NAGLOWKI.length).setValues([wiersz_(p)]);
  } finally {
    lock.releaseLock();
  }
  return ContentService.createTextOutput('ok');
}
