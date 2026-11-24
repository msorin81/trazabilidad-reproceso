import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import seleccion as S
from reproceso import ui

c = ui.ctx()
df = D.ingreso(c["traz_f"])

brand.header("Ingreso de azúcar por mes", "Quintales cuya fecha de ingreso cae en el mes de la hoja")
if df.empty:
    ui.no_data(); st.stop()

periodos = df["periodo"].nunique()
k = st.columns(4)
ui.kpi(k[0], "Ingreso total (qq)", ui.fnum(df["qq"].sum()))
ui.kpi(k[1], "Prom. mensual (qq)", ui.fnum(df["qq"].sum() / max(periodos, 1)))
ui.kpi(k[2], "Estibas", ui.fnum(len(df), 0))
ui.kpi(k[3], "Causas distintas", ui.fnum(df["causa"].nunique(), 0))

st.subheader("Ingreso mensual por categoría")
S.grafico_por_categoria(df, "ing", modo="suma", height=380)

a, b = st.columns(2)
with a:
    st.subheader("Por causa de ingreso")
    n = st.slider("Mostrar las principales", 5, 30, 15, key="ing_n_causa")
    ui.show(ui.top_bar(df, "causa", n=n))
with b:
    st.subheader("Por código de producto")
    n2 = st.slider("Mostrar los principales", 5, 30, 15, key="ing_n_cod")
    ui.show(ui.top_bar(df, "codigo", n=n2))

st.subheader("Matriz categoría × mes (qq)")
ui.show_pivot(ui.pivot_month(df, "categoria"))

with st.expander("Matriz causa × mes (qq)"):
    ui.show_pivot(ui.pivot_month(df, "causa"), height=420)

with st.expander("Detalle de registros ingresados"):
    ui.detail_table(df.sort_values("fecha_ingreso", ascending=False),
                    ["periodo", "estiba", "qq", "estado", "categoria", "codigo", "fecha_produccion_txt",
                     "fecha_ingreso", "rango_marcacion", "causa", "tipo_azucar", "presentacion_kg",
                     "observaciones"], key="ing", filename="ingreso_reproceso")
