@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
if exist requirements-build.txt python -m pip install -r requirements-build.txt
pause
