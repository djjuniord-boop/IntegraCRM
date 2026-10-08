@echo off
cd /d "%~dp0"
if exist "data\python_path.txt" (
    set /p PYW=<"data\python_path.txt"
    setlocal enabledelayedexpansion
    if exist "!PYW!" (
        start "" "!PYW!" "app\start.py"
        exit /b
    )
    endlocal
)
if exist "runtime\python\pythonw.exe" (
    start "" "runtime\python\pythonw.exe" "app\start.py"
    exit /b
)
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "app\start.py"
    exit /b
)
echo Brak srodowiska programu. Uruchom najpierw Przygotuj.bat.
pause
