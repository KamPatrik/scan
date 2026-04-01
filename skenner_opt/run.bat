@echo off
python main.py
if errorlevel 1 (
    echo.
    echo ERROR: Could not launch. Make sure Python is installed and in PATH.
    echo Try: py main.py
    pause
)
