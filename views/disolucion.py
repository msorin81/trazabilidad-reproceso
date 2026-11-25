import pandas as pd
import plotly.graph_objects as go
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

# ---------------------------------------------------------------------------
# Comparativo interanual: año actual frente a los anteriores (cantidad y %)
# Usa toda la historia (con los filtros de categoría/tipo/código, sin el de año/mes).
# ---------------------------------------------------------------------------
st.subheader("Comparativo interanual de la disolución")
hist = D.disolucion(c["traz_dim"], estados or None)
if hist["anio"].nunique() < 2:
    st.info("Se necesitan al menos dos años con disolución para comparar.")
else:
    anio_act = int(max(c["anios"])) if c["anios"] else int(hist["anio"].max())
    hist = hist[hist["anio"] <= anio_act]
    ult_mes = int(hist.loc[hist["anio"] == anio_act, "mes"].max()) if (hist["anio"] == anio_act).any() else 12
    a1, a2 = st.columns([2, 1], vertical_alignment="center")
    mismo = a2.toggle(f"Mismo periodo (Ene–{D.MESES[ult_mes - 1]})", value=ult_mes < 12, key="dis_cmp_mismo",
                      help=f"{anio_act} va hasta {D.MESES_LARGO[ult_mes - 1].lower()}: para comparar de forma justa, "
                           f"cada año se cuenta solo de enero a {D.MESES_LARGO[ult_mes - 1].lower()}. "
                           "Apágalo para ver los años completos.")
    if mismo:
        hist = hist[hist["mes"] <= ult_mes]
    periodo_txt = f"enero–{D.MESES_LARGO[ult_mes - 1].lower()} de cada año" if mismo else "años completos"
    a1.caption(f"Año actual: **{anio_act}** · {periodo_txt}. Haz clic en la leyenda para ocultar o mostrar una "
               "serie (p. ej. Avería); doble clic deja solo esa.")

    g = hist.groupby(["anio", "categoria"])["qq"].sum().unstack(fill_value=0.0)
    cats = [x for x in ui.CAT_COLORS if x in g.columns] + [x for x in g.columns if x not in ui.CAT_COLORS]
    g = g[cats]
    g["Total"] = g[cats].sum(axis=1)
    anios = [int(a) for a in g.index]
    etiquetas = [f"<b>{a}</b>" if a == anio_act else str(a) for a in anios]

    # 1) cantidad por año
    fig = go.Figure()
    for cat in cats:
        fig.add_bar(x=etiquetas, y=g[cat], name=cat, marker_color=ui.cat_color(cat),
                    text=[ui.fnum(v) if v else "" for v in g[cat]], textposition="outside", cliponaxis=False,
                    hovertemplate=f"%{{x}} · {cat}: %{{y:,.1f}} qq<extra></extra>")
    fig.update_layout(barmode="group", legend_itemclick="toggle", legend_itemdoubleclick="toggleothers")
    ui.style(fig, height=400)
    ui.headroom(fig, g[cats].max().max(), 1.15)
    # los años son texto (categorías): si no, Plotly los toma como números y descarta «<b>2026</b>»
    fig.update_xaxes(type="category")
    fig.update_layout(hovermode="closest", uniformtext=dict(mode="show", minsize=8))
    st.markdown("**Quintales disueltos por año**")
    ui.show(fig)

    # 2) variación % del año actual frente a cada año anterior
    previos = [a for a in anios if a < anio_act]
    if anio_act in anios and previos:
        act = g.loc[anio_act]
        fig = go.Figure()
        for cat in cats + ["Total"]:
            vals, txt, hov = [], [], []
            for a in previos:
                prev = g.loc[a, cat]
                v = (act[cat] - prev) / prev * 100 if prev else None
                vals.append(v)
                txt.append("" if v is None else (("+" if v > 0 else "") + ui.fnum(v) + " %"))
                hov.append(f"{cat}: {anio_act} {ui.fnum(act[cat])} qq vs {a} {ui.fnum(prev)} qq · "
                           f"diferencia {('+' if act[cat] - prev > 0 else '')}{ui.fnum(act[cat] - prev)} qq")
            fig.add_bar(x=[f"vs {a}" for a in previos], y=vals, name=cat, text=txt, textposition="outside",
                        cliponaxis=False, hovertext=hov, hoverinfo="text",
                        marker_color=ui.cat_color(cat) if cat != "Total" else "#6D6E71")
        fig.add_hline(y=0, line=dict(color="#6D6E71", width=1))
        fig.update_layout(barmode="group", legend_itemclick="toggle", legend_itemdoubleclick="toggleothers",
                          hovermode="closest")
        ui.style(fig, height=380, ytitle=f"Variación de {anio_act} (%)")
        fig.update_yaxes(ticksuffix=" %", rangemode="normal")
        fig.update_xaxes(type="category")
        fig.update_layout(uniformtext=dict(mode="show", minsize=8))  # mostrar todas las etiquetas de %
        vals = [v for tr in fig.data for v in tr.y if v is not None] or [0]
        alto = max(max(vals), 0) or 10
        bajo = min(min(vals), 0)
        fig.update_yaxes(range=[bajo * 1.3 - (alto * 0.08 if bajo < 0 else 0), alto * 1.2])
        st.markdown(f"**Variación de {anio_act} frente a cada año anterior** "
                    "<span style='color:#6D6E71;font-size:.85rem'>(positivo = más reproceso que ese año; "
                    "negativo = menos)</span>", unsafe_allow_html=True)
        ui.show(fig)

    with st.expander("Ver tabla del comparativo"):
        t = g.copy()
        t.index = [str(a) for a in anios]
        t.index.name = "Año"
        filas_var = {}
        if anio_act in anios:
            for a in previos:
                filas_var[f"Var. % {anio_act} vs {a}"] = [
                    (g.loc[anio_act, cc] - g.loc[a, cc]) / g.loc[a, cc] * 100 if g.loc[a, cc] else None
                    for cc in t.columns]
        ui.show_pivot(t)
        if filas_var:
            st.caption("Variación porcentual (%)")
            ui.show_pivot(pd.DataFrame(filas_var, index=t.columns).T)

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
