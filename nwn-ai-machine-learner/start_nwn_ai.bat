@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Python312\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo ============================================================
echo  NWN-AI Machine Learner
echo ============================================================
echo.
echo Using Python:
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found.
    echo Install Python or add it to PATH, then run this file again.
    pause
    exit /b 1
)

echo.
echo Installing/updating required packages in the current user Python...
"%PYTHON_EXE%" -m pip install --user -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo ERROR: Python package install failed.
    echo Try running: "%PYTHON_EXE%" -m pip install --user -r requirements.txt
    pause
    exit /b 1
)

echo.
echo Starting server. The browser should open automatically.
"%PYTHON_EXE%" main.py

pause
