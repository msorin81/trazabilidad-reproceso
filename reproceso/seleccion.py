"""Gráfico mensual apilado por categoría con selección por clic y tarjeta flotante.

modo="suma": flujos (ingreso, disolución) → se suman los meses elegidos.
modo="foto": stock de fin de mes (cada mes es una foto) → promedio, máximo y mínimo de lo elegido;
             sumar meses contaría varias veces las mismas estibas.
"""
from __future__ import annotations

import time as _time

import pandas as pd
import streamlit as st

from . import data as D
from . import ui

_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia


def _cats(df: pd.DataFrame) -> list[str]:
    presentes = df["categoria"].unique()
    return [x for x in ui.CAT_COLORS if x in presentes] + [x for x in presentes if x not in ui.CAT_COLORS]


def _etiqueta_meses(meses: list) -> str:
    n = len(meses)
    if n == len(pd.period_range(meses[0], meses[-1], freq="M")):
        return ui.etiqueta_rango((meses[0], meses[-1]))
    return ", ".join(D.periodo_label(m) for m in meses[:4]) + (" …" if n > 4 else "")


def _filas_elegidas(df: pd.DataFrame, sel: list[tuple]) -> pd.DataFrame:
    pares = pd.DataFrame([(m, c) for m, c in sel if c is not None], columns=["periodo", "categoria"])
    meses_tot = [m for m, c in sel if c is None]
    partes = [df[df["periodo"].isin(meses_tot)]]
    if not pares.empty:
        partes.append(df.merge(pares, on=["periodo", "categoria"]))
    return pd.concat(partes).drop_duplicates()


def _lineas_suma(d: pd.DataFrame, cats: list[str]) -> list[str]:
    out = []
    for cat in cats:
        dc = d[d["categoria"] == cat]
        k = dc["periodo"].nunique()
        linea = f"{cat}: <b>{ui.fnum(dc['qq'].sum())} qq</b> · {ui.fnum(len(dc), 0)} estibas"
        if k > 1:
            linea += f" · prom. {ui.fnum(dc['qq'].sum() / k)} qq/mes ({k} meses)"
        out.append(linea)
    if len(cats) > 1:
        out.append(f"<b>Total: {ui.fnum(d['qq'].sum())} qq</b> · {ui.fnum(len(d), 0)} estibas")
    return out


def _linea_foto(nombre: str, qq: pd.Series, est: pd.Series, negrita=False) -> str:
    b0, b1 = ("<b>", "</b>") if negrita else ("", "")
    if len(qq) == 1:
        return (f"{b0}{nombre}: {b1}<b>{ui.fnum(qq.iloc[0])} qq</b> · {ui.fnum(est.iloc[0], 0)} estibas "
                f"({D.periodo_label(qq.index[0])})")
    return (f"{b0}{nombre}: {b1}prom. <b>{ui.fnum(qq.mean())} qq</b> · {ui.fnum(est.mean())} estibas · "
            f"máx. {ui.fnum(qq.max())} ({D.periodo_label(qq.idxmax())}) · "
            f"mín. {ui.fnum(qq.min())} ({D.periodo_label(qq.idxmin())})")


def _lineas_foto(d: pd.DataFrame, cats: list[str]) -> list[str]:
    out = []
    for cat in cats:
        dc = d[d["categoria"] == cat]
        out.append(_linea_foto(cat, dc.groupby("periodo")["qq"].sum(), dc.groupby("periodo").size()))
    if len(cats) > 1:
        out.append(_linea_foto("Total", d.groupby("periodo")["qq"].sum(), d.groupby("periodo").size(), negrita=True))
    return out


def grafico_por_categoria(df: pd.DataFrame, key: str, modo: str = "suma", height: int = 370) -> list[tuple]:
    """Dibuja botones «todo el periodo», ayuda, gráfico apilado seleccionable y tarjeta. Devuelve la selección."""
    meses = sorted(pd.to_datetime(df["periodo"].unique()))
    cats = _cats(df)
    estado = f"_sel_{key}"

    def todo(cat):
        st.session_state[estado] = [(m, cat) for m in meses]

    bt = st.columns([1.3] + [1] * len(cats) + [max(0.5, 5 - len(cats))], vertical_alignment="center")
    bt[0].markdown(f"<span style='font-size:.85rem;color:#6D6E71'>"
                   f"{'Sumar' if modo == 'suma' else 'Resumir'} todo el periodo:</span>", unsafe_allow_html=True)
    for i, cat in enumerate(cats):
        bt[i + 1].button(cat, key=f"{key}_todo_{cat}", on_click=todo, args=(cat,), **ui.WIDE,
                         help=f"{'Suma' if modo == 'suma' else 'Promedio, máximo y mínimo de'} {cat} "
                              "en todos los meses del filtro")

    sel = ui.seleccion_cat(key, df["periodo"].unique())
    ayuda = ("Haz clic en un segmento (p. ej. Avería de un mes) para " +
             ("sumarlo" if modo == "suma" else "incluirlo") +
             "; otro clic lo quita. Clic en el total de un mes incluye todas sus categorías. "
             "Para un rango de meses usa el recuadro ⬚ de la barra del gráfico.")
    if modo == "foto":
        ayuda += " Como cada mes es una foto del stock, se muestran promedio, máximo y mínimo (no la suma)."
    ui.ayuda_seleccion(key, bool(sel), ayuda)

    fig = ui.stacked_by_category(df)
    ui.style(fig, height=height + (40 if sel else 0))
    ui.month_axis(fig)
    if sel:
        d = _filas_elegidas(df, sel)
        meses_sel = sorted({m for m, _ in sel})
        n_m = len(meses_sel)
        cs = _cats(d) if not d.empty else []
        lineas = (_lineas_suma if modo == "suma" else _lineas_foto)(d, cs) if cs else ["Sin registros en lo elegido"]
        if set(meses_sel) == set(meses) and n_m > 1:
            titulo = (f"<b>{ui.etiqueta_rango((meses[0], meses[-1]))}</b>  <span style='color:#6D6E71'>"
                      f"(todo el periodo · {n_m} meses con datos)</span>")
        else:
            titulo = (f"<b>{_etiqueta_meses(meses_sel)}</b>  <span style='color:#6D6E71'>"
                      f"({n_m} {'mes' if n_m == 1 else 'meses'})</span>")
        ui.tarjeta(fig, titulo, lineas)
        ui.headroom(fig, df.groupby("periodo")["qq"].sum().max(), 1.55 + 0.07 * len(lineas))
        ui.resaltar_seleccion(fig, sel)
    ui.show_seleccionable_cat(fig, key)
    return sel
