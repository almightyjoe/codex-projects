@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
pyinstaller --noconfirm --onedir --windowed --name SteamOSINTReportBuilder steam_osint_report_builder.py
pause
