@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  NWN-AI Installer
echo ============================================================

set "PYTHON_EXE=C:\Python312\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

:: --- Python packages ---
echo.
echo [1/3] Installing Python packages...
"%PYTHON_EXE%" --version
if %errorlevel% neq 0 (
    echo ERROR: Python was not found. Install Python or add it to PATH.
    pause & exit /b 1
)
"%PYTHON_EXE%" -m pip install --user -r "%~dp0requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check your Python installation.
    pause & exit /b 1
)
echo      Done.

:: --- Ollama ---
echo.
echo [2/3] Installing Ollama (local AI engine)...

where ollama >nul 2>&1
if %errorlevel% equ 0 (
    echo      Ollama already installed, skipping download.
    goto pull_model
)

set OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe
echo      Downloading OllamaSetup.exe...
powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%OLLAMA_INSTALLER%' -UseBasicParsing"
if %errorlevel% neq 0 (
    echo ERROR: Download failed. Check your internet connection.
    pause & exit /b 1
)
echo      Running installer (silent)...
"%OLLAMA_INSTALLER%" /S
timeout /t 5 /nobreak >nul
echo      Done.

:pull_model
echo.
echo [3/3] Pulling Ollama model (mistral:7b ~4GB, one-time download)...
ollama pull mistral:7b
if %errorlevel% neq 0 (
    echo WARNING: Model pull failed. You can run "ollama pull mistral:7b" manually later.
)

:: --- Data directory ---
if not exist "%~dp0data" mkdir "%~dp0data"

echo.
echo ============================================================
echo  Installation complete!
echo  Run:  start_nwn_ai.bat
echo  The browser should open to:  http://127.0.0.1:5000
echo ============================================================
pause
