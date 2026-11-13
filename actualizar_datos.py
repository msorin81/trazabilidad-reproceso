"""Publica los datos de reproceso para la versión web de la app.

1. Lee los libros «AAAA-Stock-Reproceso.xlsm» (hojas 1–12) de la carpeta de OneDrive.
2. Guarda una instantánea limpia en app_reproceso/data/ (parquet + metadata.json con la fecha).
3. Si la carpeta es un repositorio git, hace commit y push → Streamlit Cloud se actualiza solo.

Uso:  python actualizar_datos.py            (o doble clic en actualizar_datos.bat)
      python actualizar_datos.py --sin-push  (solo genera la instantánea)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from reproceso import data as D  # noqa: E402

DATA_DIR = os.environ.get("REPROCESO_DATA_DIR", os.path.dirname(APP_DIR))
SNAP_DIR = os.path.join(APP_DIR, "data")


def _git() -> str | None:
    cand = [shutil.which("git"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Git", "cmd", "git.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "cmd", "git.exe")]
    return next((c for c in cand if c and os.path.exists(c)), None)


def main():
    print(f"Leyendo Excel en: {DATA_DIR}")
    datos = D.load_all(DATA_DIR)
    if datos["traz"].empty:
        sys.exit("ERROR: no se leyeron registros. ¿Están los archivos .xlsm en la carpeta?")
    meta = D.export_snapshot(datos, DATA_DIR, SNAP_DIR)
    print(f"Instantánea guardada en {SNAP_DIR}")
    print(f"  {meta['registros_trazabilidad']} registros de trazabilidad · {meta['registros_tiquetes']} tiquetes")
    print(f"  Último movimiento registrado: {meta['ultimo_movimiento']}")
    for a in meta["avisos"]:
        print("  AVISO:", a)

    if "--sin-push" in sys.argv:
        return
    git = _git()
    if not git or not os.path.isdir(os.path.join(APP_DIR, ".git")):
        print("\n(git no está configurado: la instantánea quedó solo en este equipo)")
        return
    run = lambda *a: subprocess.run([git, *a], cwd=APP_DIR, check=False)  # noqa: E731
    run("add", "data")
    r = run("commit", "-m", f"Actualización de datos {meta['publicado']}")
    if r.returncode == 0:
        p = run("push")
        print("\nPublicado en GitHub ✔ (la app web se actualiza en 1–2 minutos)" if p.returncode == 0
              else "\nERROR al hacer push. Revisa la conexión o las credenciales de GitHub.")
    else:
        print("\nNo hubo cambios en los datos desde la última publicación.")


if __name__ == "__main__":
    main()
