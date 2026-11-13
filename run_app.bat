@echo off
REM Inicia la aplicación de trazabilidad de reproceso (Ingenio Sancarlos)
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m streamlit run app.py
pause
