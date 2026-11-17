import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
df, tq = c["traz_f"], c["tiq_f"]

brand.header("Resumen trazabilidad del PPR de reproceso",
             "Ingreso, disolución y stock de azúcar no conforme, avería, barredura y rechazado")
if df.empty:
    ui.no_data(); st.stop()

ing = D.mensual(D.ingreso(df)).set_index("periodo")["qq"]
dis = D.mensual(D.disolucion(df)).set_index("periodo")["qq"]
stk_all = D.stock(df)
stk = D.mensual(stk_all).set_index("periodo")["qq"]
periodos = sorted(df["periodo"].unique())
ultimo = pd.Timestamp(periodos[-1])
anterior = pd.Timestamp(periodos[-2]) if len(periodos) > 1 else None

stk_ult = stk_all[stk_all["periodo"] == ultimo]
v_stk = stk.get(ultimo, 0.0)
d_stk = (v_stk - stk.get(anterior, 0.0)) if anterior is not None else None

brand.grupo(f"Periodo filtrado: {D.periodo_label(periodos[0])} – {D.periodo_label(ultimo)}",
            f"Stock y estibas: cierre de {D.periodo_label(ultimo)} · Ingreso y disuelto: total del periodo")

k = st.columns(5)
ui.kpi(k[0], "Stock (qq)", ui.fnum(v_stk),
       delta=None if d_stk is None else f"{ui.fnum(d_stk)} qq", delta_color="inverse",
       help=f"Quintales con estado «Cuantificado» en la hoja de {D.periodo_label(ultimo)}; "
            "la variación es frente al mes anterior.")
ui.kpi(k[1], "Ingreso (qq)", ui.fnum(ing.sum()),
       help="Quintales del periodo cuya fecha de ingreso cae en el mes de la hoja.")
ui.kpi(k[2], "Disuelto (qq)", ui.fnum(dis.sum()),
       help="Quintales del periodo con estado «Disuelto» o «Mezclado».")
ui.kpi(k[3], "Estibas en stock", ui.fnum(len(stk_ult), 0),
       help=f"Registros «Cuantificado» en la hoja de {D.periodo_label(ultimo)}.")
viejas = (stk_ult["dias_en_stock"] > 60).sum()
ui.kpi(k[4], "Estibas > 60 días", ui.fnum(viejas, 0),
       help="Estibas en stock con más de 60 días: fin de mes (u hoy) − fecha de ingreso.")

# ---------------------------------------------------------------------------
st.subheader("Flujo mensual: ingreso, disolución y stock")
idx = pd.DatetimeIndex(periodos)
flow = pd.DataFrame({"Ingreso": ing, "Disolución": dis, "Stock fin de mes": stk}).reindex(idx).fillna(0)

rango = ui.rango_elegido("resumen", periodos)
ui.ayuda_rango("resumen", bool(rango))
fig = go.Figure()
for name in ["Ingreso", "Disolución"]:
    fig.add_bar(x=flow.index, y=flow[name], name=name, marker_color=ui.FLOW_COLORS[name],
                text=flow[name], texttemplate="%{y:,.0f}", textposition="outside",
                hovertemplate=f"{name}: %{{y:,.1f}} qq<extra></extra>")
fig.add_scatter(x=flow.index, y=flow["Stock fin de mes"], name="Stock fin de mes", mode="lines+markers+text",
                line=dict(color=ui.FLOW_COLORS["Stock fin de mes"], width=2), marker=dict(size=8),
                text=[ui.fnum(v, 0) for v in flow["Stock fin de mes"]], textposition="top center",
                hovertemplate="Stock fin de mes: %{y:,.1f} qq<extra></extra>")
fig.update_layout(barmode="group", hovermode="x unified")
ui.style(fig, height=430)
ui.headroom(fig, flow.max().max(), 1.6 if rango else 1.15)  # con tarjeta: espacio arriba para ella
if len(flow) > 14:  # muchas barras: se dejan solo las etiquetas de la línea de stock
    fig.update_traces(selector=dict(type="bar"), texttemplate=None, text=None)
fig.update_layout(hovermode="x unified")
ui.month_axis(fig)
if rango:
    fr = flow.loc[rango[0]:rango[1]]
    s = fr["Stock fin de mes"]
    ui.marcar_rango(fig, rango)
    ui.tarjeta_rango(fig, rango, [
        f"Stock promedio: <b>{ui.fnum(s.mean())} qq</b>",
        f"Máx.: {ui.fnum(s.max())} ({D.periodo_label(s.idxmax())}) · "
        f"Mín.: {ui.fnum(s.min())} ({D.periodo_label(s.idxmin())})",
        f"Ingreso: <b>{ui.fnum(fr['Ingreso'].sum())} qq</b> · {ui.fnum(fr['Ingreso'].mean())} qq/mes",
        f"Disuelto: <b>{ui.fnum(fr['Disolución'].sum())} qq</b> · {ui.fnum(fr['Disolución'].mean())} qq/mes",
    ])
ui.show_seleccionable(fig, "resumen")

with st.expander("Ver tabla"):
    t = flow.copy()
    t.index = [D.periodo_label(p) for p in t.index]
    t["Balance (ingreso − disolución)"] = t["Ingreso"] - t["Disolución"]
    ui.show_pivot(t)

# ---------------------------------------------------------------------------
a, b = st.columns(2)
with a:
    st.subheader(f"Stock {D.periodo_label(ultimo)} por categoría")
    if stk_ult.empty:
        st.info("No hay stock «Cuantificado» en ese mes.")
    else:
        ui.show(ui.top_bar(stk_ult, "categoria", n=10, by_category=True))
with b:
    st.subheader(f"Antigüedad del stock {D.periodo_label(ultimo)}")
    if stk_ult.empty:
        st.info("No hay stock «Cuantificado» en ese mes.")
    else:
        ag = stk_ult.assign(rango=ui.aging_bucket(stk_ult["dias_en_stock"]))
        g = ag.groupby("rango", observed=False)["qq"].sum().reindex(ui.AGING_ORDER).fillna(0)
        fig = go.Figure(go.Bar(x=g.index, y=g.values, marker_color=[ui.AGING_COLORS[r] for r in g.index],
                               text=[ui.fnum(v) for v in g.values], textposition="outside",
                               hovertemplate="%{x}: %{y:,.1f} qq<extra></extra>"))
        ui.style(fig, height=320, legend=False)
        fig.update_yaxes(range=[0, max(g.max(), 1) * 1.2])
        ui.show(fig)
