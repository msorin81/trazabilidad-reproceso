import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
base = c["traz_f"]

brand.header("Stock al final de mes", "Estibas pendientes de reproceso registradas en la hoja de cada mes")
if base.empty:
    ui.no_data(); st.stop()

estados_all = sorted(c["traz"]["estado"].unique())  # opciones estables, no dependen del filtro
f1, f2 = st.columns([2, 1])
estados = f1.multiselect("Estados que cuentan como stock", estados_all,
                         default=[e for e in D.ESTADOS_STOCK if e in estados_all], key="stk_estados",
                         help="Por defecto «Cuantificado», igual que el reporte de Power BI.")
df = D.stock(base, estados or None)
if df.empty:
    ui.no_data(); st.stop()
periodos = sorted(df["periodo"].unique())
sel = f2.selectbox("Mes de la foto", periodos[::-1], format_func=D.periodo_label, key="stk_mes")
snap = df[df["periodo"] == sel]

prev = [p for p in periodos if p < sel]
v, v_prev = snap["qq"].sum(), (df[df["periodo"] == prev[-1]]["qq"].sum() if prev else None)
k = st.columns(4)
ui.kpi(k[0], "Stock del mes (qq)", ui.fnum(v),
       delta=None if v_prev is None else f"{ui.fnum(v - v_prev)} qq", delta_color="inverse",
       help=None if v_prev is None else f"Variación frente a {D.periodo_label(prev[-1])}.")
ui.kpi(k[1], "Estibas", ui.fnum(len(snap), 0))
ui.kpi(k[2], "Días prom. en stock", ui.fnum(snap["dias_en_stock"].mean(), 0),
       help="Fin de mes (u hoy, si es el mes en curso) − fecha de ingreso.")
ui.kpi(k[3], "Estibas > 60 días", ui.fnum((snap["dias_en_stock"] > 60).sum(), 0))

if (snap["dias_en_stock"] > 90).any():
    q90 = snap.loc[snap["dias_en_stock"] > 90, "qq"].sum()
    brand.note(f"⚠️ <b>Atención:</b> {ui.fnum(q90)} qq ({ui.fnum((snap['dias_en_stock'] > 90).sum(), 0)} "
               f"estibas) llevan más de 90 días en stock en {D.periodo_label(sel)}.", risk=True)

st.subheader("Evolución del stock de fin de mes por categoría")
per_base = sorted(pd.Timestamp(p) for p in base["periodo"].unique())
mes_qq = df.groupby("periodo")["qq"].sum().reindex(per_base).fillna(0)
mes_est = df.groupby("periodo").size().reindex(per_base).fillna(0)
rango = ui.rango_meses(per_base, "stock")
if rango:
    s = mes_qq.loc[rango[0]:rango[1]]
    e = mes_est.loc[rango[0]:rango[1]]
    n = len(s)
    st.caption(f"Resumen de **{ui.etiqueta_rango(rango)}** ({n} {'mes' if n == 1 else 'meses'}):")
    k = st.columns(5)
    ui.kpi(k[0], "Stock promedio (qq)", ui.fnum(s.mean()),
           help="Promedio del stock de fin de mes de los meses del rango (estados elegidos arriba).")
    ui.kpi(k[1], "Stock máximo (qq)", ui.fnum(s.max()), nota=D.periodo_label(s.idxmax()),
           help="Mes del rango con más stock.")
    ui.kpi(k[2], "Stock mínimo (qq)", ui.fnum(s.min()), nota=D.periodo_label(s.idxmin()),
           help="Mes del rango con menos stock.")
    ui.kpi(k[3], "Estibas promedio", ui.fnum(e.mean(), 0),
           help="Promedio de estibas en stock al cierre de cada mes del rango.")
    ui.kpi(k[4], "Variación en el rango (qq)", ui.fnum(s.iloc[-1] - s.iloc[0]),
           nota=f"{D.periodo_label(s.index[0])} → {D.periodo_label(s.index[-1])}",
           help="Stock del último mes del rango menos el del primero (negativo = bajó).")
fig = ui.stacked_by_category(df)
ui.style(fig, height=360)
ui.month_axis(fig)
ui.marcar_rango(fig, rango, per_base)
ui.show(fig)

a, b = st.columns(2)
with a:
    st.subheader(f"Por causa · {D.periodo_label(sel)}")
    ui.show(ui.top_bar(snap, "causa", n=15))
with b:
    st.subheader(f"Por código de producto · {D.periodo_label(sel)}")
    ui.show(ui.top_bar(snap, "codigo", n=15))

st.subheader(f"Antigüedad del stock · {D.periodo_label(sel)}")
ag = snap.assign(rango=ui.aging_bucket(snap["dias_en_stock"]))
g = ag.groupby(["rango", "categoria"], observed=False)["qq"].sum().reset_index()
fig = go.Figure()
for cat in [x for x in ui.CAT_COLORS if x in g["categoria"].unique()]:
    s = g[g["categoria"] == cat]
    if s["qq"].sum() == 0:
        continue
    fig.add_bar(x=s["rango"].astype(str), y=s["qq"], name=cat, marker_color=ui.cat_color(cat),
                hovertemplate=f"%{{x}}<br>{cat}: %{{y:,.1f}} qq<extra></extra>")
fig.update_layout(barmode="stack")
tot_ag = g.groupby("rango", observed=False)["qq"].sum().reindex(ui.AGING_ORDER).fillna(0)
ui.add_totals(fig, tot_ag.index, tot_ag.values)
fig.update_traces(selector=dict(type="bar"), texttemplate="%{y:,.0f}", textposition="inside",
                  textfont_color="#ffffff")
fig.update_xaxes(categoryorder="array", categoryarray=ui.AGING_ORDER)
ui.style(fig, height=340)
ui.headroom(fig, tot_ag.max(), 1.15)
ui.show(fig)

st.subheader("Matriz categoría × mes (qq)")
ui.show_pivot(ui.pivot_month(df, "categoria"))

st.subheader(f"Detalle del stock · {D.periodo_label(sel)}")
ui.detail_table(snap.sort_values("dias_en_stock", ascending=False),
                ["estiba", "qq", "estado", "categoria", "codigo", "fecha_produccion_txt", "fecha_ingreso",
                 "dias_en_stock", "rango_marcacion", "causa", "tipo_azucar", "presentacion_kg",
                 "observaciones"], key="stk", filename=f"stock_{pd.Timestamp(sel):%Y_%m}")
