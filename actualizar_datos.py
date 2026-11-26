"""Publica los datos de reproceso para la versión web de la app.

1. Lee los libros «AAAA-Stock-Reproceso.xlsm» (hojas 1–12) de la carpeta de OneDrive.
2. Guarda una instantánea limpia en app_reproceso/data/ (parquet + metadata.json con la fecha).
   Si los datos no cambiaron desde la última publicación, no hace nada.
3. Si la carpeta es un repositorio git, hace commit y push → Streamlit Cloud se actualiza solo.

Uso:  python actualizar_datos.py            (o doble clic en actualizar_datos.bat)
      python actualizar_datos.py --sin-push  (solo genera la instantánea)
      pythonw actualizar_datos.py --auto     (tarea programada: sin ventana, registro en logs/)
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

DATA_DIR = os.environ.get("REPROCESO_DATA_DIR", os.path.dirname(APP_DIR))
SNAP_DIR = os.path.join(APP_DIR, "data")
LOG_DIR = os.path.join(APP_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "actualizacion_auto.log")
AUTO = "--auto" in sys.argv
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: git sin ventanas en modo auto


def _setup_log():
    """En modo automático todo lo que se imprime va a logs/actualizacion_auto.log (últimas ~1000 líneas)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-1000:]
        with open(LOG_FILE, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
    fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = fh
    print(f"\n===== {dt.datetime.now():%Y-%m-%d %H:%M:%S} · actualización automática =====")


def _git() -> str | None:
    cand = [shutil.which("git"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "cmd", "git.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Git", "cmd", "git.exe")]
    return next((c for c in cand if c and os.path.exists(c)), None)


def _paso(texto: str):
    """En modo automático deja la hora de cada paso: si Windows corta la tarea se sabe dónde quedó."""
    if AUTO:
        print(f"  [{dt.datetime.now():%H:%M:%S}] {texto}")


def main() -> int:
    _paso("importando módulos")
    from reproceso import data as D

    print(f"Leyendo Excel en: {DATA_DIR}")
    datos = D.load_all(DATA_DIR)
    _paso("libros de stock leídos; leyendo vínculos e inventario")
    if datos["traz"].empty:
        print("ERROR: no se leyeron registros. ¿Están los archivos .xlsm en la carpeta?")
        return 1
    datos.update(D.load_extras(DATA_DIR))  # vínculos PDF por tiquete + inventario físico
    fallidos = [a for a in datos["avisos"] + datos.get("extra_avisos", []) if "no se pudo leer" in a.lower()]
    if fallidos:
        # nunca publicar datos incompletos (p. ej. un libro bloqueado dejaría la web sin ese año)
        print("ERROR: no se publica porque no se pudieron leer todos los libros:")
        for a in fallidos:
            print("  ", a)
        return 4
    if not datos["inv"].empty:
        print(f"Inventario físico: {datos['inv']['fecha'].nunique()} pestañas, "
              f"última {datos['inv']['fecha'].max():%Y-%m-%d}")
    _paso("generando instantánea")
    meta = D.export_snapshot(datos, DATA_DIR, SNAP_DIR, solo_si_cambia=True)
    if meta is None:
        print("Sin cambios en los Excel desde la última instantánea.")
    else:
        print(f"Instantánea guardada en {SNAP_DIR}")
        print(f"  {meta['registros_trazabilidad']} registros de trazabilidad · {meta['registros_tiquetes']} tiquetes")
        print(f"  Último movimiento registrado: {meta['ultimo_movimiento']}")
        for a in meta["avisos"]:
            print("  AVISO:", a)

    if "--sin-push" in sys.argv:
        return 0
    git = _git()
    if not git or not os.path.isdir(os.path.join(APP_DIR, ".git")):
        print("\n(git no está configurado: la instantánea quedó solo en este equipo)")
        return 0

    # git nunca debe quedarse esperando una respuesta (credenciales, etc.): falla rápido y queda en el registro
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")

    def run(*a, mostrar=True):
        _paso(f"git {a[0]}")
        try:
            r = subprocess.run([git, *a], cwd=APP_DIR, capture_output=True, text=True, env=env, timeout=180,
                               encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            print(f"ERROR: «git {a[0]}» no respondió en 3 minutos (¿sin conexión o pidiendo credenciales?).")
            return 1, ""
        out = (r.stdout + r.stderr).strip()
        if out and mostrar:
            print(out)
        return r.returncode, out

    # se publica también una instantánea que quedó pendiente (p. ej. generada antes con --sin-push)
    run("add", "data")
    pendiente = run("status", "--porcelain", "data", mostrar=False)[1]
    if pendiente:
        cuando = meta["publicado"] if meta else dt.datetime.now().isoformat(timespec="minutes")
        run("commit", "-m", f"Actualización de datos {cuando}")
    adelante = run("rev-list", "--count", "@{u}..HEAD", mostrar=False)[1]
    if not pendiente and adelante in ("", "0"):
        print("\nNada pendiente por publicar: la web ya tiene estos datos.")
        return 0
    if run("push")[0] == 0:
        print("\nPublicado en GitHub ✔ (la app web se actualiza en 1–2 minutos)")
        return 0
    print("\nERROR al hacer push. Revisa la conexión o las credenciales de GitHub.")
    return 2


if __name__ == "__main__":
    if AUTO:
        _setup_log()
    try:
        code = main()
    except Exception as e:  # en modo auto el error debe quedar en el registro
        import traceback
        traceback.print_exc()
        print(f"ERROR inesperado: {e}")
        code = 3
    sys.exit(code)
