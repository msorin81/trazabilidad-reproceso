import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import plano
from reproceso import ui

c = ui.ctx()
inv, zonas = c["inv"], c["inv_zonas"]

brand.header("Inventario físico de la bodega de reproceso",
             "Plano de ubicación de estibas (formato F-RPR-266) y conciliación con la trazabilidad")
if inv.empty:
    st.info("No se encontró el libro «AAAA-Inventario_Fisico_Reproceso.xlsx» (pestañas con nombre de fecha "
            "AAAA-MM-DD) en la carpeta de los Excel.")
    st.stop()

fechas = sorted(pd.to_datetime(inv["fecha"].unique()), reverse=True)
f1, f2, f3 = st.columns([1.1, 1, 1.1])
fecha = f1.selectbox("Fecha del conteo", fechas, format_func=lambda f: f"{f:%d/%m/%Y}", key="inv_fecha",
                     help="Cada pestaña del libro de inventario es un conteo; por defecto, el más reciente.")
buscar = f2.text_input("Buscar estiba", key="inv_buscar", placeholder="p. ej. 2170").strip().lstrip("0")
rotulos = f3.toggle("Mostrar rótulos «qq-estiba»", value=True, key="inv_rotulos",
                    help="Apágalo para ver el plano más compacto (la información sigue en el recuadro "
                         "al pasar el mouse).")

u = inv[inv["fecha"] == fecha].copy()
anteriores = [f for f in fechas if f < fecha]
prev = inv[inv["fecha"] == anteriores[0]] if anteriores else None


# --- cruce con la trazabilidad: stock «Cuantificado» de la hoja del mes del conteo (o la anterior disponible)
def stock_traz(f: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    tr = c["traz"]
    p = pd.Timestamp(f.year, f.month, 1)
    cand = tr[tr["periodo"] <= p]
    if cand.empty:
        return pd.DataFrame(), None
    per = cand["periodo"].max()
    return D.stock(cand[cand["periodo"] == per]), per


stk, per_t = stock_traz(fecha)
if not stk.empty:
    s = stk.assign(estiba=stk["estiba"].astype(str).str.strip().str.lstrip("0"))
    agg = s.groupby("estiba").agg(t_qq=("qq", "sum"), t_categoria=("categoria", "first"),
                                  t_causa=("causa", lambda x: " / ".join(sorted(set(map(str, x))))),
                                  t_ingreso=("fecha_ingreso", "min"))
    agg["t_dias"] = (fecha - agg["t_ingreso"]).dt.days
    u = u.merge(agg, left_on="estiba", right_index=True, how="left")

# ---------------------------------------------------------------------------
tot, n_est = u["qq"].sum(), len(u)
pos = u.dropna(subset=["bloque"]).groupby(["zona", "bloque", "columna"]).ngroups
brand.grupo(f"Conteo físico del {fecha:%d/%m/%Y}",
            f"comparado con el conteo anterior ({anteriores[0]:%d/%m/%Y})" if anteriores else "primer conteo del libro")
k = st.columns(5)
d_qq = None if prev is None else tot - prev["qq"].sum()
d_n = None if prev is None else n_est - len(prev)
ui.kpi(k[0], "Inventario físico (qq)", ui.fnum(tot),
       delta=None if not d_qq else f"{ui.fnum(d_qq)} qq", delta_color="inverse",
       help="Suma de las celdas «qq-estiba» del plano.", icon="warehouse",
       nota="Sin cambio frente al conteo anterior" if d_qq == 0 else None)
ui.kpi(k[1], "Estibas", ui.fnum(n_est, 0), delta=None if not d_n else f"{d_n:+d}", delta_color="inverse")
ui.kpi(k[2], "Posiciones ocupadas", ui.fnum(pos, 0), icon="grid_view",
       help="Combinaciones zona · bloque · columna con al menos una estiba.")
if not stk.empty:
    q_t = stk["qq"].sum()
    ui.kpi(k[3], "Stock trazabilidad (qq)", ui.fnum(q_t), icon="fact_check",
           help=f"Estado «Cuantificado» en la hoja de {D.periodo_label(per_t)} del libro de stock.")
    ui.kpi(k[4], "Físico − trazabilidad (qq)", ui.fnum(tot - q_t), icon="difference",
           help="Diferencia entre el conteo físico y el stock registrado. Ver la conciliación más abajo. "
                "La hoja de trazabilidad refleja el estado actual del mes, así que en conteos de días "
                "anteriores del mismo mes puede haber diferencias por movimientos posteriores.")

# --- leyenda: colores del Excel con lo que hay en este conteo
ley = c["inv_leyenda"]
ley = ley[ley["fecha"] == fecha].sort_values("orden") if not ley.empty else ley
por_cond = u.groupby("condicion").agg(qq=("qq", "sum"), n=("qq", "size"))
col_cond = dict(zip(u["condicion"], u["color"]))
if not ley.empty:
    col_cond.update(dict(zip(ley["condicion"], ley["color"])))
orden = list(ley["condicion"]) if not ley.empty else []
orden += [x for x in por_cond.index if x not in orden]
chips = []
for cond in orden:
    q = por_cond["qq"].get(cond, 0)
    n = por_cond["n"].get(cond, 0)
    sw = f"#{col_cond.get(cond) or 'FFFFFF'}"
    op = "1" if n else ".45"
    chips.append(f'<span style="display:inline-flex;align-items:center;gap:6px;margin:3px 14px 3px 0;opacity:{op}">'
                 f'<span style="width:16px;height:12px;background:{sw};border:1px solid #9A9B9D;'
                 f'display:inline-block"></span><span style="font-size:.85rem">{cond}'
                 + (f' · <b>{ui.fnum(q)} qq</b> ({n})' if n else "") + "</span></span>")
marcas = u["color_texto"].dropna().map(lambda h: {"E46C0A": "naranja", "FFFF00": "amarillo"}.get(h, "otro color"))
for nombre, cnt in marcas.value_counts().items():
    chips.append(f'<span style="display:inline-flex;align-items:center;gap:6px;margin:3px 14px 3px 0">'
                 f'<span style="color:{plano.MARCA_TEXTO.get(nombre, "#1A1A1A")}">◀</span>'
                 f'<span style="font-size:.85rem">texto {nombre} en el Excel ({cnt})</span></span>')
st.markdown('<div style="margin:6px 0 2px 0">' + "".join(chips) + "</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Plano por zona
# ---------------------------------------------------------------------------
st.subheader("Plano de la bodega")
st.caption("Pasa el mouse sobre una estiba para ver su detalle; haz clic o arrastra un recuadro para "
           "seleccionar estibas y verlas en la tabla de abajo. Columnas y bloques numerados como en el Excel.")
zf = zonas[zonas["fecha"] == fecha].sort_values("orden") if not zonas.empty else pd.DataFrame()
resaltar = {buscar} if buscar else None
if buscar:
    hall = u[u["estiba"] == buscar]
    if hall.empty:
        st.warning(f"La estiba {buscar} no aparece en el conteo del {fecha:%d/%m/%Y}.")
    else:
        st.success(" · ".join(f"Estiba {buscar}: {r.zona}, bloque {int(r.bloque)}, columna {r.columna}, "
                              f"{ui.fnum(r.qq)} qq ({r.condicion})" for r in hall.itertuples()))

seleccion = []
if zf.empty:
    st.info("No se reconocieron zonas en esta pestaña.")
else:
    nombres = []
    for z in zf.itertuples():
        q = u.loc[u["zona"] == z.zona, "qq"].sum()
        nombres.append(f"{z.zona} · {ui.fnum(q)} qq" if q else f"{z.zona} · vacía")
    tabs = st.tabs(nombres)
    for tab, z in zip(tabs, zf.itertuples()):
        with tab:
            ez = u[u["zona"] == z.zona]
            meta = {"bloques": z.bloques, "niveles": z.niveles, "columnas": str(z.columnas).split(",")}
            fig = plano.figura(ez, meta, compacto=not rotulos, resaltar=resaltar)
            ev = st.plotly_chart(fig, **ui.WIDE, config={"displaylogo": False, "displayModeBar": False},
                                 key=f"plano_{z.orden}", on_select="rerun", selection_mode=("points", "box"))
            try:
                for p in ev["selection"]["points"]:
                    cd = p.get("customdata")
                    cd = cd[0] if isinstance(cd, (list, tuple)) else cd
                    if cd is not None:
                        seleccion.append(int(cd))
            except Exception:  # noqa: BLE001
                pass
    sin_ubicar = u[u["zona"] == "Sin ubicar"]
    if not sin_ubicar.empty:
        st.warning(f"{len(sin_ubicar)} celdas «qq-estiba» están fuera de las zonas del plano: "
                   + ", ".join(sin_ubicar["celda"]))

COLS_DET = {"zona": "Zona", "bloque": "Bloque", "columna": "Columna", "nivel": "Nivel", "celda": "Celda Excel",
            "estiba": "Estiba", "qq": "Quintales", "condicion": "Tipo (color Excel)", "t_categoria": "Categoría (traz.)",
            "t_causa": "Causa (traz.)", "t_dias": "Días en stock", "t_ingreso": "Fecha ingreso"}


def tabla(df: pd.DataFrame):
    t = df.copy()
    t["nivel"] = t["nivel"] + 1
    t = t[[k for k in COLS_DET if k in t.columns]].rename(columns=COLS_DET)
    st.dataframe(t, **ui.WIDE, hide_index=True,
                 column_config={"Quintales": st.column_config.NumberColumn(format="%.1f"),
                                "Fecha ingreso": st.column_config.DateColumn(format="YYYY-MM-DD")})
    return t


if seleccion:
    sel = u.loc[[i for i in seleccion if i in u.index]]
    brand.grupo(f"Estibas seleccionadas: {len(sel)}", f"{ui.fnum(sel['qq'].sum())} qq")
    tabla(sel.sort_values(["zona_orden", "bloque", "col_pos", "nivel"]))

# ---------------------------------------------------------------------------
a, b = st.columns(2)
with a:
    st.subheader("Quintales por tipo de producto")
    g = por_cond["qq"].sort_values()
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h",
                           marker=dict(color=[f"#{col_cond.get(x) or 'CCCCCC'}" for x in g.index],
                                       line=dict(color="#9A9B9D", width=1)),
                           text=[ui.fnum(v) for v in g.values], textposition="outside",
                           hovertemplate="%{y}: %{x:,.1f} qq<extra></extra>"))
    ui.style(fig, height=max(220, 60 + 42 * len(g)), legend=False, ytitle=None)
    fig.update_xaxes(range=[0, max(g.max(), 1) * 1.25], title="Quintales")
    fig.update_yaxes(type="category")
    ui.show(fig)
with b:
    st.subheader("Quintales por zona")
    gz = u.groupby(["zona_orden", "zona"])["qq"].sum().reset_index().sort_values("zona_orden")
    fig = go.Figure(go.Bar(x=gz["zona"], y=gz["qq"], marker_color=ui.BLUE,
                           text=[ui.fnum(v) for v in gz["qq"]], textposition="outside",
                           hovertemplate="%{x}: %{y:,.1f} qq<extra></extra>"))
    ui.style(fig, height=max(220, 60 + 42 * len(g)), legend=False)
    ui.headroom(fig, gz["qq"].max(), 1.2)
    ui.show(fig)

# ---------------------------------------------------------------------------
st.subheader("Evolución del inventario físico")
serie = inv.groupby("fecha")["qq"].sum().sort_index()
fig = go.Figure()
fig.add_scatter(x=serie.index, y=serie.values, name="Inventario físico (conteo)", mode="lines+markers",
                line=dict(color=ui.FLOW_COLORS["Stock fin de mes"], width=2), marker=dict(size=7),
                hovertemplate="%{x|%d/%m/%Y}: %{y:,.1f} qq<extra>Físico</extra>")
mens = D.mensual(D.stock(c["traz"])).set_index("periodo")["qq"]
mens = mens[(mens.index >= serie.index.min() - pd.offsets.MonthBegin(1)) & (mens.index <= serie.index.max())]
if not mens.empty:
    fin = mens.index + pd.offsets.MonthEnd(0)
    fin = fin.where(fin <= pd.Timestamp.today().normalize(), pd.Timestamp.today().normalize())
    fig.add_scatter(x=fin, y=mens.values, name="Stock trazabilidad (fin de mes)", mode="markers+text",
                    marker=dict(symbol="diamond", size=11, color=ui.ORANGE, line=dict(color="#FFFFFF", width=1)),
                    text=[ui.fnum(v) for v in mens.values], textposition="top center",
                    hovertemplate="%{x|%b %Y}: %{y:,.1f} qq<extra>Trazabilidad</extra>")
fig.add_vline(x=fecha, line=dict(color="#6D6E71", width=1, dash="dot"))
ui.style(fig, height=360)
fig.update_xaxes(tickformat="%d/%m/%y")
ui.headroom(fig, max(serie.max(), mens.max() if not mens.empty else 0), 1.15)
ui.show(fig)

# ---------------------------------------------------------------------------
st.subheader("Conciliación físico vs trazabilidad")
if stk.empty:
    st.info("No hay hoja de trazabilidad para el mes de este conteo.")
else:
    st.caption(f"Conteo físico del {fecha:%d/%m/%Y} frente al stock «Cuantificado» de la hoja de "
               f"{D.periodo_label(per_t)}. Los números de estiba se repiten entre lotes, así que la comparación "
               "suma los quintales por número de estiba.")
    fis = u.groupby("estiba").agg(qq_fisico=("qq", "sum"), ubicacion=("zona", lambda x: " / ".join(sorted(set(x)))),
                                  tipo=("condicion", "first"))
    trz = stk.assign(estiba=stk["estiba"].astype(str).str.strip().str.lstrip("0")).groupby("estiba").agg(
        qq_traz=("qq", "sum"), categoria=("categoria", "first"), causa=("causa", "first"))
    cc = fis.join(trz, how="outer")
    cc["estado_conc"] = cc.apply(lambda r: "Solo en físico" if pd.isna(r["qq_traz"]) else
                                 ("Solo en trazabilidad" if pd.isna(r["qq_fisico"]) else
                                  ("Cuadra" if abs(r["qq_fisico"] - r["qq_traz"]) < 0.05 else "Quintales distintos")),
                                 axis=1)
    cc["diferencia"] = cc["qq_fisico"].fillna(0) - cc["qq_traz"].fillna(0)
    resumen = cc.groupby("estado_conc").agg(estibas=("diferencia", "size"), dif=("diferencia", "sum"))
    k = st.columns(4)
    for i, est in enumerate(["Cuadra", "Quintales distintos", "Solo en físico", "Solo en trazabilidad"]):
        n = int(resumen["estibas"].get(est, 0))
        ui.kpi(k[i], est, ui.fnum(n, 0),
               icon={"Cuadra": "check_circle", "Quintales distintos": "rule", "Solo en físico": "warehouse",
                     "Solo en trazabilidad": "link_off"}[est],
               nota=None if est == "Cuadra" or not n else f"{ui.fnum(resumen['dif'].get(est, 0))} qq")
    dif = cc[cc["estado_conc"] != "Cuadra"].reset_index().rename(columns={
        "estiba": "Estiba", "qq_fisico": "QQ físico", "qq_traz": "QQ trazabilidad", "diferencia": "Diferencia",
        "estado_conc": "Resultado", "ubicacion": "Zona", "tipo": "Tipo (color Excel)", "categoria": "Categoría (traz.)",
        "causa": "Causa (traz.)"})
    if dif.empty:
        st.success("Todas las estibas cuadran entre el conteo físico y la trazabilidad.")
    else:
        dif = dif[["Estiba", "Resultado", "QQ físico", "QQ trazabilidad", "Diferencia", "Zona", "Tipo (color Excel)",
                   "Categoría (traz.)", "Causa (traz.)"]].sort_values(["Resultado", "Estiba"])
        for c_ in ("Zona", "Tipo (color Excel)", "Categoría (traz.)", "Causa (traz.)"):
            dif[c_] = dif[c_].fillna("—")
        st.dataframe(dif, **ui.WIDE, hide_index=True,
                     column_config={c_: st.column_config.NumberColumn(format="%.1f")
                                    for c_ in ("QQ físico", "QQ trazabilidad", "Diferencia")})
        st.download_button("⬇️ Descargar conciliación", ui.to_excel_bytes({"conciliacion": dif}),
                           file_name=f"conciliacion_inventario_{fecha:%Y_%m_%d}.xlsx", key="dl_conc")

with st.expander(f"Detalle de las {n_est} estibas del conteo"):
    t = tabla(u.sort_values(["zona_orden", "bloque", "col_pos", "nivel"]))
    st.download_button("⬇️ Descargar inventario", ui.to_excel_bytes({"inventario": t}),
                       file_name=f"inventario_fisico_{fecha:%Y_%m_%d}.xlsx", key="dl_inv")
