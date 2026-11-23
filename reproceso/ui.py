"""Componentes compartidos: paleta, formatos, filtros globales y ayudas de gráficos."""
from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import data as D

# ---------------------------------------------------------------------------
# Paleta (paleta de referencia validada para daltonismo; el color sigue a la entidad)
# ---------------------------------------------------------------------------
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
GRAY = "#898781"

CAT_COLORS = {"No conforme": BLUE, "Avería": ORANGE, "Barredura": AQUA,
              "Rechazado": YELLOW, "(Sin dato)": GRAY}
FLOW_COLORS = {"Ingreso": BLUE, "Disolución": ORANGE, "Stock fin de mes": AQUA}
AGING_ORDER = ["0–30 días", "31–60 días", "61–90 días", "> 90 días"]
AGING_COLORS = dict(zip(AGING_ORDER, ["#86b6ef", "#3987e5", "#256abf", "#104281"]))
STATUS = {"ok": ("✅", "#0ca30c"), "warn": ("⚠️", "#fab219"), "crit": ("⛔", "#d03b3b")}


def _st_version() -> tuple:
    try:
        return tuple(int(x) for x in st.__version__.split(".")[:2])
    except ValueError:
        return (1, 0)


# Ancho completo compatible: Streamlit ≥1.46 usa width="stretch"; versiones previas, use_container_width
WIDE = {"width": "stretch"} if _st_version() >= (1, 46) else {"use_container_width": True}


def cat_color(cat: str) -> str:
    return CAT_COLORS.get(cat, GRAY)


# ---------------------------------------------------------------------------
# Formatos (es-CO: punto de miles, coma decimal)
# ---------------------------------------------------------------------------
def fnum(x, dec: int = 1) -> str:
    if x is None or pd.isna(x):
        return "—"
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fpct(x, dec: int = 1) -> str:
    return "—" if x is None or pd.isna(x) else fnum(100 * x, dec) + " %"


def aging_bucket(dias: pd.Series) -> pd.Series:
    return pd.cut(dias, bins=[-1, 30, 60, 90, 10**6], labels=AGING_ORDER)


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def style(fig: go.Figure, height: int = 380, legend: bool = True, ytitle: str | None = "Quintales",
          xtitle: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36 if legend else 12, b=8),
        separators=",.",
        barcornerradius=4,
        bargap=0.28,
        hovermode="x unified" if fig.data and fig.data[0].type in ("scatter",) else "closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="",
                    traceorder="normal"),
        showlegend=legend,
        font=dict(family="'Century Gothic', 'URW Gothic', 'Avant Garde', sans-serif",
                  size=round(12 * _scale())),
        # etiquetas: se ocultan solas si no caben dentro de la barra
        uniformtext=dict(minsize=max(8, round(9 * _scale())), mode="hide"),
    )
    fig.update_traces(selector=dict(type="bar"), textfont_size=round(11 * _scale()), cliponaxis=False)
    fig.update_traces(selector=dict(type="scatter"), textfont_size=round(11 * _scale()), cliponaxis=False)
    fig.update_xaxes(showgrid=False, title_text=xtitle)
    fig.update_yaxes(gridwidth=1, title_text=ytitle, rangemode="tozero", tickformat=",.0f")
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    fig.update_traces(selector=dict(type="scatter"), line_width=2)
    return fig


def _scale() -> float:
    return st.session_state.get("font_scale", 1.0)


def add_totals(fig: go.Figure, x, totals, horizontal=False, dec=0):
    """Etiqueta del total encima de barras apiladas (texto en tinta neutra, no en color de serie)."""
    x, totals = list(x), list(totals)
    txt = [fnum(t, dec) if t else "" for t in totals]
    if horizontal:
        fig.add_scatter(y=x, x=totals, mode="text", text=txt, textposition="middle right",
                        showlegend=False, hoverinfo="skip")
    else:
        fig.add_scatter(x=x, y=totals, mode="text", text=txt, textposition="top center",
                        showlegend=False, hoverinfo="skip")
    return fig


def headroom(fig: go.Figure, vmax: float, factor=1.15):
    fig.update_yaxes(range=[0, (vmax or 1) * factor])
    return fig


def show(fig: go.Figure, key: str | None = None):
    st.plotly_chart(fig, **WIDE, config={"displaylogo": False}, key=key)


def month_axis(fig: go.Figure):
    """Eje de meses con etiquetas en español (Plotly solo trae nombres en inglés)."""
    xs = set()
    for tr in fig.data:
        if tr.x is not None:
            xs.update(pd.Timestamp(x).normalize().replace(day=1) for x in tr.x)
    if not xs:
        return fig
    meses = sorted(xs)
    paso = 1 if len(meses) <= 18 else (3 if len(meses) <= 48 else 6)
    first = pd.date_range(meses[0], meses[-1], freq="MS")
    ticks = [m for i, m in enumerate(first) if i % paso == 0]
    fig.update_xaxes(tickvals=ticks, ticktext=[D.periodo_label(m) for m in ticks])
    # nombre del mes en español en los tooltips de cada traza
    for tr in fig.data:
        if tr.x is not None and len(tr.x):
            labels = [D.periodo_label(x) for x in tr.x]
            ht = tr.hovertemplate or ""
            if "%{x|%b %Y}" in ht:
                tr.customdata = labels if tr.customdata is None else tr.customdata
                if tr.customdata is not None and list(tr.customdata) == labels:
                    tr.hovertemplate = ht.replace("%{x|%b %Y}", "%{customdata}")
    if fig.layout.hovermode == "x unified":
        fig.update_xaxes(hoverformat="%m/%Y")
    return fig


def _span_months(fig) -> int:
    xs = []
    for tr in fig.data:
        if tr.x is not None and len(tr.x):
            xs += [pd.Timestamp(min(tr.x)), pd.Timestamp(max(tr.x))]
    if not xs:
        return 0
    a, b = min(xs), max(xs)
    return (b.year - a.year) * 12 + b.month - a.month + 1


def stacked_by_category(df: pd.DataFrame, value="qq", x="periodo", title_hover="Quintales",
                        kind="bar") -> go.Figure:
    """Serie mensual apilada por categoría (colores fijos por categoría)."""
    fig = go.Figure()
    g = df.groupby([x, "categoria"], as_index=False)[value].sum()
    order = [c for c in CAT_COLORS if c in g["categoria"].unique()] + \
            [c for c in g["categoria"].unique() if c not in CAT_COLORS]
    for cat in order:
        s = g[g["categoria"] == cat]
        if kind == "bar":
            fig.add_bar(x=s[x], y=s[value], name=cat, marker_color=cat_color(cat),
                        text=s[value], texttemplate="%{y:,.0f}", textposition="inside",
                        insidetextanchor="middle",
                        textfont_color="#0b0b0b" if cat_color(cat) == YELLOW else "#ffffff",
                        hovertemplate=f"%{{x|%b %Y}}<br>{cat}: %{{y:,.1f}} qq<extra></extra>")
        else:
            fig.add_scatter(x=s[x], y=s[value], name=cat, mode="lines", stackgroup="one",
                            line=dict(color=cat_color(cat), width=2),
                            hovertemplate=f"{cat}: %{{y:,.1f}} qq<extra></extra>")
    fig.update_layout(barmode="stack")
    if kind == "bar" and len(order) > 1:
        tot = g.groupby(x)[value].sum()
        if len(tot) <= 24:  # con muchos meses los totales se amontonan; quedan en el tooltip
            add_totals(fig, tot.index, tot.values)
        headroom(fig, tot.max(), 1.12)
    elif kind == "bar":
        headroom(fig, g[value].max(), 1.12)
    return fig


def top_bar(df: pd.DataFrame, dim: str, value="qq", n=15, label: str | None = None,
            by_category=True) -> go.Figure:
    """Barras horizontales Top-N de una dimensión; apiladas por categoría."""
    tot = df.groupby(dim)[value].sum().sort_values(ascending=False)
    top = list(tot.head(n).index)
    d = df.copy()
    if len(tot) > n:
        d[dim] = d[dim].where(d[dim].isin(top), "Otras")
        top.append("Otras")
    fig = go.Figure()
    if dim == "categoria":
        g = d.groupby(dim, as_index=False)[value].sum()
        fig.add_bar(y=g[dim].astype(str), x=g[value], orientation="h",
                    marker_color=[cat_color(x) for x in g[dim]],
                    hovertemplate="%{y}: %{x:,.1f} qq<extra></extra>", showlegend=False)
        by_category = False
    elif by_category:
        g = d.groupby([dim, "categoria"], as_index=False)[value].sum()
        for cat in [c for c in CAT_COLORS if c in g["categoria"].unique()]:
            s = g[g["categoria"] == cat]
            fig.add_bar(y=s[dim].astype(str), x=s[value], name=cat, orientation="h",
                        marker_color=cat_color(cat),
                        hovertemplate=f"%{{y}}<br>{cat}: %{{x:,.1f}} qq<extra></extra>")
        fig.update_layout(barmode="stack")
    else:
        g = d.groupby(dim, as_index=False)[value].sum()
        fig.add_bar(y=g[dim].astype(str), x=g[value], orientation="h", marker_color=BLUE,
                    hovertemplate="%{y}<br>%{x:,.1f} qq<extra></extra>", name=label or dim)
    totals = d.groupby(dim)[value].sum().reindex(top)
    fig.add_scatter(y=[str(t) for t in top], x=totals.values, mode="text",
                    text=[fnum(v) for v in totals.values], textposition="middle right",
                    showlegend=False, hoverinfo="skip", textfont=dict(size=11))
    style(fig, height=max(300, 26 * len(top) + 80), ytitle=None, xtitle="Quintales",
          legend=by_category)
    # eje categórico: los códigos de producto son números y Plotly los ubicaría en un eje numérico
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=[str(t) for t in top][::-1],
                     title_text=None, automargin=True, showgrid=False, tickformat=None, rangemode=None)
    fig.update_xaxes(title_text="Quintales", range=[0, (totals.max() or 1) * 1.3],
                     showgrid=True, tickformat=",.0f", nticks=5, tickangle=0)
    return fig


def pivot_month(df: pd.DataFrame, row: str, value="qq") -> pd.DataFrame:
    """Tabla dinámica fila × mes con total (como las matrices del reporte)."""
    if df.empty:
        return pd.DataFrame()
    p = df.pivot_table(index=row, columns="periodo", values=value, aggfunc="sum", fill_value=0)
    p.columns = [D.periodo_label(c) for c in p.columns]
    p["Total"] = p.sum(axis=1)
    p = p.sort_values("Total", ascending=False)
    p.loc["Total"] = p.sum()
    p.index.name = D.LABELS.get(row, row)
    return p


def show_pivot(p: pd.DataFrame, height: int | None = None):
    if p.empty:
        st.info("Sin datos para los filtros seleccionados.")
        return
    cfg = {c: st.column_config.NumberColumn(c, format="%.1f") for c in p.columns}
    extra = {"height": height} if height else {}  # Streamlit ≥1.4x no acepta height=None
    st.dataframe(p, **WIDE, column_config=cfg, **extra)


# ---------------------------------------------------------------------------
# Tablas y descargas
# ---------------------------------------------------------------------------
def to_excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, f in frames.items():
            f.to_excel(xw, sheet_name=name[:31], index=not isinstance(f.index, pd.RangeIndex))
    return buf.getvalue()


def detail_table(df: pd.DataFrame, cols: list[str], key: str, filename: str, height=420):
    # en la versión web los nombres de personas no se publican: se omiten esas columnas vacías
    cols = [c for c in cols if c in df.columns and not (c in D.PERSONAL_COLS and df[c].isna().all())]
    view = df[cols].rename(columns=D.LABELS)
    cfg = {}
    for c in cols:
        lab = D.LABELS.get(c, c)
        if c.startswith("fecha") and c != "fecha_produccion_txt" or c == "periodo":
            cfg[lab] = st.column_config.DateColumn(lab, format="YYYY-MM-DD" if c != "periodo" else "MMM YYYY")
        elif c in ("qq", "qq_tiquete", "qq_fisico", "qq_enteros", "diferencia"):
            cfg[lab] = st.column_config.NumberColumn(lab, format="%.1f")
    st.dataframe(view, **WIDE, hide_index=True, column_config=cfg, height=height)
    st.download_button("⬇️ Descargar Excel", to_excel_bytes({"datos": view}),
                       file_name=f"{filename}.xlsx", key=f"dl_{key}",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# Íconos minimalistas (Material Symbols, trazo simple) según la métrica.
# Se evalúan en orden: la primera palabra clave que aparezca en la etiqueta define el ícono.
KPI_ICONS = [
    ("cuadran", "check_circle"), ("con diferencia", "rule"), ("sin trazabilidad", "link_off"),
    ("controles críticos", "error"), ("advertencias", "warning"), ("registros revisados", "fact_check"),
    ("día del máximo", "event"), ("días con reproceso", "calendar_month"), ("máximo día", "arrow_upward"),
    ("promedio día", "avg_pace"), ("> 30", "hourglass_bottom"), ("> 60", "hourglass_bottom"),
    ("días prom", "schedule"), ("yoy", "compare_arrows"), ("acumulado", "stacked_line_chart"),
    ("móvil", "show_chart"), ("% stock", "pie_chart"), ("% disolución", "donut_large"),
    ("% diferencia", "percent"), ("diferencia", "difference"), ("qq tiquete", "receipt_long"),
    ("qq físico", "scale"), ("causas", "category"), ("prom. mensual", "functions"),
    ("stock promedio", "functions"), ("stock máximo", "arrow_upward"), ("stock mínimo", "arrow_downward"),
    ("variación", "trending_down"),
    ("estibas", "pallet"), ("stock", "inventory_2"), ("ingreso", "input"),
    ("disuelto", "water_drop"), ("disolución", "water_drop"),
]


def kpi_icon(label: str) -> str | None:
    low = label.lower()
    return next((ic for key, ic in KPI_ICONS if key in low), None)


def kpi(col, label: str, value: str, delta: str | None = None, help: str | None = None,
        delta_color: str = "normal", icon: str | None = None, nota: str | None = None):
    """Tarjeta con ícono. `nota` = texto pequeño bajo el valor (sin flecha, a diferencia de delta)."""
    icon = icon or kpi_icon(label)
    shown = f":material/{icon}: {label}" if icon else label
    with col.container(border=True):
        st.metric(shown, value, delta=delta, help=help, delta_color=delta_color)
        if nota:
            st.caption(nota)


def no_data():
    st.info("No hay datos para los filtros seleccionados. Ajusta los filtros en la barra lateral.")


# ---------------------------------------------------------------------------
# Selección de un rango de meses DENTRO del gráfico → tarjeta flotante con las métricas
# ---------------------------------------------------------------------------
AYUDA_RANGO = "Arrastra sobre el gráfico (o haz clic en una barra o punto) para resumir esos meses."
import time as _time
_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia (Streamlit Cloud)


def ayuda_rango(key: str, activo: bool):
    """Indicación de uso y, si hay un rango elegido, botón para quitarlo."""
    if not activo:
        st.caption(AYUDA_RANGO)
        return
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.caption(AYUDA_RANGO)
    b.button("✕ Quitar", key=f"clr_{key}", **WIDE, help="Quitar la selección de meses",
             on_click=lambda: st.session_state.update({f"_rng_{key}": None}))


def _mes(x) -> pd.Timestamp:
    return pd.Timestamp(x).normalize().replace(day=1)


def _al_seleccionar(key: str):
    """Callback: guarda el rango elegido. Solo corre cuando el usuario selecciona/deselecciona."""
    ev = st.session_state.get(f"chart_{key}")
    pts = []
    try:
        pts = ev["selection"]["points"] or []
    except Exception:
        pass
    xs = []
    for p in pts:
        try:
            xs.append(_mes(p["x"]))
        except Exception:
            continue
    st.session_state[f"_rng_{key}"] = (min(xs), max(xs)) if xs else None


def rango_elegido(key: str, periodos) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Rango guardado, recortado a los meses del filtro actual (None si no hay selección)."""
    r = st.session_state.get(f"_rng_{key}")
    if not r:
        return None
    meses = [m for m in sorted({_mes(p) for p in periodos}) if r[0] <= m <= r[1]]
    return (meses[0], meses[-1]) if meses else None


def marcar_rango(fig: go.Figure, rango):
    """Sombrea el tramo elegido en el eje de meses."""
    if rango:
        fig.add_vrect(x0=rango[0] - pd.Timedelta(days=16), x1=rango[1] + pd.Timedelta(days=16),
                      fillcolor="#6D6E71", opacity=0.10, line_width=0, layer="below")


def tarjeta_rango(fig: go.Figure, rango, lineas: list[str]):
    """Tarjeta dentro del gráfico (esquina superior izquierda) con las métricas del rango."""
    n = len(pd.period_range(rango[0], rango[1], freq="M"))
    titulo = f"<b>{etiqueta_rango(rango)}</b>  <span style='color:#6D6E71'>({n} {'mes' if n == 1 else 'meses'})</span>"
    fig.add_annotation(xref="paper", yref="paper", x=0.005, y=0.99, xanchor="left", yanchor="top",
                       align="left", showarrow=False, text="<br>".join([titulo, *lineas]),
                       bgcolor="rgba(255,255,255,0.96)", bordercolor="#267939", borderwidth=1.5, borderpad=8,
                       font=dict(size=round(13 * _scale()), color="#1A1A1A"))


def show_seleccionable(fig: go.Figure, key: str):
    """Gráfico en el que arrastrar (solo en horizontal) selecciona meses."""
    fig.update_layout(dragmode="select", selectdirection="h")
    st.plotly_chart(fig, **WIDE, config={"displaylogo": False}, key=f"chart_{key}",
                    on_select=lambda: _al_seleccionar(key), selection_mode=("box", "points"))


def etiqueta_rango(rango) -> str:
    a, b = rango
    return D.periodo_label(a) if a == b else f"{D.periodo_label(a)} – {D.periodo_label(b)}"

# ---------------------------------------------------------------------------
# Contexto (datos cargados + filtros globales)
# ---------------------------------------------------------------------------
def ctx() -> dict:
    return st.session_state["_ctx"]
