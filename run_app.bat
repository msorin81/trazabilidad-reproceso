@echo off
REM Inicia la aplicacion de trazabilidad de reproceso (Ingenio Sancarlos)
REM No cierres esta ventana mientras uses la app.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
REM El navegador se abre solo cuando la app ya responde (espera hasta 90 s)
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 90;$i++){try{Invoke-WebRequest 'http://localhost:8501/_stcore/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process 'http://localhost:8501'; break}catch{Start-Sleep -Seconds 1}}"
echo Iniciando la app... el navegador se abrira en unos segundos.
"%PY%" -m streamlit run app.py --server.headless true --server.port 8501
pause
