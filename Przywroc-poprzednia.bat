@echo off
cd /d "%~dp0"
if not exist "data\backup\app\version.py" (
    echo Brak kopii poprzedniej wersji.
    pause
    exit /b
)
set V=
for /f "tokens=3 delims= " %%a in ('findstr /b "VERSION" app\version.py') do set V=%%~a
if not "%V%"=="" echo %V%> data\skip_version.txt
xcopy "data\backup\app" "app" /E /Y /I /Q >nul
echo Przywrocono poprzednia wersje programu.
echo Wersja %V% nie bedzie instalowana ponownie, dopoki nie pojawi sie nowsza.
pause
