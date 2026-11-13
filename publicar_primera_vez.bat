@echo off
REM ============================================================================
REM  Primera publicacion de la app en GitHub (ejecutar UNA sola vez).
REM  Requisitos: Git instalado y el repositorio VACIO creado en
REM  https://github.com/msorin81/trazabilidad-reproceso  (publico, sin README)
REM ============================================================================
cd /d "%~dp0"
setlocal
set "REPO=https://github.com/msorin81/trazabilidad-reproceso.git"

REM Git instalado solo para el usuario (sin permisos de administrador)
if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%PATH%"
where git >nul 2>nul
if errorlevel 1 (
  echo No se encontro Git. Instala Git for Windows: https://git-scm.com/download/win
  pause & exit /b 1
)

REM Nombre y correo para los commits (solo si no estan configurados)
git config --global user.name >nul 2>nul || (
  set /p GNAME=Tu nombre para GitHub:
  call git config --global user.name "%%GNAME%%"
)
git config --global user.email >nul 2>nul || (
  echo Usa tu correo "noreply" de GitHub ^(github.com/settings/emails^) para no exponer tu correo.
  set /p GMAIL=Correo para los commits:
  call git config --global user.email "%%GMAIL%%"
)

REM 1. Datos al dia (sin nombres de personas)
set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" actualizar_datos.py --sin-push || (pause & exit /b 1)

REM 2. Repositorio local y primer envio
if not exist ".git" git init -b main
git add .
git commit -m "Primera version de la app de trazabilidad de reproceso"
git remote get-url origin >nul 2>nul || git remote add origin %REPO%
git push -u origin main
if errorlevel 1 (
  echo.
  echo ERROR al subir. Verifica que el repositorio exista y este vacio, y que iniciaste sesion en GitHub.
) else (
  echo.
  echo Listo. Ahora despliega la app en https://share.streamlit.io  (ver README.md, paso 3^)
)
pause
