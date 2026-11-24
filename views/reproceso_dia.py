import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
base = c["traz_f"]

brand.header("Reproceso por día", "Máxima cantidad de azúcar reprocesada por día (según fecha de reproceso)")
if base.empty:
    ui.no_data(); st.stop()

d = D.reproceso_diario(base)
if d.empty:
    ui.no_data(); st.stop()
d["periodo"] = d["fecha"].dt.to_period("M").dt.to_timestamp()
top = d.loc[d["qq"].idxmax()]

k = st.columns(4)
ui.kpi(k[0], "Máximo día (qq)", ui.fnum(top["qq"]), help=f"Día: {top['fecha']:%Y-%m-%d}")
ui.kpi(k[1], "Día del máximo", f"{top['fecha']:%d/%m/%Y}")
ui.kpi(k[2], "Promedio día (qq)", ui.fnum(d["qq"].mean()),
       help="Promedio de los días en que hubo reproceso.")
ui.kpi(k[3], "Días con reproceso", ui.fnum(len(d), 0))

st.subheader("Máximo diario por mes")
mx = d.loc[d.groupby("periodo")["qq"].idxmax()].sort_values("periodo")
fig = go.Figure(go.Bar(
    x=mx["periodo"], y=mx["qq"], marker_color=ui.ORANGE, name="Máximo diario",
    customdata=mx["fecha"].dt.strftime("%d/%m/%Y"),
    text=[ui.fnum(v) for v in mx["qq"]], textposition="outside",
    hovertemplate="Máximo: %{y:,.1f} qq<br>Día: %{customdata}<extra></extra>"))
ui.style(fig, height=360, legend=False)
fig.update_yaxes(range=[0, mx["qq"].max() * 1.18])
ui.month_axis(fig)
ui.show(fig)

st.subheader("Reproceso diario")
st.caption("Se etiquetan los 10 días de mayor reproceso; pasa el cursor sobre las barras para ver el resto.")
top10 = set(d.nlargest(10, "qq").index)
fig = go.Figure(go.Bar(x=d["fecha"], y=d["qq"], marker_color=ui.BLUE, name="qq por día",
                       customdata=d["estibas"],
                       text=[f"{ui.fnum(q)}<br>{f:%d/%m}" if i in top10 else "" for i, q, f in
                             zip(d.index, d["qq"], d["fecha"])],
                       textposition="outside",
                       hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.1f} qq · %{customdata} estibas<extra></extra>"))
fig.update_layout(bargap=0.1)
ui.style(fig, height=360, legend=False)
ui.headroom(fig, d["qq"].max(), 1.25)
ui.month_axis(fig)
ui.show(fig)

a, b = st.columns(2)
with a:
    st.subheader("Días de mayor reproceso")
    t = d.sort_values("qq", ascending=False).head(15)[["fecha", "qq", "estibas"]]
    st.dataframe(t.rename(columns={"fecha": "Fecha", "qq": "Quintales", "estibas": "Estibas"}),
                 hide_index=True, **ui.WIDE,
                 column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                "Quintales": st.column_config.NumberColumn(format="%.1f")})
with b:
    st.subheader("Resumen mensual")
    r = d.groupby("periodo").agg(maximo=("qq", "max"), promedio=("qq", "mean"), total=("qq", "sum"),
                                 dias=("qq", "size")).reset_index()
    r["periodo"] = r["periodo"].map(D.periodo_label)
    st.dataframe(r.rename(columns={"periodo": "Mes", "maximo": "Máx. día (qq)", "promedio": "Prom. día (qq)",
                                   "total": "Total (qq)", "dias": "Días"}),
                 hide_index=True, **ui.WIDE,
                 column_config={c_: st.column_config.NumberColumn(format="%.1f")
                                for c_ in ["Máx. día (qq)", "Prom. día (qq)", "Total (qq)"]})
