@echo off
echo ========================================
echo  SkennerOpt - Building standalone .exe
echo ========================================
echo.

echo Installing PyInstaller...
"C:\Program Files\Python313\python.exe" -m pip install pyinstaller --user

echo.
echo Building executable (this takes 1-2 minutes)...
"C:\Program Files\Python313\python.exe" -m PyInstaller --onedir --windowed --name "SkennerOpt" --add-data "scanner_app;scanner_app" main.py

echo.
echo ========================================
echo  DONE! Your app is in: dist\SkennerOpt\
echo  Send that entire folder to the other PC
echo  and double-click SkennerOpt.exe to run.
echo ========================================
pause
