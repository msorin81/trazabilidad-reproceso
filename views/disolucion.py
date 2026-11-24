import pandas as pd
import streamlit as st

from reproceso import brand
from reproceso import data as D
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
ui.kpi(k[3], "Días prom. en stock", ui.fnum(df["dias_en_stock"].mean(), 0),
       help="Promedio de días entre la fecha de ingreso y la fecha de reproceso.")

st.subheader("Disolución mensual por categoría")
meses_df = sorted(pd.to_datetime(df["periodo"].unique()))
cats_df = [x for x in ui.CAT_COLORS if x in df["categoria"].unique()] + \
          [x for x in df["categoria"].unique() if x not in ui.CAT_COLORS]


def _sumar_todo(cat):
    st.session_state["_sel_dis"] = [(m, cat) for m in meses_df]


bt = st.columns([1.3] + [1] * len(cats_df) + [max(0.5, 5 - len(cats_df))], vertical_alignment="center")
bt[0].markdown("<span style='font-size:.85rem;color:#6D6E71'>Sumar todo el periodo:</span>", unsafe_allow_html=True)
for i, cat in enumerate(cats_df):
    bt[i + 1].button(cat, key=f"dis_todo_{cat}", on_click=_sumar_todo, args=(cat,), **ui.WIDE,
                     help=f"Suma {cat} en todos los meses del filtro")
sel = ui.seleccion_cat("dis", df["periodo"].unique())
ui.ayuda_seleccion("dis", bool(sel),
                   "Haz clic en un segmento (p. ej. Avería de un mes) para sumarlo; otro clic lo quita. Clic en el "
                   "total de un mes suma todas sus categorías. Para un rango de meses usa el recuadro ⬚ de la barra "
                   "del gráfico.")
fig = ui.stacked_by_category(df)
ui.style(fig, height=400 if sel else 360)
ui.month_axis(fig)
if sel:
    pares = pd.DataFrame([(m, c_) for m, c_ in sel if c_ is not None], columns=["periodo", "categoria"])
    meses_tot = [m for m, c_ in sel if c_ is None]
    d = pd.concat([df.merge(pares, on=["periodo", "categoria"]) if not pares.empty else df.iloc[0:0],
                   df[df["periodo"].isin(meses_tot)]]).drop_duplicates()
    meses_sel = sorted({m for m, _ in sel})
    n_m = len(meses_sel)
    consecutivos = n_m == len(pd.period_range(meses_sel[0], meses_sel[-1], freq="M"))
    if consecutivos:
        etiqueta = ui.etiqueta_rango((meses_sel[0], meses_sel[-1]))
    else:
        etiqueta = ", ".join(D.periodo_label(m) for m in meses_sel[:4]) + (" …" if n_m > 4 else "")
    lineas = []
    cats = [x for x in ui.CAT_COLORS if x in d["categoria"].unique()] + \
           [x for x in d["categoria"].unique() if x not in ui.CAT_COLORS]
    for cat in cats:
        dc = d[d["categoria"] == cat]
        k_m = dc["periodo"].nunique()
        linea = f"{cat}: <b>{ui.fnum(dc['qq'].sum())} qq</b> · {ui.fnum(len(dc), 0)} estibas"
        if k_m > 1:
            linea += f" · prom. {ui.fnum(dc['qq'].sum() / k_m)} qq/mes ({k_m} meses)"
        lineas.append(linea)
    if len(cats) > 1:
        lineas.append(f"<b>Total: {ui.fnum(d['qq'].sum())} qq</b> · {ui.fnum(len(d), 0)} estibas")
    ui.tarjeta(fig, f"<b>{etiqueta}</b>  <span style='color:#6D6E71'>({n_m} {'mes' if n_m == 1 else 'meses'})</span>",
               lineas)
    tot_mes = df.groupby("periodo")["qq"].sum()
    ui.headroom(fig, tot_mes.max(), 1.55 + 0.07 * len(lineas))
    ui.resaltar_seleccion(fig, sel)
ui.show_seleccionable_cat(fig, "dis")

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
