@echo off
REM Publica los datos de reproceso (Excel -> data/*.parquet -> GitHub -> app web)
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" actualizar_datos.py %*
pause
