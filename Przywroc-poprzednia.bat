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
rem usun pliki .py nowej wersji (tak jak przywracanie w programie), zeby nie zostaly nowe moduly
for /r "app" %%f in (*.py) do del /q "%%f" >nul 2>nul
xcopy "data\backup\app" "app" /E /Y /I /Q >nul
echo Przywrocono poprzednia wersje programu.
echo Wersja %V% nie bedzie instalowana ponownie, dopoki nie pojawi sie nowsza.
echo Uwaga: jesli administrator ustawil minimalna wersje %V%, program przy starcie
echo zainstaluje ja ponownie. Wycofanie dla wszystkich wymaga obnizenia minimalnej wersji w bazie.
pause
