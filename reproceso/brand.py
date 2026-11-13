"""Identidad corporativa Ingenio Sancarlos (skill boletines-sancarlos).

Verde #267939 · Naranja #D35E13 · Gris #6D6E71 · Century Gothic.
Los colores corporativos van en la estructura de la página (cintilla, títulos, badge,
pie); las series de las gráficas conservan la paleta validada para daltonismo.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import os

import pandas as pd
import streamlit as st

from . import ui

VERDE = "#267939"
NARANJA = "#D35E13"
GRIS = "#6D6E71"
GRIS_CLARO = "#F5F5F2"
NARANJA_CLARO = "#FDF1E8"
FONT = '"Century Gothic", "URW Gothic", "Avant Garde", sans-serif'
AREA = "Aseguramiento de Calidad"

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "logo_sancarlos.png")


@st.cache_data
def _logo_b64() -> str | None:
    if not os.path.exists(LOGO_PATH):
        return None
    with open(LOGO_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


FONT_STEPS = [0.85, 0.92, 1.0, 1.1, 1.2, 1.32, 1.45]


def font_scale() -> float:
    return st.session_state.get("font_scale", 1.0)


def _set_scale(delta: int | None):
    s = font_scale()
    if delta is None:
        st.session_state["font_scale"] = 1.0
        return
    i = min(range(len(FONT_STEPS)), key=lambda k: abs(FONT_STEPS[k] - s))
    st.session_state["font_scale"] = FONT_STEPS[max(0, min(len(FONT_STEPS) - 1, i + delta))]


def font_controls():
    """Botones A− / A / A+ para cambiar el tamaño de letra de toda la app."""
    st.markdown("**Tamaño de letra**")
    c1, c2, c3 = st.columns(3)
    c1.button("A−", on_click=_set_scale, args=(-1,), **ui.WIDE, help="Disminuir letra",
              disabled=font_scale() <= FONT_STEPS[0])
    c2.button("A", on_click=_set_scale, args=(None,), **ui.WIDE, help="Tamaño normal")
    c3.button("A+", on_click=_set_scale, args=(1,), **ui.WIDE, help="Aumentar letra",
              disabled=font_scale() >= FONT_STEPS[-1])
    st.caption(f"Tamaño actual: {round(font_scale() * 100)} %")


def inject_css():
    scale = font_scale()
    st.markdown(f"""
<style>
html {{ font-size: {16 * scale:.1f}px !important; }}
html, body, [class*="st-"], .stMarkdown, .stMetric, button, input, textarea, select,
[data-testid="stSidebar"], [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
  font-family: {FONT} !important;
}}
/* conservar la fuente de íconos de Streamlit */
[data-testid="stIconMaterial"], .material-symbols-rounded {{ font-family: "Material Symbols Rounded" !important; }}
h1, h2, h3 {{ color: {VERDE} !important; font-family: {FONT} !important; }}
h1 {{ font-size: 1.7rem !important; }}
h3 {{ border-bottom: 2px solid {VERDE}; padding-bottom: .2rem; font-size: 1.2rem !important; }}
[data-testid="stMetricValue"] {{ font-size: 1.6rem; }}
[data-testid="stMetricLabel"] p {{ color: {GRIS}; }}
[data-testid="stMetricLabel"] span[role="img"] {{ color: {VERDE}; font-size: 1.45em !important;
  font-family: "Material Symbols Rounded" !important; vertical-align: -0.3em !important;
  margin-right: .2em; font-variation-settings: "FILL" 0, "wght" 300; }}
/* etiquetas de las tarjetas: que bajen de línea en vez de cortarse con «…» */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] div, [data-testid="stMetricLabel"] p {{
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
  height: auto !important; }}
[data-testid="stMetricLabel"] p {{ line-height: 1.25; }}
.block-container {{ padding-top: 3.6rem; }}

.isc-band {{ display:flex; align-items:stretch; border-radius:6px; overflow:hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,.08); margin-bottom: .8rem; }}
.isc-logo {{ background:#ffffff; padding:6px 18px; display:flex; align-items:center; }}
.isc-logo img {{ height:58px; }}
.isc-mid {{ background:{VERDE}; color:#fff; flex:1; padding:10px 20px; display:flex;
  flex-direction:column; justify-content:center; }}
.isc-mid .t1 {{ font-size:1.25rem; font-weight:700; letter-spacing:.2px; }}
.isc-mid .t2 {{ font-size:.85rem; opacity:.92; }}
.isc-badge-wrap {{ background:{VERDE}; display:flex; align-items:center; padding:0 18px; }}
.isc-badge {{ background:{NARANJA}; color:#fff; font-weight:700; text-transform:uppercase;
  font-size:.8rem; padding:6px 14px; border-radius:3px; letter-spacing:.5px; white-space:nowrap; }}
.isc-footer {{ background:{VERDE}; color:#fff; display:flex; justify-content:space-between;
  flex-wrap:wrap; gap:8px; padding:10px 18px; border-radius:6px; margin-top:2rem; font-size:.8rem; }}
.isc-footer b {{ letter-spacing:.3px; }}
.isc-note {{ background:{GRIS_CLARO}; border-left:5px solid {NARANJA}; padding:10px 14px;
  border-radius:4px; color:#1a1a1a; font-size:.9rem; margin:.4rem 0 .8rem 0; }}
.isc-risk {{ background:{NARANJA_CLARO}; border:2px solid {NARANJA}; padding:10px 14px;
  border-radius:4px; color:#1a1a1a; font-size:.9rem; margin:.4rem 0 .8rem 0; }}
.isc-update {{ display:flex; flex-wrap:wrap; gap:6px 18px; align-items:center; font-size:.85rem;
  color:{GRIS}; margin:-.3rem 0 .9rem 0; }}
.isc-update b {{ color:{VERDE}; }}
.isc-update .chip {{ background:{GRIS_CLARO}; border-left:4px solid {NARANJA}; padding:3px 10px;
  border-radius:3px; }}
@media (max-width: 640px) {{
  .isc-badge-wrap {{ display:none; }}
  .isc-logo img {{ height:42px; }}
}}
</style>""", unsafe_allow_html=True)


def header(titulo: str, subtitulo: str = "", badge: str = "PPR Reproceso"):
    logo = _logo_b64()
    logo_html = (f'<img src="data:image/png;base64,{logo}" alt="Ingenio Sancarlos">' if logo
                 else f'<b style="color:{VERDE}">INGENIO SANCARLOS</b>')
    st.markdown(f"""
<div class="isc-band">
  <div class="isc-logo">{logo_html}</div>
  <div class="isc-mid"><div class="t1">{html.escape(titulo)}</div>
    <div class="t2">{html.escape(subtitulo)}</div></div>
  <div class="isc-badge-wrap"><span class="isc-badge">{html.escape(badge)}</span></div>
</div>""", unsafe_allow_html=True)
    update_line()


def _f(ts, hora=True) -> str:
    if ts is None or pd.isna(ts):
        return "—"
    return pd.Timestamp(ts).strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y")


def update_line():
    """Mensaje con la fecha de la última actualización de los datos."""
    info = st.session_state.get("_ctx", {}).get("actualizacion")
    if not info:
        return
    partes = [f'<span class="chip">🕒 <b>Última actualización de datos:</b> {_f(info["excel_modificado"])}'
              + (f' · {html.escape(info["archivo"])}' if info.get("archivo") else "") + "</span>",
              f'<span>Último movimiento registrado: <b>{_f(info["ultimo_movimiento"], False)}</b></span>']
    if info.get("publicado") is not None:
        partes.append(f'<span>Publicado en la web: {_f(info["publicado"])}</span>')
    st.markdown(f'<div class="isc-update">{"".join(partes)}</div>', unsafe_allow_html=True)


def note(texto_md: str, risk: bool = False):
    """Caja gris (resumen) o naranja claro (impacto/riesgo). Acepta HTML simple."""
    st.markdown(f'<div class="{"isc-risk" if risk else "isc-note"}">{texto_md}</div>',
                unsafe_allow_html=True)


def footer():
    hoy = dt.date.today()
    st.markdown(f"""
<div class="isc-footer"><span><b>INGENIO SANCARLOS</b> · {AREA}</span>
<span>Uso interno · Trazabilidad del PPR de reproceso · {hoy:%Y-%m-%d}</span></div>""",
                unsafe_allow_html=True)
