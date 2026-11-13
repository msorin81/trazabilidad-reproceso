import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
tq = c["tiq_f"]

brand.header("Disolución físico vs tiquete de báscula",
             "Quintales físicos (estibas) frente a lo registrado en los tiquetes de pesaje")
if tq.empty:
    ui.no_data(); st.stop()
if c["filtros_traz_extra"]:
    st.caption("ℹ️ Los filtros de categoría, tipo, presentación y código no aplican a los tiquetes "
               "(la tabla de tiquetes no tiene esos campos); solo se usan año y mes.")

tot_t, tot_f = tq["qq_tiquete"].sum(), tq["qq_fisico"].sum()
k = st.columns(4)
ui.kpi(k[0], "QQ tiquete", ui.fnum(tot_t))
ui.kpi(k[1], "QQ físico", ui.fnum(tot_f))
ui.kpi(k[2], "Diferencia (qq)", ui.fnum(tot_t - tot_f),
       help="Tiquete − físico. Negativo: la báscula registró menos que lo declarado en estibas.")
ui.kpi(k[3], "% diferencia", ui.fpct((tot_t - tot_f) / tot_t if tot_t else np.nan, 2))

m = tq.groupby("periodo", as_index=False)[["qq_tiquete", "qq_fisico"]].sum()
m["diferencia"] = m["qq_tiquete"] - m["qq_fisico"]

st.subheader("Quintales por mes")
fig = go.Figure()
fig.add_bar(x=m["periodo"], y=m["qq_tiquete"], name="Tiquete báscula", marker_color=ui.BLUE,
            text=m["qq_tiquete"], texttemplate="%{y:,.0f}", textposition="outside",
            hovertemplate="Tiquete: %{y:,.1f} qq<extra></extra>")
fig.add_bar(x=m["periodo"], y=m["qq_fisico"], name="Físico", marker_color=ui.ORANGE,
            text=m["qq_fisico"], texttemplate="%{y:,.0f}", textposition="outside",
            hovertemplate="Físico: %{y:,.1f} qq<extra></extra>")
fig.update_layout(barmode="group", bargroupgap=0.06)
ui.style(fig, height=380)
ui.headroom(fig, m[["qq_tiquete", "qq_fisico"]].max().max(), 1.15)
fig.update_layout(hovermode="x unified")
ui.month_axis(fig)
ui.show(fig)

st.subheader("Diferencia mensual (tiquete − físico)")
fig = go.Figure(go.Bar(x=m["periodo"], y=m["diferencia"],
                       marker_color=np.where(m["diferencia"] >= 0, ui.BLUE, ui.RED),
                       text=[ui.fnum(v) for v in m["diferencia"]], textposition="outside",
                       hovertemplate="%{x|%b %Y}<br>Diferencia: %{y:,.1f} qq<extra></extra>"))
ui.style(fig, height=280, legend=False)
lo, hi = min(m["diferencia"].min(), 0), max(m["diferencia"].max(), 0)
pad = max(hi - lo, 1) * 0.18
fig.update_yaxes(rangemode="normal", zeroline=True, zerolinewidth=1, range=[lo - pad, hi + pad])
ui.month_axis(fig)
ui.show(fig)

with st.expander("Tabla mensual"):
    t = m.copy()
    t["% dif"] = np.where(t["qq_tiquete"] != 0, 100 * t["diferencia"] / t["qq_tiquete"], np.nan)
    t["periodo"] = t["periodo"].map(D.periodo_label)
    st.dataframe(t.rename(columns={"periodo": "Mes", "qq_tiquete": "QQ tiquete", "qq_fisico": "QQ físico",
                                   "diferencia": "Diferencia"}), hide_index=True, use_container_width=True,
                 column_config={x: st.column_config.NumberColumn(format="%.2f")
                                for x in ["QQ tiquete", "QQ físico", "Diferencia", "% dif"]})

# ---------------------------------------------------------------------------
st.subheader("Conciliación por tiquete: báscula vs trazabilidad")
brand.note("Cruza cada tiquete de báscula con la suma de quintales de las estibas disueltas/mezcladas "
           "que registran ese mismo <b>Tiquete pesaje</b> en la tabla de trazabilidad.")
traz = c["traz"]
dis = D.disolucion(traz).dropna(subset=["tiquete"])
tz = dis.groupby("tiquete").agg(qq_traz=("qq", "sum"), estibas=("estiba", "count"),
                                fecha_repro=("fecha_reproceso", "max")).reset_index()
tk = tq.groupby("tiquete").agg(fecha=("fecha", "min"), qq_tiquete=("qq_tiquete", "sum"),
                               qq_fisico=("qq_fisico", "sum")).reset_index()
j = tk.merge(tz, on="tiquete", how="left")
# tiquetes de trazabilidad (en el periodo) que no están en báscula
anios, meses = c["anios"], c["meses"]
mask = pd.Series(True, index=dis.index)
if anios:
    mask &= dis["anio"].isin(anios)
if meses:
    mask &= dis["mes"].isin(meses)
dis_per = dis[mask]
sin_bascula = dis_per[~dis_per["tiquete"].isin(tq["tiquete"]) & ~dis_per["tiquete"].isin(c["tiq"]["tiquete"])]

tol = st.number_input("Tolerancia (qq)", min_value=0.0, value=1.0, step=0.5, key="tq_tol")
j["dif_fisico_traz"] = j["qq_fisico"] - j["qq_traz"]
j["Estado"] = np.select(
    [j["qq_traz"].isna(), j["dif_fisico_traz"].abs() > tol],
    ["⚠️ Sin estibas en trazabilidad", "⚠️ Diferencia > tolerancia"], "✅ Cuadra")

k = st.columns(3)
ui.kpi(k[0], "Cuadran", ui.fnum((j["Estado"] == "✅ Cuadra").sum(), 0))
ui.kpi(k[1], "Con diferencia", ui.fnum((j["Estado"] == "⚠️ Diferencia > tolerancia").sum(), 0),
       help="Tiquetes cuya diferencia físico − trazabilidad supera la tolerancia.")
ui.kpi(k[2], "Sin trazabilidad", ui.fnum((j["Estado"] == "⚠️ Sin estibas en trazabilidad").sum(), 0),
       help="Tiquetes de báscula sin estibas disueltas que los registren.")

solo_alertas = st.toggle("Mostrar solo tiquetes con alerta", value=True, key="tq_alert")
v = j[j["Estado"] != "✅ Cuadra"] if solo_alertas else j
v = v.sort_values("fecha", ascending=False).rename(columns={
    "tiquete": "Tiquete", "fecha": "Fecha báscula", "qq_tiquete": "QQ tiquete", "qq_fisico": "QQ físico",
    "qq_traz": "QQ trazabilidad", "estibas": "Estibas", "fecha_repro": "Fecha reproceso",
    "dif_fisico_traz": "Físico − trazabilidad"})
st.dataframe(v, hide_index=True, use_container_width=True,
             column_config={"Fecha báscula": st.column_config.DateColumn(format="DD/MM/YYYY"),
                            "Fecha reproceso": st.column_config.DateColumn(format="DD/MM/YYYY"),
                            **{x: st.column_config.NumberColumn(format="%.1f") for x in
                               ["QQ tiquete", "QQ físico", "QQ trazabilidad", "Físico − trazabilidad"]}})
st.download_button("⬇️ Descargar conciliación", ui.to_excel_bytes({"conciliacion": v}),
                   file_name="conciliacion_tiquetes.xlsx", key="dl_conc")

if not sin_bascula.empty:
    with st.expander(f"⚠️ {sin_bascula['tiquete'].nunique()} tiquetes de trazabilidad sin registro en báscula"):
        ui.detail_table(sin_bascula, ["periodo", "tiquete", "estiba", "qq", "estado", "fecha_reproceso",
                                      "categoria", "codigo"], key="sinb", filename="tiquetes_sin_bascula")
