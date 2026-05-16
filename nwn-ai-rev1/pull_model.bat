@echo off
set OLLAMA_MODELS=D:\1Ollama
echo Pulling Ollama model: mistral:7b (~4GB, one-time download)
echo This may take several minutes depending on your connection.
echo.
ollama pull mistral:7b
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Pull failed. Make sure Ollama service is running.
    echo Try:  ollama serve
    echo Then re-run this script.
) else (
    echo.
    echo Done! Model ready. Start NWN-AI with: python main.py
)
pause
