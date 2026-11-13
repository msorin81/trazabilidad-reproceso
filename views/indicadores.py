import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()

brand.header("Indicadores del modelo Power BI",
             "Medidas DAX de la tabla «Medidas» recalculadas por mes (hoja)")

# Se calculan sobre toda la historia (con los filtros de categoría/tipo/código) para que
# MoM, YoY y acumulados tengan el mes/año anterior aunque el filtro de año sea uno solo.
med_all = D.medidas_pbi(c["traz_dim"])
sel = c["traz_f"]["periodo"].unique()
med = med_all[med_all.index.isin(sel)]
if med.empty:
    ui.no_data(); st.stop()

ult = med.index.max()
r = med.loc[ult]
st.caption(f"Tarjetas calculadas para **{D.periodo_label(ult)}** (último mes del filtro).")


def pct(x):
    return "—" if pd.isna(x) else (("+" if x > 0 else "") + ui.fpct(x))


k = st.columns(4)
ui.kpi(k[0], "Ingreso del mes (qq)", ui.fnum(r["Ingreso (qq)"]), delta=pct(r["Var. MoM ingreso"]) + " MoM"
       if pd.notna(r["Var. MoM ingreso"]) else None, delta_color="off",
       help="Var MoM Ingreso (%) = (mes − mes anterior) / mes anterior.")
ui.kpi(k[1], "Var. YoY ingreso", pct(r["Var. YoY ingreso"]),
       help="Var YoY Ingreso (%) frente al mismo mes del año anterior.")
ui.kpi(k[2], "Ingreso acumulado año (qq)", ui.fnum(r["Ingreso acumulado año (qq)"]), help="QQ Ingreso YTD.")
ui.kpi(k[3], "Disuelto acumulado año (qq)", ui.fnum(r["Disuelto acumulado año (qq)"]), help="QQ Disueltos YTD.")
k = st.columns(4)
ui.kpi(k[0], "Prom. móvil 3M ingreso (qq)", ui.fnum(r["Prom. móvil 3M ingreso (qq)"]),
       help="Promedio del ingreso de los últimos 3 meses.")
ui.kpi(k[1], "% Disolución", ui.fpct(r["% Disolución"]),
       help="Disuelto del mes / total de quintales de la hoja. Equivale al Índice de rotación mensual.")
ui.kpi(k[2], "% Stock pendiente", ui.fpct(r["% Stock pendiente"]),
       help="Quintales «Cuantificado» / total de quintales de la hoja.")
ui.kpi(k[3], "Estibas > 30 / > 60 días", f'{ui.fnum(r["Estibas > 30 días"], 0)} / {ui.fnum(r["Estibas > 60 días"], 0)}',
       help="Estibas en stock con más de 30 y 60 días.")

st.subheader("Ingreso mensual y promedio móvil de 3 meses")
fig = go.Figure()
fig.add_bar(x=med.index, y=med["Ingreso (qq)"], name="Ingreso", marker_color=ui.BLUE,
            text=med["Ingreso (qq)"], texttemplate="%{y:,.0f}", textposition="outside",
            hovertemplate="Ingreso: %{y:,.1f} qq<extra></extra>")
fig.add_scatter(x=med.index, y=med["Prom. móvil 3M ingreso (qq)"], name="Promedio móvil 3M",
                mode="lines+markers", line=dict(color=ui.ORANGE, width=2), marker=dict(size=8),
                hovertemplate="Prom. 3M: %{y:,.1f} qq<extra></extra>")
ui.style(fig, height=380)
fig.update_layout(hovermode="x unified")
ui.headroom(fig, med["Ingreso (qq)"].max(), 1.15)
ui.month_axis(fig)
ui.show(fig)

st.subheader("% Disolución vs % stock pendiente (sobre el total de la hoja)")
fig = go.Figure()
for col, color in [("% Disolución", ui.ORANGE), ("% Stock pendiente", ui.AQUA)]:
    fig.add_scatter(x=med.index, y=med[col] * 100, name=col, mode="lines+markers+text",
                    line=dict(color=color, width=2), marker=dict(size=8),
                    text=[ui.fnum(v * 100, 0) + "%" if pd.notna(v) else "" for v in med[col]],
                    textposition="top center", hovertemplate=f"{col}: %{{y:.1f}} %<extra></extra>")
ui.style(fig, height=360, ytitle="% del total de la hoja")
fig.update_yaxes(range=[0, 115], tickformat=".0f", ticksuffix=" %")
fig.update_layout(hovermode="x unified")
ui.month_axis(fig)
ui.show(fig)

st.subheader("Tabla de medidas por mes")
fmt_pct = ["Var. MoM ingreso", "Var. YoY ingreso", "% Disolución", "% Stock pendiente",
           "Índice rotación (disuelto/total)"]
t = med.copy()
for cc in fmt_pct:
    t[cc] = t[cc] * 100
t.index = [D.periodo_label(p) for p in t.index]
t = t.T
t.index.name = "Medida"
cfg = {cc: st.column_config.NumberColumn(cc, format="%.1f") for cc in t.columns}
st.dataframe(t, **ui.WIDE, column_config=cfg, height=min(36 * (len(t) + 1) + 4, 820))
st.caption("Las filas de variación y porcentaje están expresadas en %.")
st.download_button("⬇️ Descargar medidas", ui.to_excel_bytes({"medidas": t}), file_name="medidas_powerbi.xlsx",
                   key="dl_med")

with st.expander("Equivalencia con las medidas DAX del archivo .pbip"):
    st.markdown("""
| Medida DAX (Power BI) | En la app |
|---|---|
| `Sum Quintales_Ingreso`, `qq_ingreso_mes` | Ingreso (qq) — páginas Resumen e Ingreso |
| `Sum Quintales_Mes` (+ filtro Estado) | Stock fin de mes (Cuantificado) y Disolución (Disuelto + Mezclado) |
| `Sum Quintales_Repro_día`, `qq máx día` | Página Reproceso por día |
| `Suma total qq tiquetes`, `Suma total qq Físico`, `Dif Tiquete_físico`, `% Dif Tiquete vs Físico` | Página Físico vs tiquete |
| `QQ Ingreso Mes Anterior`, `Var MoM Ingreso (%)`, `QQ Ingreso Año Anterior`, `Var YoY Ingreso (%)` | Esta página |
| `QQ Ingreso YTD`, `QQ Disueltos YTD`, `Promedio Móvil 3M Ingreso`, `QQ Promedio Mensual` | Esta página / KPI «Prom. mensual» |
| `% Disolución`, `% Stock Pendiente`, `Índice Rotación Mensual` | Esta página |
| `Total Estibas`, `Estibas en Stock`, `Estibas > 30 días`, `Estibas > 60 días` | KPI de Resumen y Stock + esta página |
| `Promedio Retención (días)`, `Máx Retención (días)` | Días en stock (calculado: fin de mes u hoy − ingreso) |
| `Total Causas Distintas`, `Rank Causa por QQ` | KPI de Ingreso y orden de las barras por causa |
| `QQ Stock Actual`, `QQ Disueltos` | Stock y Disolución. **Ojo:** en el .pbip filtran Estado = «En Stock», valor que no existe en los Excel (se usa «Cuantificado»), por lo que en Power BI esa medida queda en blanco. |
| `Promedio_Indicador1`, `Promedio_Confiabilidad` | No incluidas: están en páginas ocultas del reporte y el .pbip solo carga esas tablas hasta 2024. |
""")
