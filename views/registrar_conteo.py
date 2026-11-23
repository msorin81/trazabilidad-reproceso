"""Registrar un conteo físico desde la app (opcional). El Excel F-RPR-266 sigue siendo el registro principal:
esta página solo crea / actualiza la pestaña del día en ese mismo libro, a través de Excel."""
import datetime as dt
import os

import pandas as pd
import streamlit as st

from reproceso import brand
from reproceso import data as D
from reproceso import escritura as E
from reproceso import plano
from reproceso import ui

c = ui.ctx()
brand.header("Registrar conteo físico", "Opcional: crea o actualiza la pestaña del día en el libro oficial F-RPR-266")
if c["modo"] != "excel" or not E.disponible():
    st.info("Esta opción solo está disponible en la app local (equipo con Excel y los archivos de OneDrive).")
    st.stop()
inv, zonas, ley_all = c["inv"], c["inv_zonas"], c["inv_leyenda"]
if inv.empty or zonas.empty:
    st.info("Aún no hay conteos en el libro de inventario. Registra el primero directamente en Excel.")
    st.stop()

brand.note("El <b>Excel sigue siendo el registro principal</b>: puedes seguir actualizándolo como siempre. "
           "Aquí partes del último conteo, haces los cambios y la app escribe la pestaña en el mismo libro "
           "(con su formato, colores de la leyenda y fórmulas de conteo). Antes de guardar se hace una "
           "copia de respaldo del libro en <code>app_reproceso/respaldos/</code>.")

# ---------------------------------------------------------------------------
# Fecha, libro y pestaña base
# ---------------------------------------------------------------------------
a, b = st.columns([1, 2])
fecha = pd.Timestamp(a.date_input("Fecha del conteo", value=dt.date.today(), format="DD/MM/YYYY", key="rc_fecha"))
hoja = f"{fecha:%Y-%m-%d}"
archivo = f"{fecha.year}-Inventario_Fisico_Reproceso.xlsx"
ruta = os.path.join(c["data_dir"], archivo)
if not os.path.exists(ruta):
    st.error(f"No existe el libro «{archivo}» en la carpeta de los Excel. Para un año nuevo, crea el libro en Excel "
             "(con al menos un conteo) y vuelve aquí.")
    st.stop()
zl = zonas[zonas["archivo"] == archivo]
fechas_libro = sorted(pd.to_datetime(zl["fecha"].unique()))
existe = fecha in fechas_libro
anteriores = [f for f in fechas_libro if f < fecha]
if not existe and not anteriores:
    st.error(f"«{archivo}» no tiene conteos anteriores al {fecha:%d/%m/%Y} para usar como base.")
    st.stop()
f_base = fecha if existe else anteriores[-1]
hoja_base = zl.loc[zl["fecha"] == f_base, "hoja"].iloc[0]
b.markdown(f"<div style='padding-top:1.9rem'>{'Se <b>actualizará</b> la pestaña' if existe else 'Se <b>creará</b> la pestaña'} "
           f"<b>«{hoja}»</b> a partir de <b>«{hoja_base}»</b> en <code>{archivo}</code>.</div>", unsafe_allow_html=True)

zb = zl[zl["fecha"] == f_base].sort_values("orden")
META = {}
for z in zb.itertuples():
    META[z.zona] = {"orden": z.orden, "bloques": int(z.bloques), "niveles": int(z.niveles),
                    "columnas": str(z.columnas).split(","),
                    "filas_excel": [int(x) for x in str(z.filas_excel).split(",")],
                    "cols_excel": [int(x) for x in str(z.cols_excel).split(",")]}
ley = ley_all[ley_all["fecha"] == f_base].sort_values("orden")
TIPOS = list(dict.fromkeys(ley["condicion"]))
COLOR_TIPO = dict(zip(ley["condicion"], ley["color"]))


def ref(r: int, col: int) -> str:
    s = ""
    while col:
        col, rem = divmod(col - 1, 26)
        s = chr(65 + rem) + s
    return f"{s}{r}"


def celda_de(zona, bloque, columna, nivel) -> str | None:
    m = META.get(zona)
    try:
        bloque, nivel, columna = int(bloque), int(nivel), str(columna).strip()
    except (TypeError, ValueError):
        return None
    if m is None or not 1 <= bloque <= m["bloques"] or not 1 <= nivel <= m["niveles"] or columna not in m["columnas"]:
        return None
    return ref(m["filas_excel"][bloque - 1] + nivel - 1, m["cols_excel"][m["columnas"].index(columna)])


# ---------------------------------------------------------------------------
# Sugerencias: estibas del conteo que la trazabilidad ya reporta como disueltas / mezcladas
# ---------------------------------------------------------------------------
base = inv[inv["fecha"] == f_base].copy()
tr = c["traz"]
per = tr.loc[tr["periodo"] <= pd.Timestamp(fecha.year, fecha.month, 1), "periodo"].max()
sug = {}
if pd.notna(per):
    hoja_t = tr[tr["periodo"] == per].assign(estiba=lambda d: d["estiba"].astype(str).str.strip().str.lstrip("0"))
    en_stock = set(hoja_t.loc[hoja_t["estado"].isin(D.ESTADOS_STOCK), "estiba"])
    dis = hoja_t[hoja_t["estado"].isin(D.ESTADOS_DISOLUCION) & ~hoja_t["estiba"].isin(en_stock)]
    for r in dis.sort_values("fecha_reproceso").itertuples():
        txt = f"{r.estado}"
        if pd.notna(r.fecha_reproceso):
            txt += f" el {r.fecha_reproceso:%d/%m}"
        if isinstance(r.tiquete, str):
            txt += f" · tiquete {r.tiquete}"
        sug[r.estiba] = txt

# ---------------------------------------------------------------------------
# Tabla editable
# ---------------------------------------------------------------------------
clave = f"rc_{archivo}_{hoja_base}_{hoja}"
if st.session_state.get("rc_clave") != clave:
    st.session_state["rc_clave"] = clave
    st.session_state["rc_ver"] = 0
    st.session_state["rc_df"] = pd.DataFrame({
        "Retirar": False,
        "Zona": base["zona"].values,
        "Bloque": base["bloque"].astype("Int64").values,
        "Columna": base["columna"].astype(str).values,
        "Nivel": (base["nivel"] + 1).astype("Int64").values,
        "QQ": base["qq"].values,
        "Estiba": base["estiba"].astype(str).values,
        "Tipo": base["condicion"].values,
        "Sugerencia": base["estiba"].map(sug).fillna("").values,
        "Celda": base["celda"].values,
    }).sort_values(["Zona", "Bloque", "Columna", "Nivel"], key=lambda s: s.map(
        lambda v: META.get(v, {}).get("orden", 99) if s.name == "Zona" else v)).reset_index(drop=True)

df0 = st.session_state["rc_df"]
n_sug = int((df0["Sugerencia"] != "").sum())
st.subheader("Estibas del conteo")
k1, k2, k3 = st.columns([2, 1, 1])
k1.caption("Marca **Retirar** para sacar una estiba; cambia Zona / Bloque / Columna / Nivel para trasladarla; "
           "agrega estibas nuevas en la última fila (➕). La columna *Sugerencia* muestra las que la "
           "trazabilidad ya reporta como disueltas o mezcladas.")
if k2.button(f"Marcar {n_sug} sugeridas", disabled=n_sug == 0, **ui.WIDE, key="rc_marcar",
             help="Marca para retirar las estibas que la trazabilidad reporta como disueltas o mezcladas."):
    df0.loc[df0["Sugerencia"] != "", "Retirar"] = True
    st.session_state["rc_ver"] += 1
    st.rerun()
if k3.button("Restablecer", **ui.WIDE, key="rc_reset", help="Vuelve al conteo base, sin cambios."):
    st.session_state.pop("rc_clave", None)
    st.rerun()

cols_opc = sorted({x for m in META.values() for x in m["columnas"]}, key=lambda v: (len(v), v))
ed = st.data_editor(
    df0, key=f"rc_editor_{st.session_state['rc_ver']}", num_rows="dynamic", hide_index=True, **ui.WIDE,
    height=min(38 * (len(df0) + 2), 560),
    column_config={
        "Retirar": st.column_config.CheckboxColumn("Retirar", width="small"),
        "Zona": st.column_config.SelectboxColumn("Zona", options=list(META), required=True),
        "Bloque": st.column_config.NumberColumn("Bloque", min_value=1, step=1, format="%d", required=True),
        "Columna": st.column_config.SelectboxColumn("Columna", options=cols_opc, required=True),
        "Nivel": st.column_config.NumberColumn("Nivel", min_value=1, step=1, format="%d", required=True,
                                               help="Fila dentro de la posición (1 = la de arriba, como en el Excel)."),
        "QQ": st.column_config.NumberColumn("QQ", min_value=0.5, step=0.5, format="%.1f", required=True),
        "Estiba": st.column_config.TextColumn("Estiba", required=True),
        "Tipo": st.column_config.SelectboxColumn("Tipo (color)", options=TIPOS, required=True),
        "Sugerencia": st.column_config.TextColumn("Sugerencia", disabled=True),
        "Celda": st.column_config.TextColumn("Celda Excel", disabled=True),
    })

# ---------------------------------------------------------------------------
# Cambios, validación y vista previa
# ---------------------------------------------------------------------------
ed = ed.copy()
ed["Retirar"] = ed["Retirar"].fillna(False).astype(bool)
ed["Celda"] = ed["Celda"].where(ed["Celda"].notna() & (ed["Celda"].astype(str) != "None"), None)
errores, ops = [], []
quedan = ed[~ed["Retirar"]].copy()
quedan["destino"] = [celda_de(r.Zona, r.Bloque, r.Columna, r.Nivel) for r in quedan.itertuples()]
quedan["texto"] = [f"{float(q):g}-{str(e).strip()}" if pd.notna(q) and str(e).strip() not in ("", "nan", "None")
                   else None for q, e in zip(quedan["QQ"], quedan["Estiba"])]
for r in quedan.itertuples():
    nombre = f"estiba {r.Estiba}" if isinstance(r.Estiba, str) and r.Estiba.strip() else "fila nueva"
    if r.destino is None:
        m = META.get(r.Zona)
        errores.append(f"{nombre}: ubicación no válida" + (
            f" ({r.Zona}: bloques 1–{m['bloques']}, columnas {', '.join(m['columnas'])}, niveles 1–{m['niveles']})"
            if m else " (elige la zona)"))
    if r.texto is None:
        errores.append(f"{nombre}: faltan quintales o número de estiba")
    if r.Tipo not in TIPOS:
        errores.append(f"{nombre}: elige el tipo (color)")
dup = quedan[quedan["destino"].notna() & quedan["destino"].duplicated(keep=False)]
for celda, g in dup.groupby("destino"):
    errores.append(f"Dos estibas en la misma posición (celda {celda}): {', '.join(g['Estiba'].astype(str))}")

orig = {r.Celda: r for r in df0.itertuples() if isinstance(r.Celda, str)}
n_ret = n_mov = n_new = n_mod = 0
for r in ed.itertuples():
    o = orig.get(r.Celda) if isinstance(r.Celda, str) else None
    if r.Retirar:
        if o is not None:
            ops.append({"accion": "borrar", "celda": r.Celda}); n_ret += 1
        continue
    dest = celda_de(r.Zona, r.Bloque, r.Columna, r.Nivel)
    texto = f"{float(r.QQ):g}-{str(r.Estiba).strip()}" if pd.notna(r.QQ) else None
    if dest is None or texto is None:
        continue
    if o is None:
        ops.append({"accion": "escribir", "celda": dest, "texto": texto, "condicion": r.Tipo}); n_new += 1
        continue
    mismo_tipo = r.Tipo == o.Tipo
    texto_o = f"{float(o.QQ):g}-{o.Estiba}"
    if dest != r.Celda:
        ops.append({"accion": "borrar", "celda": r.Celda})
        ops.append({"accion": "escribir", "celda": dest, "texto": texto, "condicion": r.Tipo,
                    "formato_de": r.Celda if mismo_tipo else None}); n_mov += 1
    elif texto != texto_o or not mismo_tipo:
        ops.append({"accion": "escribir", "celda": dest, "texto": texto, "condicion": r.Tipo,
                    "formato_de": r.Celda if mismo_tipo else None}); n_mod += 1
# (dos estibas en la misma celda final —incluida una que no se mueve— ya se detectan como duplicado arriba)

tot0, tot1 = base["qq"].sum(), pd.to_numeric(quedan["QQ"], errors="coerce").sum()
brand.grupo("Resumen de cambios", f"base «{hoja_base}» → «{hoja}»")
k = st.columns(5)
ui.kpi(k[0], "Inventario (qq)", ui.fnum(tot1), delta=f"{ui.fnum(tot1 - tot0)} qq" if tot1 != tot0 else None,
       delta_color="inverse", icon="warehouse")
ui.kpi(k[1], "Retiradas", ui.fnum(n_ret, 0), icon="remove_circle")
ui.kpi(k[2], "Nuevas", ui.fnum(n_new, 0), icon="add_circle")
ui.kpi(k[3], "Trasladadas", ui.fnum(n_mov, 0), icon="open_with")
ui.kpi(k[4], "Corregidas", ui.fnum(n_mod, 0), icon="edit")

with st.expander("Vista previa del plano", expanded=bool(ops)):
    prev = quedan[quedan["destino"].notna()].copy()
    if not prev.empty:
        prev = pd.DataFrame({
            "zona": prev["Zona"], "zona_orden": prev["Zona"].map(lambda z: META[z]["orden"]),
            "bloque": prev["Bloque"].astype(int), "columna": prev["Columna"].astype(str),
            "col_pos": [META[z]["columnas"].index(str(cc)) for z, cc in zip(prev["Zona"], prev["Columna"])],
            "nivel": prev["Nivel"].astype(int) - 1, "celda": prev["destino"], "texto": prev["texto"],
            "qq": prev["QQ"].astype(float), "estiba": prev["Estiba"].astype(str),
            "color": prev["Tipo"].map(COLOR_TIPO), "condicion": prev["Tipo"], "color_texto": None})
    tabs = st.tabs(list(META))
    for tab, (zn, m) in zip(tabs, META.items()):
        with tab:
            ez = prev[prev["zona"] == zn] if not prev.empty else prev
            ui.show(plano.figura(ez, m, compacto=False), key=f"rc_plano_{m['orden']}")

if errores:
    st.error("Corrige antes de guardar:\n\n" + "\n".join(f"- {e}" for e in dict.fromkeys(errores)))
puede = not errores and (bool(ops) or not existe)
if st.button(f"💾 Guardar en Excel ({'actualizar' if existe else 'crear'} pestaña «{hoja}»)", type="primary",
             disabled=not puede, key="rc_guardar"):
    with st.spinner("Escribiendo en el Excel…"):
        try:
            res = E.guardar_conteo(ruta, hoja_base, hoja, ops, os.path.join(c["app_dir"], "respaldos"),
                                   colores=COLOR_TIPO)
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo guardar: {e}")
            st.stop()
    st.cache_data.clear()
    st.session_state.pop("rc_clave", None)
    st.session_state["rc_ok"] = res
    st.rerun()

if "rc_ok" in st.session_state:
    res = st.session_state.pop("rc_ok")
    st.success(f"Listo: pestaña «{res['hoja']}» {'creada' if res['creada'] else 'actualizada'} "
               f"({res['escritas']} celdas escritas, {res['borradas']} borradas). Respaldo: "
               f"{os.path.basename(res['respaldo'])}. Para verlo en la web usa «🌐 Actualizar la app web» en la "
               "barra lateral.")
    if res["libro_abierto"]:
        st.info("El libro estaba abierto en tu Excel: los cambios se guardaron en esa ventana.")
    if res["sin_color"]:
        st.warning("No se encontró el color de la leyenda para: " + ", ".join(res["sin_color"]))
