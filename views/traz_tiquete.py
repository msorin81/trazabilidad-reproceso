import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import ui

c = ui.ctx()
vin, tiq, traz = c["vinculos"], c["tiq"], c["traz"]

brand.header("Trazabilidad por tiquete",
             "Soporte PDF de cada tiquete de báscula y eventos de las estibas reprocesadas")
if vin.empty and tiq.empty:
    ui.no_data(); st.stop()

# ---------------------------------------------------------------------------
# Tabla maestra: un registro por tiquete (báscula ∪ pestaña «Trazabilidad tiquetes»)
# ---------------------------------------------------------------------------
bas = (tiq.dropna(subset=["tiquete"]).groupby("tiquete")
       .agg(fecha_bascula=("fecha", "min"), periodo_b=("periodo", "min"), qq_tiquete=("qq_tiquete", "sum"),
            qq_fisico=("qq_fisico", "sum"), diferencia=("diferencia", "sum")))
if vin.empty:
    vv = pd.DataFrame(columns=["tiquete", "fecha", "anio", "pdf_tipo", "pdf_url", "pdf_nombre", "sap_url",
                               "sap_nombre", "observacion", "tiquete_txt"])
else:
    vv = vin.sort_values(["pdf_url"], na_position="last").drop_duplicates("tiquete")
vv = vv.set_index("tiquete")[["fecha", "anio", "pdf_tipo", "pdf_url", "pdf_nombre", "sap_url", "sap_nombre",
                              "observacion", "tiquete_txt"]]
dis = traz[traz["tiquete"].notna() & traz["estado"].isin(D.ESTADOS_DISOLUCION)]
dis = dis.drop_duplicates(subset=["tiquete", "estiba", "qq", "fecha_reproceso"])
est = dis.groupby("tiquete").agg(estibas=("estiba", "nunique"), qq_estibas=("qq", "sum"),
                                 causas=("causa", lambda x: " / ".join(sorted(set(map(str, x))))),
                                 categorias=("categoria", lambda x: " / ".join(sorted(set(map(str, x))))),
                                 fecha_reproceso=("fecha_reproceso", "max"))
m = bas.join(vv, how="outer").join(est, how="left")
m["fecha_ref"] = m["fecha_bascula"].fillna(m["fecha"]).fillna(m["fecha_reproceso"])
m["anio_ref"] = m["fecha_ref"].dt.year.fillna(m["anio"]).fillna(m["periodo_b"].dt.year)
m["mes_ref"] = m["fecha_ref"].dt.month.fillna(m["periodo_b"].dt.month)
m["en_pestana"] = m.index.isin(vv.index)
m["soporte"] = m.apply(lambda r: "PDF en línea" if isinstance(r["pdf_url"], str) else
                       ("Archivo local" if isinstance(r["pdf_nombre"], str) else
                        ("Sin vínculo en la pestaña" if r["en_pestana"] else "No registrado en la pestaña")), axis=1)
m = m.reset_index().rename(columns={"index": "tiquete"})

# filtros globales de año / mes
if c["anios"]:
    m = m[m["anio_ref"].isin(c["anios"])]
if c["meses"]:
    m = m[m["mes_ref"].isin(c["meses"])]
if m.empty:
    ui.no_data(); st.stop()

n = len(m)
n_pdf = int((m["soporte"] == "PDF en línea").sum())
n_loc = int((m["soporte"] == "Archivo local").sum())
n_sinv = int((m["soporte"] == "Sin vínculo en la pestaña").sum())
n_noreg = int((m["soporte"] == "No registrado en la pestaña").sum())
brand.grupo("Tiquetes del periodo filtrado", "báscula + pestaña «Trazabilidad tiquetes» de los libros de stock")
k = st.columns(5)
ui.kpi(k[0], "Tiquetes", ui.fnum(n, 0), icon="receipt_long")
ui.kpi(k[1], "Con soporte PDF", ui.fnum(n_pdf + n_loc, 0), icon="picture_as_pdf",
       nota=f"{ui.fpct((n_pdf + n_loc) / n)} del total" + (f" · {n_loc} en ruta local" if n_loc else ""),
       help="Tiquetes con vínculo al PDF de trazabilidad. «Ruta local»: el vínculo apunta a un archivo en el "
            "computador de quien lo registró (file:///C:\\…); no se abre desde la app, se muestra el nombre del PDF.")
ui.kpi(k[2], "Sin vínculo en la pestaña", ui.fnum(n_sinv, 0), icon="link_off",
       help="Están en la pestaña «Trazabilidad tiquetes» pero la celda «Trazabilidad» no tiene vínculo al PDF.")
ui.kpi(k[3], "No registrados en la pestaña", ui.fnum(n_noreg, 0), icon="playlist_remove",
       help="Tiquetes de la tabla de báscula del mes que aún no se han anotado en la pestaña «Trazabilidad tiquetes».")
ui.kpi(k[4], "QQ tiquete", ui.fnum(m["qq_tiquete"].sum()), icon="scale")

# ---------------------------------------------------------------------------
st.subheader("Tiquetes y soporte de trazabilidad")
f1, f2 = st.columns([1, 2])
q = f1.text_input("Buscar tiquete o estiba", key="tt_buscar", placeholder="p. ej. 46994").strip()
filtro_sop = f2.multiselect("Soporte", ["PDF en línea", "Archivo local", "Sin vínculo en la pestaña",
                                        "No registrado en la pestaña"], key="tt_sop", placeholder="Todos")
vista = m.copy()
if q:
    est_q = set(dis.loc[dis["estiba"].astype(str).str.strip() == q.lstrip("0"), "tiquete"])
    vista = vista[vista["tiquete"].astype(str).str.contains(q, regex=False) | vista["tiquete"].isin(est_q)]
if filtro_sop:
    vista = vista[vista["soporte"].isin(filtro_sop)]
vista = vista.sort_values("fecha_ref", ascending=False).reset_index(drop=True)
st.caption("Haz clic en una fila para ver la trazabilidad completa del tiquete. "
           "«Abrir» lleva al PDF en SharePoint (requiere permiso de la cuenta del Ingenio).")
tabla = pd.DataFrame({
    "Tiquete": vista["tiquete"], "Fecha": vista["fecha_ref"], "Soporte PDF": vista["pdf_url"],
    "Estado del soporte": vista["soporte"],
    "Archivo (ruta local)": vista["pdf_nombre"], "QQ tiquete": vista["qq_tiquete"], "QQ físico": vista["qq_fisico"],
    "Diferencia": vista["diferencia"], "Estibas": vista["estibas"], "Causas": vista["causas"],
    "Observación": vista["observacion"],
})
if tabla["Archivo (ruta local)"].isna().all():
    tabla = tabla.drop(columns="Archivo (ruta local)")
if tabla["Observación"].isna().all():
    tabla = tabla.drop(columns="Observación")
ev = st.dataframe(
    tabla, **ui.WIDE, hide_index=True, on_select="rerun", selection_mode="single-row", key="tt_tabla",
    column_config={
        "Fecha": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "Soporte PDF": st.column_config.LinkColumn("Soporte PDF", display_text="📄 Abrir"),
        "QQ tiquete": st.column_config.NumberColumn(format="%.1f"),
        "QQ físico": st.column_config.NumberColumn(format="%.1f"),
        "Diferencia": st.column_config.NumberColumn(format="%.1f"),
        "Estibas": st.column_config.NumberColumn(format="%d"),
    })
st.download_button("⬇️ Descargar tabla", ui.to_excel_bytes({"tiquetes": tabla}), file_name="trazabilidad_tiquetes.xlsx",
                   key="dl_tt")

filas = []
try:
    filas = ev["selection"]["rows"]
except Exception:  # noqa: BLE001
    pass
if not filas and len(vista) == 1:
    filas = [0]

# ---------------------------------------------------------------------------
# Ficha del tiquete: eventos de trazabilidad
# ---------------------------------------------------------------------------
if not filas:
    st.info("Selecciona un tiquete en la tabla para ver su trazabilidad completa.")
    st.stop()
r = vista.iloc[filas[0]]
tq = r["tiquete"]
st.subheader(f"Tiquete {tq}")
grupo = r["tiquete_txt"] if isinstance(r.get("tiquete_txt"), str) and r["tiquete_txt"] != tq else None
a, b = st.columns([3, 1], vertical_alignment="center")
a.markdown(
    " · ".join(x for x in [
        f"Fecha: **{r['fecha_ref']:%Y-%m-%d}**" if pd.notna(r["fecha_ref"]) else None,
        f"QQ tiquete **{ui.fnum(r['qq_tiquete'])}** vs físico **{ui.fnum(r['qq_fisico'])}** "
        f"(dif. {ui.fnum(r['diferencia'])})" if pd.notna(r["qq_tiquete"]) else "No está en la tabla de báscula",
        f"Registrado junto con: {grupo}" if grupo else None,
        f"Observación: {r['observacion']}" if isinstance(r.get("observacion"), str) else None,
    ] if x))
if isinstance(r["pdf_url"], str):
    b.link_button("📄 Abrir soporte PDF", r["pdf_url"], **ui.WIDE)
elif isinstance(r["pdf_nombre"], str):
    b.caption(f"Soporte en ruta local: **{r['pdf_nombre']}**")
else:
    b.caption("Sin soporte PDF registrado")
if isinstance(r.get("sap_url"), str):
    b.link_button("📄 Soporte SAP - Bodega", r["sap_url"], **ui.WIDE)

ee = dis[dis["tiquete"] == tq].copy()
if ee.empty:
    st.info("No hay estibas de la trazabilidad asociadas a este tiquete (estado Disuelto o Mezclado).")
    st.stop()

EVENTOS = [("fecha_produccion", "Producción", "#6D6E71", "circle"), ("fecha_ingreso", "Ingreso a reproceso", ui.BLUE, "square"),
           ("fecha_pesaje", "Pesaje", "#1baf7a", "diamond"), ("fecha_reproceso", "Disolución / reproceso", ui.ORANGE, "x")]
ee["etiqueta"] = "Estiba " + ee["estiba"].astype(str) + " · " + ee["qq"].map(lambda v: ui.fnum(v)) + " qq"
ee = ee.sort_values("fecha_ingreso")
st.markdown(f"**Eventos de trazabilidad de las {len(ee)} estibas** "
            f"({ui.fnum(ee['qq'].sum())} qq · {', '.join(sorted(set(ee['categoria'].astype(str))))})")
fig = go.Figure()
for _, rr in ee.iterrows():
    xs = [rr[c_] for c_, *_ in EVENTOS if pd.notna(rr.get(c_))]
    if len(xs) >= 2:
        fig.add_scatter(x=[min(xs), max(xs)], y=[rr["etiqueta"]] * 2, mode="lines", showlegend=False,
                        line=dict(color="#C9CACC", width=2), hoverinfo="skip")
for col, nombre, color, simb in EVENTOS:
    d = ee[ee[col].notna()] if col in ee.columns else ee.iloc[0:0]
    if d.empty:
        continue
    fig.add_scatter(x=d[col], y=d["etiqueta"], mode="markers", name=nombre,
                    marker=dict(color=color, size=11, symbol=simb, line=dict(color="#FFFFFF", width=1)),
                    customdata=d[["causa", "categoria"]].astype(str).values,
                    hovertemplate=f"%{{y}}<br>{nombre}: %{{x|%Y-%m-%d}}<br>%{{customdata[1]}} · %{{customdata[0]}}"
                                  "<extra></extra>")
if pd.notna(r.get("fecha_bascula")):
    fig.add_vline(x=r["fecha_bascula"], line=dict(color="#267939", width=2, dash="dash"))
    fig.add_annotation(x=r["fecha_bascula"], y=1.02, yref="paper", text="Tiquete báscula", showarrow=False,
                       font=dict(color="#267939", size=11), xanchor="left")
ui.style(fig, height=max(240, 90 + 30 * len(ee)), ytitle=None)
fig.update_yaxes(type="category", autorange="reversed")
fig.update_xaxes(tickformat="%d/%m/%y")
fig.update_layout(hovermode="closest")
ui.show(fig)

ui.detail_table(ee, ["estiba", "qq", "estado", "categoria", "causa", "codigo", "fecha_produccion_txt",
                     "fecha_ingreso", "fecha_pesaje", "fecha_reproceso", "dias_en_stock", "punto_disolucion",
                     "equipo", "resp_laboratorio", "observaciones"],
                key=f"tt_{tq}", filename=f"trazabilidad_tiquete_{tq}")
