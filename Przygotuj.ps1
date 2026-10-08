$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$rt = Join-Path $root "runtime"
$pyDir = Join-Path $rt "python"
$tessDir = Join-Path $rt "tesseract"
$req = Join-Path $root "app\requirements.txt"
New-Item -ItemType Directory -Force -Path $rt | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

function Say($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "   [OK] $t" -ForegroundColor Green }
function Todo($t) { Write-Host "   [BRAK] $t" -ForegroundColor Yellow }

# Zwraca sciezke dzialajacego Pythona (>=3.9, z tkinter) albo $null
function Test-Python($exe) {
    if (-not $exe) { return $false }
    $ErrorActionPreference = "Continue"
    try {
        & $exe -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}
function Find-Python {
    $cands = @()
    $cands += (Join-Path $pyDir "python.exe")
    foreach ($n in @("py", "python")) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c -and $c.Source -notlike "*WindowsApps*") { $cands += $c.Source }
    }
    foreach ($e in $cands) {
        if ((Test-Path $e) -and (Test-Python $e)) {
            $ErrorActionPreference = "Continue"
            $real = & $e -c "import sys; print(sys.executable)"
            return ($real | Select-Object -First 1).Trim()
        }
    }
    return $null
}
function Find-Tesseract {
    $cands = @((Join-Path $tessDir "tesseract.exe"), "C:\Program Files\Tesseract-OCR\tesseract.exe",
               "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")
    $c = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($c) { $cands += $c.Source }
    foreach ($e in $cands) { if (Test-Path $e) { return $e } }
    return $null
}

try {
    Say "Sprawdzam, co jest juz zainstalowane"

    # 1. Python
    $py = Find-Python
    if ($py) {
        Ok "Python: $py"
    } else {
        Todo "Python (3.9+ z tkinter) - pobiore go do folderu programu"
        Say "Python: pobieranie i instalacja w folderze programu"
        $inst = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile $inst
        $pyArgs = @("/quiet", "InstallAllUsers=0", "TargetDir=`"$pyDir`"", "Include_launcher=0",
                    "Include_test=0", "Include_doc=0", "Include_pip=1", "Include_tcltk=1",
                    "AssociateFiles=0", "Shortcuts=0", "PrependPath=0")
        $p = Start-Process -FilePath $inst -ArgumentList $pyArgs -Wait -PassThru
        $py = Join-Path $pyDir "python.exe"
        if (-not (Test-Path $py)) { throw "Instalacja Pythona nie powiodla sie (kod $($p.ExitCode))." }
    }

    # 2. Biblioteki
    $missing = @()
    foreach ($line in Get-Content $req) {
        $name = ($line -split "[=<>~ ]")[0].Trim()
        if (-not $name) { continue }
        $ErrorActionPreference = "Continue"
        & $py -m pip show $name 2>&1 | Out-Null
        $ErrorActionPreference = "Stop"
        if ($LASTEXITCODE -ne 0) { $missing += $name } else { Ok "Biblioteka: $name" }
    }
    if ($missing.Count -gt 0) {
        Todo ("Biblioteki: " + ($missing -join ", "))
        Say "Instaluje brakujace biblioteki"
        & $py -m pip install --no-warn-script-location --disable-pip-version-check @missing
        if ($LASTEXITCODE -ne 0) { throw "Instalacja bibliotek nie powiodla sie." }
    }

    # 3. Tesseract OCR
    $tess = Find-Tesseract
    if ($tess) {
        Ok "Tesseract: $tess"
    } else {
        Todo "Tesseract OCR - pobiore go do folderu programu"
        Say "Tesseract: pobieranie instalatora"
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" -Headers @{ "User-Agent" = "IntegraCRM" }
        $asset = $rel.assets | Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } | Select-Object -First 1
        if (-not $asset) { throw "Nie znaleziono instalatora Tesseract. Zainstaluj go recznie (github.com/UB-Mannheim/tesseract/wiki) i uruchom ten plik ponownie." }
        $ti = Join-Path $env:TEMP $asset.name
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $ti
        Start-Process -FilePath $ti -ArgumentList "/S", "/D=$tessDir" -Wait
        if (-not (Test-Path (Join-Path $tessDir "tesseract.exe"))) { throw "Instalacja Tesseract nie powiodla sie." }
    }

    # zapamietaj, ktorego Pythona uzyc (Start.bat)
    New-Item -ItemType Directory -Force -Path (Join-Path $root "data") | Out-Null
    $pyw = Join-Path (Split-Path -Parent $py) "pythonw.exe"
    if (-not (Test-Path $pyw)) { $pyw = $py }
    Set-Content -Path (Join-Path $root "data\python_path.txt") -Value $pyw -Encoding ASCII

    Write-Host ""
    Write-Host "GOTOWE. Uruchamiaj program plikiem Start.bat." -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "BLAD: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
