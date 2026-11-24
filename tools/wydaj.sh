#!/usr/bin/env bash
# Wydanie oficjalne IntegraCRM – jedyna dozwolona droga (CLAUDE.md, zasada 7).
# Każdy krok musi się udać; przy pierwszym błędzie skrypt przerywa, zanim cokolwiek trafi na GitHuba.
#
#   tools/wydaj.sh            – testy + wydanie (commit z VERSION i CHANGELOG musi już być na gałęzi praca/…)
#   tools/wydaj.sh --tylko-testy
#
# Środowisko jak w CLAUDE.md („Sprawdzanie”): /tmp/venv z Pythonem 3.12, xvfb-run, systemowy python3 z Playwright.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO=djjuniord-boop/IntegraCRM
PY=${PY:-/tmp/venv/bin/python}
stop() { echo; echo "❌ STOP: $*"; exit 1; }
krok() { echo; echo "── $*"; }

GAL=$(git rev-parse --abbrev-ref HEAD)
[[ $GAL == praca/* ]] || stop "wydanie tylko z gałęzi praca/… (jesteś na $GAL)"
[[ -z $(git status --porcelain) ]] || stop "niezatwierdzone zmiany – najpierw commit"

krok "Świeży stan (git fetch + rebase na origin/beta)"
git fetch -q origin 2>/dev/null || git fetch -q origin
git rebase -q origin/beta || stop "konflikt przy rebase – rozwiąż ręcznie"

ver() { grep -m1 '^VERSION' "$1" | sed -E 's/.*"([^"]+)".*/\1/'; }
V=$(ver app/version.py)
VB=$(git show origin/beta:app/version.py | grep -m1 '^VERSION' | sed -E 's/.*"([^"]+)".*/\1/')
if [[ ${1:-} != --tylko-testy ]]; then
  krok "Wersja: $VB (beta) → $V"
  python3 - "$V" "$VB" <<'EOF' || stop "VERSION musi być wyższa niż na origin/beta, a pierwszy wpis CHANGELOG musi mieć tę wersję"
import re, sys
v, vb = (tuple(int(x) for x in s.split(".")) for s in sys.argv[1:3])
src = open("app/version.py", encoding="utf-8").read()
first = re.search(r'CHANGELOG\s*=\s*\[\s*\{\s*"version":\s*"([^"]+)"', src).group(1)
sys.exit(0 if v > vb and first == sys.argv[1] else 1)
EOF
fi

krok "Literówki i brakujące nazwy (pyflakes – tylko prawdziwe błędy)"
BLEDY=$($PY -m pyflakes app 2>&1 | grep -E "undefined name|invalid syntax|SyntaxError|unexpected|redefinition of unused .* from line" || true)
[[ -z $BLEDY ]] || { echo "$BLEDY"; stop "pyflakes"; }

krok "Importy"
$PY tests/check_imports.py || stop "brakujące importy"

krok "Testy modułów"
xvfb-run -a $PY tests/run_tests.py > /tmp/wydaj_testy.log 2>&1 || { grep -A12 "BŁĄD" /tmp/wydaj_testy.log | head -60; tail -1 /tmp/wydaj_testy.log; stop "testy modułów"; }
tail -1 /tmp/wydaj_testy.log

krok "Panel OFERT (JavaScript)"
python3 tests/test_oferty_js.py > /tmp/wydaj_js.log 2>&1 || { tail -30 /tmp/wydaj_js.log; stop "testy JS ofert"; }
grep -q "pominięty" /tmp/wydaj_js.log && stop "testy JS pominięte (brak Playwright w systemowym python3)"
tail -1 /tmp/wydaj_js.log

[[ ${1:-} == --tylko-testy ]] && { echo; echo "✅ Testy przeszły (bez wydania)."; exit 0; }

krok "Wysyłka: beta + main"
git checkout -q beta && git pull -q --ff-only origin beta 2>/dev/null
git merge -q --ff-only "$GAL" || { git checkout -q "$GAL"; stop "beta nie da się przewinąć do $GAL"; }
git checkout -q main && git pull -q --ff-only origin main 2>/dev/null
git merge -q --no-edit beta || { git merge --abort; git checkout -q "$GAL"; stop "konflikt beta → main"; }
SHA=$(git rev-parse HEAD)
git push -q origin beta main "$GAL" 2>&1 | grep -viE "moved|location|acknowledg|negotiation|github.com" || true
git checkout -q "$GAL"
[[ $(git ls-remote origin refs/heads/main | cut -f1) == "$SHA" ]] || stop "push main się nie udał"

krok "Budowa na GitHubie (Windows) dla $SHA"
RUN=""
for _ in $(seq 60); do
  RUN=$(gh run list -R $REPO -b main -c "$SHA" -w "Zbuduj IntegraCRM.exe" -L 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)
  [[ -n $RUN ]] && break; sleep 5
done
[[ -n $RUN ]] || stop "nie znalazłem budowy dla $SHA"
gh run watch "$RUN" -R $REPO --exit-status > /dev/null 2>&1 || stop "budowa $RUN się nie udała – wersja NIE jest wydana (gh run view $RUN -R $REPO --log-failed)"

TAG=$(gh api repos/$REPO/releases/latest -q .tag_name)
[[ $TAG == "v$V" ]] || stop "budowa przeszła, ale najnowsze wydanie to $TAG, a nie v$V"
echo; echo "✅ Wersja $V wydana oficjalnie (budowa $RUN, testy na Windows przeszły)."
