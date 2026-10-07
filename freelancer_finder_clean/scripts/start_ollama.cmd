@echo off
setlocal
cd /d "%~dp0\.."
if not defined OLLAMA_MODELS set "OLLAMA_MODELS=%CD%\..\.ollama_models"
set "OLLAMA_HOST=127.0.0.1:11435"
set "OLLAMA_MAX_TRANSFER_STREAMS=1"
"%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve

