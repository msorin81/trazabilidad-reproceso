import pandas as pd
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import seleccion as S
from reproceso import ui

c = ui.ctx()
base = c["traz_f"]

brand.header("Disolución de azúcar", "Quintales reprocesados (disueltos o mezclados) en cada mes")
if base.empty:
    ui.no_data(); st.stop()

DIMS = {"causa": "Causa de ingreso", "codigo": "Código de producto", "tipo_azucar": "Tipo de azúcar",
        "presentacion_kg": "Presentación (kg)", "equipo": "Etapa o equipo",
        "clasificacion": "Clasificación", "resp_laboratorio": "Responsable laboratorio"}
if base["resp_laboratorio"].isna().all():  # versión web: sin nombres de personas
    DIMS.pop("resp_laboratorio")

f1, f2 = st.columns([2, 1])
# Opciones estables (de toda la historia): si dependieran del filtro, al cambiar de año Streamlit
# conservaría la selección anterior y podría excluir «Mezclado» sin avisar.
estados_all = sorted(c["traz"]["estado"].unique())
estados = f1.multiselect("Estados que cuentan como disolución", estados_all,
                         default=[e for e in D.ESTADOS_DISOLUCION if e in estados_all], key="dis_estados",
                         help="Por defecto «Disuelto» y «Mezclado», igual que el reporte de Power BI.")
dim = f2.selectbox("Analizar por", list(DIMS), format_func=DIMS.get, key="dis_dim")

df = D.disolucion(base, estados or None)
if df.empty:
    ui.no_data(); st.stop()
df = df.assign(**{dim: df[dim].fillna("(Sin dato)")})

meses = df["periodo"].nunique()
k = st.columns(4)
ui.kpi(k[0], "Disuelto total (qq)", ui.fnum(df["qq"].sum()))
ui.kpi(k[1], "Prom. mensual (qq)", ui.fnum(df["qq"].sum() / max(meses, 1)))
ui.kpi(k[2], "Estibas disueltas", ui.fnum(len(df), 0))
ui.kpi(k[3], "Días prom. en stock", ui.fnum(df["dias_en_stock"].mean()),
       help="Promedio de días entre la fecha de ingreso y la fecha de reproceso.")

st.subheader("Disolución mensual por categoría")
S.grafico_por_categoria(df, "dis", modo="suma", height=360)

st.caption("📈 El comparativo del año actual frente a los anteriores está en el módulo **Histórico interanual** (menú *Seguimiento*).")

st.subheader(f"Disolución por {DIMS[dim].lower()}")
n = st.slider("Mostrar los principales", 5, 30, 15, key="dis_n")
ui.show(ui.top_bar(df, dim, n=n))

st.subheader(f"Matriz {DIMS[dim].lower()} × mes (qq)")
ui.show_pivot(ui.pivot_month(df, dim), height=420)

with st.expander("Detalle de registros disueltos"):
    ui.detail_table(df.sort_values("fecha_reproceso", ascending=False),
                    ["periodo", "estiba", "qq", "estado", "categoria", "codigo", "fecha_ingreso", "causa",
                     "fecha_reproceso", "dias_en_stock", "tiquete", "equipo", "medida_control",
                     "punto_disolucion", "resp_laboratorio", "resp_elaboracion", "autoriza", "tipo_azucar",
                     "presentacion_kg"], key="dis", filename="disolucion_reproceso")
