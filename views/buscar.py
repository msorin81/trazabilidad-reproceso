import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
traz, tiq = c["traz"], c["tiq"]

brand.header("Buscar estiba o tiquete", "Historia de una estiba a través de las hojas mensuales (todos los años)")

f1, f2 = st.columns([1, 2])
campo = f1.selectbox("Buscar por", ["# Estiba", "Tiquete pesaje", "Rango marcación", "Código de producto",
                                     "Texto libre (causa / observaciones)"], key="bus_campo")
q = f2.text_input("Valor a buscar", key="bus_q", placeholder="Ej. 1800, 36923, 89338…").strip()
exacto = st.checkbox("Coincidencia exacta", value=campo in ("# Estiba", "Tiquete pesaje"), key="bus_exacto")

if not q:
    brand.note("Escribe un valor para buscar. Una estiba que sigue en stock aparece en varias hojas "
               "(una por mes) con estado «Cuantificado» hasta que se disuelve.")
    st.stop()

col = {"# Estiba": ["estiba"], "Tiquete pesaje": ["tiquete"], "Rango marcación": ["rango_marcacion"],
       "Código de producto": ["codigo"], "Texto libre (causa / observaciones)": ["causa", "observaciones"]}[campo]
mask = False
for cl in col:
    s = traz[cl].fillna("").astype(str)
    m = s.str.lower() == q.lower() if exacto else s.str.contains(q, case=False, regex=False)
    mask = m | mask
res = traz[mask].sort_values(["estiba", "periodo"])

st.subheader(f"{len(res)} registros en trazabilidad")
if res.empty:
    st.info("Sin coincidencias.")
else:
    g = res.groupby("estiba").agg(hojas=("periodo", "nunique"), primera=("periodo", "min"),
                                  ultima=("periodo", "max"), qq=("qq", "last"),
                                  estado_final=("estado", "last")).reset_index()
    if len(g) <= 30:
        for _, r in g.iterrows():
            st.markdown(f"**Estiba {r['estiba']}** · {ui.fnum(r['qq'])} qq · aparece en {r['hojas']} hoja(s) "
                        f"({D.periodo_label(r['primera'])} → {D.periodo_label(r['ultima'])}) · "
                        f"último estado: **{r['estado_final']}**")
    ui.detail_table(res, ["periodo", "estiba", "qq", "estado", "categoria", "codigo", "fecha_produccion_txt",
                          "fecha_ingreso", "rango_marcacion", "causa", "fecha_reproceso", "tiquete",
                          "dias_en_stock", "equipo", "resp_laboratorio", "observaciones", "archivo"],
                    key="bus", filename="busqueda_trazabilidad")

if campo == "Tiquete pesaje":
    t = tiq[tiq["tiquete"].astype(str).str.contains(q, regex=False) if not exacto else tiq["tiquete"] == q]
    st.subheader(f"{len(t)} registros en tiquetes de báscula")
    if not t.empty:
        ui.detail_table(t, ["periodo", "fecha", "tiquete", "peso_tinas", "peso_averias", "qq_enteros",
                            "qq_tiquete", "qq_fisico", "diferencia", "archivo"], key="bus_t",
                        filename="busqueda_tiquetes", height=200)
