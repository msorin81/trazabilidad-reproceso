@echo off
REM Inicia la aplicación de trazabilidad de reproceso (Ingenio Sancarlos)
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
REM headless: no pregunta correo al iniciar; el navegador se abre aparte
start "" "http://localhost:8501"
"%PY%" -m streamlit run app.py --server.headless true --server.port 8501
pause
