@echo off
cd /d "%~dp0"
echo ========================================
echo  SkennerOpt - Building standalone .exe
echo ========================================
echo.

:: Find Python
set PYTHON=
for %%p in (
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe"
) do (
    if exist %%p (
        set PYTHON=%%p
        goto :found
    )
)

python --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python
    goto :found
)

echo ERROR: Python not found! Please install Python from https://python.org
pause
exit /b 1

:found
echo Found Python: %PYTHON%
echo.

echo Installing PyInstaller...
%PYTHON% -m pip install pyinstaller

echo.
echo Building executable (this takes 1-2 minutes)...
%PYTHON% -m PyInstaller --onedir --windowed --name "SkennerOpt" --add-data "scanner_app;scanner_app" main.py

echo.
echo ========================================
echo  DONE! Your app is in: dist\SkennerOpt\
echo  Copy that entire folder to the other PC
echo  and double-click SkennerOpt.exe to run.
echo ========================================
pause
