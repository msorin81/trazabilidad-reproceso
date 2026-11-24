"""Plano físico interactivo de una zona de la bodega (estibas con los colores del Excel)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import time as _time
_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia (Streamlit Cloud)

from . import ui
from .inventario import nombre_color_texto

TINTA, GRIS_LINEA, VACIO = "#1A1A1A", "#C9CACC", "#F5F5F2"
MARCA_TEXTO = {"naranja": "#E46C0A", "amarillo": "#D4A800", "rojo": "#C00000"}


def _hex(h) -> str:
    return f"#{h}" if isinstance(h, str) and not h.startswith("#") else (h or "#FFFFFF")


def _texto_oscuro(hex6: str) -> str:
    h = hex6.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return TINTA if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45 else "#FFFFFF"


def figura(est: pd.DataFrame, zona_meta: dict, compacto: bool, resaltar: set[str] | None = None) -> go.Figure:
    """est: estibas de UNA zona y UNA fecha (con columnas de trazabilidad opcionales).
    zona_meta: {"bloques": n, "niveles": h, "columnas": [etiquetas…]} tal como están en el Excel."""
    n_b, niv = int(zona_meta["bloques"]), int(zona_meta["niveles"])
    etiquetas = [str(x) for x in zona_meta["columnas"]]
    n_c = len(etiquetas)
    alto_bloque = 40 if compacto else 16 * niv + 12
    fig = go.Figure()
    shapes, ann = [], []
    pad, alto_util = 0.06, 0.86

    # posiciones vacías (estructura física de la carpa)
    for b in range(1, n_b + 1):
        for c in range(n_c):
            shapes.append(dict(type="rect", x0=c + pad, x1=c + 1 - pad, y0=b - 1 + 0.07, y1=b - 1 + 0.07 + alto_util,
                               line=dict(color=GRIS_LINEA, width=1, dash="dot"), fillcolor=VACIO, layer="below"))

    alto_slot = alto_util / niv
    xs, ys, hover, idx = [], [], [], []
    marcas_x, marcas_y, marcas_c = [], [], []
    for i, r in est.iterrows():
        if pd.isna(r["col_pos"]) or pd.isna(r["bloque"]):
            continue
        c, b, nv = int(r["col_pos"]), int(r["bloque"]), int(r["nivel"] if pd.notna(r["nivel"]) else 0)
        nv = min(nv, niv - 1)
        y0 = b - 1 + 0.07 + nv * alto_slot
        col = _hex(r["color"])
        borde = dict(color=TINTA, width=3) if resaltar and r["estiba"] in resaltar else dict(color="#FFFFFF", width=1)
        shapes.append(dict(type="rect", x0=c + pad, x1=c + 1 - pad, y0=y0, y1=y0 + alto_slot,
                           fillcolor=col, line=borde, layer="below"))  # debajo de las marcas y del hover
        if not compacto:
            ann.append(dict(x=c + 0.5, y=y0 + alto_slot / 2, text=r["texto"].replace("'", ""), showarrow=False,
                            font=dict(size=round(10 * ui._scale()), color=_texto_oscuro(col)), xanchor="center",
                            yanchor="middle"))
        tx = nombre_color_texto(r.get("color_texto"))
        if tx:
            marcas_x.append(c + 1 - pad - 0.06); marcas_y.append(y0 + alto_slot / 2)
            marcas_c.append(MARCA_TEXTO.get(tx, TINTA))
        info = [f"<b>Estiba {r['estiba']}</b> · {ui.fnum(r['qq'])} qq",
                f"{r['condicion']}",
                f"Bloque {b} · columna {etiquetas[c] if c < n_c else c + 1} · nivel {nv + 1} (celda {r['celda']})"]
        if tx:
            info.append(f"Texto en {tx} en el Excel")
        if isinstance(r.get("t_categoria"), str):
            info.append(f"Trazabilidad: {r['t_categoria']} · {r.get('t_causa') or 's. d.'}")
            if pd.notna(r.get("t_dias")):
                linea = f"{ui.fnum(r['t_dias'], 0)} días en stock"
                if pd.notna(r.get("t_ingreso")):
                    linea += f" · ingreso {pd.Timestamp(r['t_ingreso']):%Y-%m-%d}"
                info.append(linea)
        elif "t_categoria" in est.columns:
            info.append("<i>No está en el stock «Cuantificado» de la trazabilidad</i>")
        xs.append(c + 0.5); ys.append(y0 + alto_slot / 2); hover.append("<br>".join(info)); idx.append(i)

    fig.add_scatter(x=xs, y=ys, mode="markers", customdata=idx, hovertext=hover, hoverinfo="text",
                    marker=dict(symbol="square", size=18, color="rgba(0,0,0,0)"), showlegend=False,
                    name="estibas")
    if marcas_x:
        fig.add_scatter(x=marcas_x, y=marcas_y, mode="markers", hoverinfo="skip", showlegend=False,
                        marker=dict(symbol="triangle-left", size=8, color=marcas_c,
                                    line=dict(color="#FFFFFF", width=1)))
    # total por posición (a la derecha del número de bloque no cabe: va como etiqueta en el eje y)
    tot_b = est.groupby("bloque")["qq"].sum()
    fig.update_layout(shapes=shapes, annotations=ann, height=max(260, n_b * alto_bloque + 80),
                      margin=dict(l=8, r=8, t=30, b=8), plot_bgcolor="#FFFFFF", hovermode="closest",
                      dragmode="select", clickmode="event+select")
    ui.style(fig, height=max(260, n_b * alto_bloque + 80), legend=False, ytitle=None)
    fig.update_xaxes(range=[0, n_c], tickvals=[c + 0.5 for c in range(n_c)], ticktext=etiquetas, side="top",
                     showgrid=False, zeroline=False, fixedrange=True, title=None)
    fig.update_yaxes(range=[n_b, 0], tickvals=[b - 0.5 for b in range(1, n_b + 1)],
                     ticktext=[f"<b>{b}</b>  {ui.fnum(tot_b.get(b, 0))} qq" if tot_b.get(b, 0) else f"<b>{b}</b>"
                               for b in range(1, n_b + 1)],
                     showgrid=False, zeroline=False, fixedrange=True, title=None)
    return fig
