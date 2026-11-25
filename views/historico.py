"""Histórico interanual: el año actual frente a los años anteriores, por categoría (cantidad y %)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
brand.header("Histórico interanual", "Año actual frente a los años anteriores: cantidad y variación porcentual")

f1, f2 = st.columns([1, 2])
NOMBRE = f1.radio("Analizar", ["Disolución", "Ingreso", "Stock fin de mes"], horizontal=True, key="hist_medida",
                  help="Disolución: estibas disueltas o mezcladas. Ingreso: quintales cuya fecha de ingreso cae "
                       "en el mes de la hoja. Stock fin de mes: estado «Cuantificado» al cierre de cada mes.")
ES_STOCK = NOMBRE == "Stock fin de mes"
MES_A_MES = False
if NOMBRE == "Disolución":
    estados_all = sorted(c["traz"]["estado"].unique())
    estados = f2.multiselect("Estados que cuentan como disolución", estados_all,
                             default=[e for e in D.ESTADOS_DISOLUCION if e in estados_all], key="hist_estados")
    fuente = D.disolucion(c["traz_dim"], estados or None)
elif NOMBRE == "Ingreso":
    fuente = D.ingreso(c["traz_dim"])
else:
    fuente = D.stock(c["traz_dim"])
    # el stock es una foto de cada cierre: no se suma por año
    MEDIDA_STOCK = f2.radio("Comparar", ["Mes a mes", "Promedio mensual del año", "Cierre del último mes comparable"],
                            horizontal=True, key="hist_stock_medida",
                            help="Mes a mes: stock al cierre de cada mes, una línea por año. "
                                 "Promedio: promedio del stock de cierre de los meses del periodo de cada año. "
                                 "Cierre: stock al cierre del mismo mes (el último mes con datos del año actual).")
    MES_A_MES = MEDIDA_STOCK == "Mes a mes" and not fuente.empty
    if MES_A_MES:
        _anio_act = int(max(c["anios"])) if c["anios"] else int(fuente["anio"].max())
        hojas_m = c["traz_dim"][["anio", "mes"]].drop_duplicates()
        hojas_m = hojas_m[hojas_m["anio"] <= _anio_act].sort_values(["anio", "mes"])
        mm = fuente[fuente["anio"] <= _anio_act].groupby(["anio", "mes", "categoria"])["qq"].sum() \
            .unstack(fill_value=0.0)
        # los meses con hoja pero sin stock quedan en 0 (no desaparecen de la línea)
        mm = mm.reindex(pd.MultiIndex.from_frame(hojas_m), fill_value=0.0)
        cats_m = [x for x in ui.CAT_COLORS if x in mm.columns and mm[x].any()] + \
                 [x for x in mm.columns if x not in ui.CAT_COLORS and mm[x].any()]
        cat_sel = st.radio("Categoría", ["Todas"] + cats_m, horizontal=True, key="hist_stock_cat")
        serie = mm.sum(axis=1) if cat_sel == "Todas" else mm[cat_sel]
        tabla = serie.unstack("mes").sort_index()  # filas: año · columnas: mes
        anios_m = [int(a) for a in tabla.index]
        previos_m = [a for a in anios_m if a < _anio_act]
        st.caption(f"Stock «Cuantificado» al cierre de cada mes · categoría: **{cat_sel}** · año actual "
                   f"**{_anio_act}** en verde. Haz clic en la leyenda para ocultar o mostrar un año; doble clic deja "
                   "solo ese.")

        def _rampa(n):  # azules de claro (años más antiguos) a oscuro (año anterior al actual)
            a, b = (198, 219, 245), (16, 66, 129)
            return ["#%02x%02x%02x" % tuple(round(a[k] + (b[k] - a[k]) * (i / max(n - 1, 1))) for k in range(3))
                    for i in range(n)]

        fig = go.Figure()
        for anio, color in zip(previos_m, _rampa(len(previos_m))):
            fila = tabla.loc[anio].dropna()
            fig.add_scatter(x=[D.MESES[m - 1] for m in fila.index], y=fila.values, name=str(anio),
                            mode="lines+markers", line=dict(color=color, width=1.8), marker=dict(size=6),
                            hovertemplate=f"{anio} · %{{x}}: %{{y:,.1f}} qq<extra></extra>")
        if len(previos_m) >= 2:
            prom = tabla.loc[previos_m].mean()
            fig.add_scatter(x=[D.MESES[m - 1] for m in prom.index], y=prom.values,
                            name=f"Promedio {previos_m[0]}–{previos_m[-1]}", mode="lines",
                            line=dict(color="#6D6E71", width=2, dash="dot"),
                            hovertemplate="Promedio años anteriores · %{x}: %{y:,.1f} qq<extra></extra>")
        if _anio_act in anios_m:
            fila = tabla.loc[_anio_act].dropna()
            fig.add_scatter(x=[D.MESES[m - 1] for m in fila.index], y=fila.values, name=f"{_anio_act} (actual)",
                            mode="lines+markers+text", line=dict(color="#267939", width=3.5),
                            marker=dict(size=9, color="#267939", line=dict(color="#FFFFFF", width=1.5)),
                            text=[ui.fnum(v) for v in fila.values], textposition="top center",
                            hovertemplate=f"{_anio_act} · %{{x}}: %{{y:,.1f}} qq<extra></extra>")
        fig.update_layout(legend_itemclick="toggle", legend_itemdoubleclick="toggleothers", hovermode="x unified")
        ui.style(fig, height=430)
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=D.MESES)
        fig.update_layout(hovermode="x unified")
        ui.headroom(fig, float(tabla.max().max() or 1), 1.15)
        st.markdown(f"**Stock al cierre de cada mes, por año (qq) · {cat_sel}**")
        ui.show(fig)

        t = tabla.copy()
        t.columns = [D.MESES[m - 1] for m in t.columns]
        t["Promedio"] = tabla.mean(axis=1)
        t.index = [str(a) for a in anios_m]
        t.index.name = "Año"
        if _anio_act in anios_m and (_anio_act - 1) in anios_m:
            ant = tabla.loc[_anio_act - 1]
            act = tabla.loc[_anio_act]
            var = ((act - ant) / ant.where(ant != 0) * 100)
            var.index = [D.MESES[m - 1] for m in var.index]
            var["Promedio"] = (t.loc[str(_anio_act), "Promedio"] / t.loc[str(_anio_act - 1), "Promedio"] - 1) * 100 \
                if t.loc[str(_anio_act - 1), "Promedio"] else None
            t.loc[f"Var. % vs {_anio_act - 1}"] = var
        st.markdown("**Tabla: stock al cierre de cada mes (qq)**")
        ui.show_pivot(t)
        st.caption("La última fila es la variación porcentual del año actual frente al anterior en cada mes "
                   "(vacía si el año anterior tenía 0 qq en ese mes).")
if fuente.empty:
    ui.no_data(); st.stop()

# Usa toda la historia (con los filtros de categoría/tipo/código de la barra lateral; el año elegido
# en la barra lateral se toma como «año actual»).
# ---------------------------------------------------------------------------
hist = fuente
if MES_A_MES:
    pass  # la vista mes a mes del stock ya se dibujó arriba
elif hist["anio"].nunique() < 2:
    st.info(f"Se necesitan al menos dos años con {NOMBRE.lower()} para comparar.")
else:
    anio_act = int(max(c["anios"])) if c["anios"] else int(hist["anio"].max())
    hist = hist[hist["anio"] <= anio_act]
    ult_mes = int(hist.loc[hist["anio"] == anio_act, "mes"].max()) if (hist["anio"] == anio_act).any() else 12
    a1, a2 = st.columns([2, 1], vertical_alignment="center")
    mismo = a2.toggle(f"Mismo periodo (Ene–{D.MESES[ult_mes - 1]})", value=ult_mes < 12, key="hist_mismo",
                      help=f"{anio_act} va hasta {D.MESES_LARGO[ult_mes - 1].lower()}: para comparar de forma justa, "
                           f"cada año se cuenta solo de enero a {D.MESES_LARGO[ult_mes - 1].lower()}. "
                           "Apágalo para ver los años completos.")
    if mismo:
        hist = hist[hist["mes"] <= ult_mes]
    periodo_txt = f"enero–{D.MESES_LARGO[ult_mes - 1].lower()} de cada año" if mismo else "años completos"
    a1.caption(f"Año actual: **{anio_act}** · {periodo_txt}. Haz clic en la leyenda para ocultar o mostrar una "
               "serie (p. ej. Avería); doble clic deja solo esa.")

    if not ES_STOCK:
        g = hist.groupby(["anio", "categoria"])["qq"].sum().unstack(fill_value=0.0)
        TITULO = f"Quintales de {NOMBRE.lower()} por año"
    else:
        # stock por mes y categoría; los meses con hoja pero sin stock cuentan como 0 (no se omiten del promedio)
        hojas = c["traz_dim"][["anio", "mes"]].drop_duplicates()
        hojas = hojas[hojas["anio"] <= anio_act]
        if mismo:
            hojas = hojas[hojas["mes"] <= ult_mes]
        m = hist.groupby(["anio", "mes", "categoria"])["qq"].sum().unstack(fill_value=0.0)
        m = m.reindex(pd.MultiIndex.from_frame(hojas.sort_values(["anio", "mes"])), fill_value=0.0)
        if MEDIDA_STOCK.startswith("Promedio"):
            g = m.groupby(level="anio").mean()
            TITULO = f"Stock de fin de mes: promedio mensual por año (qq, {periodo_txt})"
        else:
            g = m.xs(ult_mes, level="mes") if ult_mes in m.index.get_level_values("mes") else m.iloc[0:0]
            TITULO = f"Stock al cierre de {D.MESES_LARGO[ult_mes - 1].lower()} de cada año (qq)"
        g = g.loc[:, (g != 0).any(axis=0)]
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
    if anio_act in anios:  # resaltar el año actual: fondo sombreado + rótulo
        i = anios.index(anio_act)
        fig.add_vrect(x0=i - 0.5, x1=i + 0.5, fillcolor="#267939", opacity=0.08, line_width=0, layer="below")
        fig.add_annotation(x=i, y=1, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"<b>Año actual {anio_act}</b>", font=dict(color="#267939", size=12))
    st.markdown(f"**{TITULO}**")
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
            fig.add_bar(x=[f"{anio_act} vs {a}" for a in previos], y=vals, name=cat, text=txt, textposition="outside",
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
                    f"<span style='color:#6D6E71;font-size:.85rem'>(positivo = más {'stock' if ES_STOCK else NOMBRE.lower()} que ese año; "
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

