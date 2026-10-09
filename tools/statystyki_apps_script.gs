/**
 * IntegraCRM – odbiór anonimowych statystyk do Arkusza Google.
 *
 * Instalacja (raz):
 *  1. Utwórz nowy Arkusz Google, np. „IntegraCRM – statystyki”.
 *  2. Rozszerzenia → Apps Script → usuń przykładowy kod i wklej ten plik → Zapisz.
 *  3. Na górze wybierz funkcję „przygotuj” → Uruchom (zgoda na dostęp do arkusza).
 *  4. Wdróż → Nowe wdrożenie → typ: Aplikacja internetowa
 *       Wykonuj jako: Ja,  Kto ma dostęp: Wszyscy  → Wdróż.
 *  5. Skopiuj „Adres URL aplikacji internetowej” (…/exec) i prześlij go autorowi programu.
 *
 * Skrypt tylko DOPISUJE wiersze w ustalonym formacie – nikt z zewnątrz nie może niczego odczytać ani zmienić.
 */
var COLS = ['czas_utc', 'instalacja', 'wersja', 'zdarzenie', 'n_integra', 'n_crm', 'n_missing',
            'n_uncertain', 'n_autofix', 'n_warnings', 'seconds', 'n_recipients', 'error'];
var EVENTS = {start: 1, check: 1, mail_sent: 1, error: 1};

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var events = (body.events || []).slice(0, 500);
    var rows = [];
    events.forEach(function (ev) {
      if (!EVENTS[ev.event] || !/^[0-9a-f]{12}$/.test(String(ev.id))) return;   // tylko poprawne wpisy
      rows.push(COLS.map(function (c) {
        var k = {czas_utc: 'ts', instalacja: 'id', wersja: 'v', zdarzenie: 'event'}[c] || c;
        var v = ev[k];
        if (v === undefined || v === null) return '';
        if (c === 'czas_utc') return new Date(v);
        if (typeof v === 'number') return v;
        return String(v).substring(0, 60);
      }));
    });
    if (rows.length) {
      var sh = arkusz_();
      sh.getRange(sh.getLastRow() + 1, 1, rows.length, COLS.length).setValues(rows);
    }
    return ContentService.createTextOutput(JSON.stringify({ok: true, n: rows.length}));
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ok: false}));
  }
}

function arkusz_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName('Zdarzenia');
  if (!sh) {
    sh = ss.insertSheet('Zdarzenia');
    sh.appendRow(COLS);
    sh.setFrozenRows(1);
  }
  return sh;
}

/** Uruchom raz: tworzy arkusze „Zdarzenia” i „Podsumowanie” z gotowymi wzorami. */
function przygotuj() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  arkusz_();
  var p = ss.getSheetByName('Podsumowanie') || ss.insertSheet('Podsumowanie', 0);
  p.clear();
  var z = 'Zdarzenia!';
  var data = [
    ['IntegraCRM – statystyki użycia (anonimowe)', ''],
    ['', ''],
    ['Użytkownicy (instalacje) – łącznie', '=COUNTUNIQUE(' + z + 'B2:B)'],
    ['Aktywni w ostatnich 7 dniach', '=IFERROR(COUNTUNIQUE(FILTER(' + z + 'B2:B, ' + z + 'A2:A>=NOW()-7)),0)'],
    ['Aktywni w ostatnich 30 dniach', '=IFERROR(COUNTUNIQUE(FILTER(' + z + 'B2:B, ' + z + 'A2:A>=NOW()-30)),0)'],
    ['Uruchomienia programu', '=COUNTIF(' + z + 'D2:D,"start")'],
    ['Sprawdzenia', '=COUNTIF(' + z + 'D2:D,"check")'],
    ['Sprawdzenia z brakami (raport do maila)', '=COUNTIFS(' + z + 'D2:D,"check",' + z + 'G2:G,">0")'],
    ['Wysłane maile', '=COUNTIF(' + z + 'D2:D,"mail_sent")'],
    ['Błędy', '=COUNTIF(' + z + 'D2:D,"error")'],
    ['Sprawdzone numery (suma)', '=SUMIF(' + z + 'D2:D,"check",' + z + 'E2:E)'],
    ['Wykryte braki (suma)', '=SUMIF(' + z + 'D2:D,"check",' + z + 'G2:G)'],
    ['Średni czas sprawdzenia [s]', '=IFERROR(AVERAGEIF(' + z + 'D2:D,"check",' + z + 'K2:K),"")'],
    ['', ''],
    ['Tygodniowo', ''],
  ];
  p.getRange(1, 1, data.length, 2).setValues(data);
  p.getRange('A16').setFormula(
    '=IFERROR(QUERY(' + z + 'A2:D, "select year(A), week(A), count(D) where D = \'check\' group by year(A), week(A) ' +
    'order by year(A) desc, week(A) desc label year(A) \'Rok\', week(A) \'Tydzień\', count(D) \'Sprawdzenia\'", 0), "brak danych")');
  p.getRange('E15').setValue('Wersje w użyciu (ostatnie 30 dni)');
  p.getRange('E16').setFormula(
    '=IFERROR(QUERY(' + z + 'A2:D, "select C, count(B) where A >= date \'"&TEXT(TODAY()-30,"yyyy-mm-dd")&"\' ' +
    'group by C order by C desc label C \'Wersja\', count(B) \'Zdarzenia\'", 0), "brak danych")');
  p.getRange('A1').setFontWeight('bold').setFontSize(14);
  p.getRange('A15').setFontWeight('bold');
  p.getRange('E15').setFontWeight('bold');
  p.setColumnWidth(1, 320);
}
