import pandas as pd
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
df, tq = c["traz_f"], c["tiq_f"]

brand.header("Control de calidad de los registros",
             "Inconsistencias detectadas en las tablas de trazabilidad y tiquetes (según filtros)")
if df.empty:
    ui.no_data(); st.stop()

COLS = ["periodo", "estiba", "qq", "estado", "categoria", "codigo", "fecha_ingreso", "causa",
        "fecha_reproceso", "tiquete", "archivo", "hoja"]
dis = D.disolucion(df)
hoy = pd.Timestamp.today().normalize()
fin_hoja = df["periodo"] + pd.offsets.MonthEnd(0)

checks = [
    ("crit", "Registros sin estado o sin categoría",
     "La fila tiene datos pero no indica Estado o Categoría; no se cuenta en stock ni en disolución.",
     df[(df["estado"] == "(Sin dato)") | (df["categoria"] == "(Sin dato)")]),
    ("crit", "Disuelto/Mezclado sin fecha de reproceso",
     "No se puede ubicar el día del reproceso.", dis[dis["fecha_reproceso"].isna()]),
    ("warn", "Disuelto/Mezclado sin tiquete de pesaje",
     "No es posible conciliar con la báscula.", dis[dis["tiquete"].isna()]),
    ("warn", "Fecha de reproceso fuera del mes de la hoja",
     "El registro disuelto está en una hoja distinta al mes de su fecha de reproceso.",
     dis[dis["fecha_reproceso"].notna() &
         (dis["fecha_reproceso"].dt.to_period("M") != dis["periodo"].dt.to_period("M"))]),
    ("warn", "Stock (Cuantificado) con fecha de reproceso",
     "Si ya se reprocesó, el estado debería ser «Disuelto» o «Mezclado».",
     df[(df["estado"].isin(D.ESTADOS_STOCK)) & df["fecha_reproceso"].notna()]),
    ("crit", "Sin fecha de ingreso", "No se puede calcular el ingreso del mes ni los días en stock.",
     df[df["fecha_ingreso"].isna()]),
    ("crit", "Fecha de ingreso posterior al mes de la hoja",
     "Posible error de digitación de la fecha.",
     df[df["fecha_ingreso"].notna() & (df["fecha_ingreso"] > fin_hoja)]),
    ("warn", "Fecha de reproceso anterior a la de ingreso", "Posible error de digitación de la fecha.",
     dis[dis["fecha_reproceso"] < dis["fecha_ingreso"]]),
    ("warn", "Fechas futuras", "Fecha de ingreso o de reproceso posterior a hoy.",
     df[(df["fecha_ingreso"] > hoy) | (df["fecha_reproceso"] > hoy)]),
    ("warn", "Quintales vacíos, cero o negativos", "El registro no suma al balance.",
     df[df["qq"].isna() | (df["qq"] <= 0)]),
    ("warn", "Posibles registros duplicados en la misma hoja",
     "Misma estiba, quintales, fecha de ingreso y código dentro de una misma hoja.",
     df[df.duplicated(["periodo", "estiba", "qq", "fecha_ingreso", "codigo", "estado"], keep=False)]
     .sort_values(["periodo", "estiba"])),
]

t_sin_traz = tq[~tq["tiquete"].isin(D.disolucion(c["traz"])["tiquete"].dropna())]
t_dif = tq[(tq["diferencia"].abs() > 0.05 * tq["qq_tiquete"].abs()) & (tq["qq_tiquete"] > 0)]

n_crit = sum(len(x[3]) > 0 for x in checks if x[0] == "crit")
n_warn = sum(len(x[3]) > 0 for x in checks if x[0] == "warn") + (len(t_sin_traz) > 0) + (len(t_dif) > 0)
k = st.columns(3)
ui.kpi(k[0], "Registros revisados", ui.fnum(len(df) + len(tq), 0))
ui.kpi(k[1], "Controles críticos", str(n_crit), help="Controles críticos con al menos un hallazgo.")
ui.kpi(k[2], "Advertencias", str(n_warn), help="Controles de advertencia con al menos un hallazgo.")

st.subheader("Trazabilidad")
for nivel, titulo, desc, sub in checks:
    icon = "✅" if sub.empty else ui.STATUS[nivel][0]
    etiqueta = "OK" if sub.empty else ("Crítico" if nivel == "crit" else "Advertencia")
    with st.expander(f"{icon} {titulo} — {len(sub)} registros · {etiqueta}", expanded=False):
        st.caption(desc)
        if not sub.empty:
            ui.detail_table(sub, COLS, key=f"q_{titulo}", filename="control_" +
                            titulo.lower().replace(" ", "_")[:40], height=300)

st.subheader("Tiquetes de báscula")
for titulo, desc, sub, cols in [
    ("Tiquetes sin estibas disueltas en trazabilidad",
     "El número de tiquete no aparece en ningún registro Disuelto/Mezclado.", t_sin_traz,
     ["periodo", "fecha", "tiquete", "qq_tiquete", "qq_fisico", "diferencia", "archivo"]),
    ("Diferencia tiquete − físico mayor al 5 %", "Revisar pesaje o declaración de estibas.", t_dif,
     ["periodo", "fecha", "tiquete", "qq_tiquete", "qq_fisico", "diferencia", "archivo"]),
]:
    icon = "✅" if sub.empty else "⚠️"
    with st.expander(f"{icon} {titulo} — {len(sub)} registros · {'OK' if sub.empty else 'Advertencia'}"):
        st.caption(desc)
        if not sub.empty:
            ui.detail_table(sub, cols, key=f"qt_{titulo}", filename="control_tiquetes", height=300)

st.subheader("Homologación de textos")
var = (df.groupby("causa")["causa_original"].nunique().reset_index(name="variantes"))
var = var[var["variantes"] > 1]
st.caption("Las causas escritas con diferencias de mayúsculas, tildes o espacios se agrupan automáticamente "
           f"bajo la escritura más frecuente. Causas distintas tras homologar: **{df['causa'].nunique()}**.")
with st.expander("Ver frecuencia de causas de ingreso"):
    f = df.groupby("causa").agg(registros=("qq", "size"), qq=("qq", "sum")).sort_values("qq", ascending=False)
    st.dataframe(f.rename(columns={"registros": "Registros", "qq": "Quintales"}), use_container_width=True,
                 column_config={"Quintales": st.column_config.NumberColumn(format="%.1f")})
