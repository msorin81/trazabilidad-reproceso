"""Control y visualización del PPR de reproceso de azúcar.

Ejecutar:  streamlit run app.py   (o doble clic en run_app.bat)
Los datos se leen de los libros «AAAA-Stock-Reproceso.xlsm» (hojas 1–12) de la carpeta
indicada en la variable de entorno REPROCESO_DATA_DIR o, por defecto, la carpeta padre.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st


def _recargar_modulos_cambiados():
    """Streamlit Cloud actualiza el código con cada push sin reiniciar el proceso: las páginas usan el código
    nuevo, pero los módulos de reproceso/ ya importados se quedaban en la versión vieja. Se recargan los que
    cambiaron (o los que vienen de una versión sin marca de carga), en orden de dependencias."""
    import importlib
    import sys
    for nombre in ("reproceso.data", "reproceso.inventario", "reproceso.vinculos", "reproceso.ui",
                   "reproceso.brand", "reproceso.plano", "reproceso.escritura"):
        m = sys.modules.get(nombre)
        if m is None or not getattr(m, "__file__", None):
            continue
        try:
            viejo = os.path.getmtime(m.__file__) > getattr(m, "_CARGADO", 0)
        except OSError:
            continue
        if viejo:
            importlib.reload(m)


_recargar_modulos_cambiados()

from reproceso import brand  # noqa: E402
from reproceso import escritura as E  # noqa: E402
from reproceso import data as D
from reproceso import ui

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("REPROCESO_DATA_DIR", os.path.dirname(APP_DIR))
SNAP_DIR = os.path.join(APP_DIR, "data")
ICON = brand.LOGO_PATH

st.set_page_config(page_title="Trazabilidad reproceso · Ingenio Sancarlos",
                   page_icon=ICON if os.path.exists(ICON) else "🍬", layout="wide")
brand.inject_css()


@st.cache_data(show_spinner="Leyendo libros de reproceso…")
def _load(data_dir: str, signature: tuple):  # signature invalida la caché si cambia un archivo
    return D.load_all(data_dir)


def _publicar_web() -> tuple[bool, str]:
    """Ejecuta actualizar_datos.py (instantánea + commit + push) y devuelve (ok, salida)."""
    import subprocess
    import sys
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable, os.path.join(APP_DIR, "actualizar_datos.py")], cwd=APP_DIR,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                           timeout=300, creationflags=0x08000000 if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        return False, "Se superó el tiempo de espera (5 min)."
    return r.returncode == 0, (r.stdout + r.stderr).strip()


@st.cache_data(show_spinner="Leyendo vínculos de tiquetes e inventario físico…")
def _load_extras(data_dir: str, signature: tuple):
    return D.load_extras(data_dir)


@st.cache_data(show_spinner="Cargando datos publicados…")
def _load_snap(snap_dir: str, signature: tuple):
    return D.load_snapshot(snap_dir)


# Origen de datos:
#  · local (equipo con OneDrive): se leen directamente los .xlsm → siempre al día
#  · web (Streamlit Cloud / GitHub): se lee la instantánea data/*.parquet publicada con actualizar_datos.bat
sig = D.files_signature(DATA_DIR)
modo = os.environ.get("REPROCESO_MODO", "excel" if sig else "snapshot")
if modo == "excel" and sig:
    datos = {**_load(DATA_DIR, sig), **_load_extras(DATA_DIR, D.extras_signature(DATA_DIR))}
    info_upd = D.info_actualizacion(datos, DATA_DIR)
elif D.snapshot_exists(SNAP_DIR):
    datos = _load_snap(SNAP_DIR, D.snapshot_signature(SNAP_DIR))
    info_upd = D.info_actualizacion(datos, None)
else:
    st.error(f"No se encontraron archivos «{D.FILE_PATTERN}» en `{DATA_DIR}` ni datos publicados en "
             f"`{SNAP_DIR}`. Ejecuta actualizar_datos.bat en el equipo que tiene los Excel.")
    st.stop()
traz, tiq = datos["traz"], datos["tiq"]

# ---------------------------------------------------------------------------
# Barra lateral: filtros globales
# ---------------------------------------------------------------------------
if os.path.exists(ICON):
    st.logo(ICON)

with st.sidebar:
    brand.font_controls()
    st.divider()
    st.markdown("### Filtros")
    anios = sorted(traz["anio"].unique().tolist())
    sel_anios = st.multiselect("Año", anios, default=[anios[-1]], key="f_anio",
                               placeholder="Todos los años")
    sel_meses = st.multiselect("Mes", list(range(1, 13)), format_func=lambda m: D.MESES_LARGO[m - 1],
                               key="f_mes", placeholder="Todos los meses")
    cats = [c for c in ui.CAT_COLORS if c in traz["categoria"].unique()]
    sel_cats = st.multiselect("Categoría", cats, key="f_cat", placeholder="Todas")
    with st.expander("Más filtros"):
        sel_tipo = st.multiselect("Tipo de azúcar", sorted(traz["tipo_azucar"].unique()), key="f_tipo",
                                  placeholder="Todos")
        sel_pres = st.multiselect("Presentación (kg)", sorted(traz["presentacion_kg"].unique(),
                                                              key=lambda x: (not x.isdigit(), x.zfill(6))),
                                  key="f_pres", placeholder="Todas")
        sel_cod = st.multiselect("Código de producto", sorted(traz["codigo"].unique()), key="f_cod",
                                 placeholder="Todos")
    st.divider()
    if modo == "excel":
        if st.button("🔄 Recargar datos", **ui.WIDE,
                     help="Vuelve a leer los archivos de Excel (úsalo después de actualizarlos)."):
            st.cache_data.clear()
            st.rerun()
        with st.expander("🌐 Actualizar la app web", expanded=False):
            st.caption("Lee los Excel guardados y publica los cambios en GitHub. "
                       "La app web se actualiza 1–2 minutos después. Guarda y cierra los Excel antes.")
            if st.button("Publicar ahora", key="btn_publicar", type="primary", **ui.WIDE):
                with st.spinner("Leyendo Excel y publicando…"):
                    ok, salida = _publicar_web()
                st.session_state["_pub_res"] = (ok, salida)
            if "_pub_res" in st.session_state:
                ok, salida = st.session_state["_pub_res"]
                if not ok:
                    st.error("No se pudo publicar. Revisa el detalle.")
                elif "Sin cambios" in salida or "No hubo cambios" in salida:
                    st.info("No hay cambios desde la última publicación.")
                else:
                    st.success("Publicado ✔. La web se actualiza en 1–2 minutos.")
                st.code(salida or "(sin salida)", language=None)
    else:
        st.caption("ℹ️ Esta versión se actualiza sola todos los días a las 6:00 p. m. "
                   "y cada vez que se publica desde la app local.")
    st.caption(("Fuente: archivos Excel (OneDrive)" if modo == "excel" else "Fuente: datos publicados") +
               f"  \n{len(traz):,} registros de trazabilidad · {len(tiq):,} tiquetes".replace(",", "."))
    todos_avisos = datos["avisos"] + datos.get("extra_avisos", [])
    if todos_avisos:
        with st.expander(f"⚠️ {len(todos_avisos)} avisos de lectura"):
            for a in todos_avisos:
                st.caption(a)


def _apply(df, cols_filters):
    m = None
    for col, sel in cols_filters:
        if sel:
            cond = df[col].isin(sel)
            m = cond if m is None else (m & cond)
    return df if m is None else df[m]


traz_dim = _apply(traz, [("categoria", sel_cats), ("tipo_azucar", sel_tipo), ("presentacion_kg", sel_pres),
                         ("codigo", sel_cod)])
traz_f = _apply(traz_dim, [("anio", sel_anios), ("mes", sel_meses)])
tiq_f = _apply(tiq, [("anio", sel_anios), ("mes", sel_meses)])

st.session_state["_ctx"] = {
    "traz": traz, "tiq": tiq, "traz_f": traz_f, "tiq_f": tiq_f, "traz_dim": traz_dim,
    "actualizacion": info_upd, "modo": modo,
    "filtros_traz_extra": bool(sel_cats or sel_tipo or sel_pres or sel_cod),
    "anios": sel_anios, "meses": sel_meses,
    **{k: datos.get(k, pd.DataFrame()) for k in ("vinculos", "inv", "inv_leyenda", "inv_zonas")},
    "data_dir": DATA_DIR, "app_dir": APP_DIR,
}

# ---------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------
V = os.path.join(APP_DIR, "views")
import inspect  # noqa: E402

# Menú completo (sin «View more») en las versiones de Streamlit que lo permiten
NAV_EXTRA = {"expanded": True} if "expanded" in inspect.signature(st.navigation).parameters else {}
pg = st.navigation(**NAV_EXTRA, pages={
    "Seguimiento": [
        st.Page(os.path.join(V, "resumen.py"), title="Resumen", icon="🏠", default=True),
        st.Page(os.path.join(V, "ingreso.py"), title="Ingreso por mes", icon="📥", url_path="ingreso"),
        st.Page(os.path.join(V, "stock.py"), title="Stock fin de mes", icon="📦", url_path="stock_fin_mes"),
        st.Page(os.path.join(V, "disolucion.py"), title="Disolución", icon="💧", url_path="disolucion"),
        st.Page(os.path.join(V, "reproceso_dia.py"), title="Reproceso por día", icon="📅",
                url_path="reproceso_dia"),
        st.Page(os.path.join(V, "indicadores.py"), title="Indicadores (Power BI)", icon="📊",
                url_path="indicadores"),
    ],
    "Bodega": [
        st.Page(os.path.join(V, "inventario.py"), title="Inventario físico", icon="🏭", url_path="inventario"),
        *([st.Page(os.path.join(V, "registrar_conteo.py"), title="Registrar conteo", icon="✏️",
                   url_path="registrar_conteo")] if modo == "excel" and E.disponible() else []),
    ],
    "Control": [
        st.Page(os.path.join(V, "tiquetes.py"), title="Físico vs tiquete", icon="⚖️", url_path="tiquetes"),
        st.Page(os.path.join(V, "traz_tiquete.py"), title="Trazabilidad por tiquete", icon="🔗",
                url_path="trazabilidad_tiquete"),
        st.Page(os.path.join(V, "buscar.py"), title="Buscar estiba / tiquete", icon="🔎", url_path="buscar"),
        st.Page(os.path.join(V, "calidad.py"), title="Calidad de datos", icon="🩺", url_path="calidad"),
    ],
})
pg.run()
brand.footer()
