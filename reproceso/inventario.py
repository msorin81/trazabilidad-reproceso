"""Inventario físico de reproceso: libros «AAAA-Inventario_Fisico_Reproceso.xlsx» (formato F-RPR-266).

Cada pestaña con nombre de fecha (AAAA-MM-DD) es un plano de la bodega:
  · zonas (Carpa Encerrada Reproceso, Carpa bodega PT, Patio…) con bloques numerados 1, 2, 3… en una
    columna (cada bloque ocupa varias filas de Excel) y columnas de posiciones a la derecha;
  · cada celda «qq-estiba» (p. ej. 40-320 = 40 quintales de la estiba 320) es una estiba;
  · el color de relleno de la celda indica el tipo de producto según la leyenda de la hoja.

El lector no depende de direcciones fijas: detecta los bloques, las zonas, la leyenda y los colores
en cada pestaña, así que sirve para todas las fechas y para el libro de cada año.
"""
from __future__ import annotations

import colorsys
import glob
import os
import re
import shutil
import tempfile
import zipfile
import time as _time
_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia (Streamlit Cloud)

import pandas as pd

from . import data as D

FILE_PATTERN = "20[0-9][0-9]-Inventario_Fisico_Reproceso.xlsx"
CELDA = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*-\s*['´`]?\s*([0-9A-Za-z][^\s]*)\s*$")
FECHA_HOJA = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")
SIN_COLOR, OTRO_COLOR = "Sin color", "Otro color"

# Paleta estándar de colores «indexed» de Excel (0–63)
_INDEXED = ["000000", "FFFFFF", "FF0000", "00FF00", "0000FF", "FFFF00", "FF00FF", "00FFFF",
            "000000", "FFFFFF", "FF0000", "00FF00", "0000FF", "FFFF00", "FF00FF", "00FFFF",
            "800000", "008000", "000080", "808000", "800080", "008080", "C0C0C0", "808080",
            "9999FF", "993366", "FFFFCC", "CCFFFF", "660066", "FF8080", "0066CC", "CCCCFF",
            "000080", "FF00FF", "FFFF00", "00FFFF", "800080", "800000", "008080", "0000FF",
            "00CCFF", "CCFFFF", "CCFFCC", "FFFF99", "99CCFF", "FF99CC", "CC99FF", "FFCC99",
            "3366FF", "33CCCC", "99CC00", "FFCC00", "FF9900", "FF6600", "666699", "969696",
            "003366", "339966", "003300", "333300", "993300", "993366", "333399", "333333"]


# ---------------------------------------------------------------------------
# Archivos
# ---------------------------------------------------------------------------
def list_files(data_dir: str) -> list[str]:
    files = sorted(glob.glob(os.path.join(data_dir, FILE_PATTERN)))
    return [f for f in files if not os.path.basename(f).startswith("~$")]


def files_signature(data_dir: str) -> tuple:
    return tuple((os.path.basename(f), os.path.getsize(f), int(os.path.getmtime(f))) for f in list_files(data_dir))


def _abrir(path: str) -> zipfile.ZipFile:
    """Abre el libro; si Excel/OneDrive lo tiene bloqueado, lee una copia temporal."""
    return D.abrir_libro(path)


# ---------------------------------------------------------------------------
# Colores (estilos + tema del libro)
# ---------------------------------------------------------------------------
def _tint(hex6: str, tint: float) -> str:
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    r, g, b = colorsys.hls_to_rgb(h, max(0, min(1, l)), s)
    return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _theme_colors(z) -> list[str]:
    try:
        xml = z.read("xl/theme/theme1.xml").decode("utf8")
    except KeyError:
        return []
    cs = re.search(r"<a:clrScheme.*?</a:clrScheme>", xml, re.S)
    if not cs:
        return []
    found = dict(re.findall(r"<a:(dk1|lt1|dk2|lt2|accent\d|hlink|folHlink)>.*?(?:val|lastClr)=\"([0-9A-Fa-f]{6})\"",
                            cs.group(), re.S))
    # orden de índices de Excel: 0=lt1, 1=dk1, 2=lt2, 3=dk2, 4..9=accent1..6, 10=hlink, 11=folHlink
    order = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
             "hlink", "folHlink"]
    return [found.get(k, "000000").upper() for k in order]


def _color(el, theme: list[str]) -> tuple[tuple | None, str | None]:
    """Elemento <fgColor>/<color> → (clave estable, hex RRGGBB)."""
    if el is None:
        return None, None
    tint = float(el.get("tint", 0) or 0)
    if el.get("rgb"):
        h = el.get("rgb")[-6:].upper()
        return ("rgb", h), _tint(h, tint) if tint else h
    if el.get("theme") is not None:
        i = int(el.get("theme"))
        base = theme[i] if i < len(theme) else "000000"
        return ("theme", i, round(tint, 2)), _tint(base, tint) if tint else base
    if el.get("indexed") is not None:
        i = int(el.get("indexed"))
        if i >= len(_INDEXED):  # 64 = color automático
            return None, None
        return ("rgb", _INDEXED[i]), _INDEXED[i]
    return None, None


def _styles(z, theme: list[str]) -> list[dict]:
    """Por cada estilo de celda (cellXfs): color de relleno y color de letra."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(z.read("xl/styles.xml"))
    M = D._M
    fills = []
    for f in root.find(M + "fills"):
        pf = f.find(M + "patternFill")
        if pf is None or pf.get("patternType") in (None, "none"):
            fills.append((None, None))
        else:
            fills.append(_color(pf.find(M + "fgColor"), theme))
    fonts = [_color(f.find(M + "color"), theme) for f in root.find(M + "fonts")]
    out = []
    for xf in root.find(M + "cellXfs"):
        fi, fo = int(xf.get("fillId", 0)), int(xf.get("fontId", 0))
        out.append({"fill": fills[fi] if fi < len(fills) else (None, None),
                    "font": fonts[fo] if fo < len(fonts) else (None, None)})
    return out


# ---------------------------------------------------------------------------
# Lectura de una pestaña
# ---------------------------------------------------------------------------
def _celdas(z, sheet_path: str, sst: list[str]) -> dict:
    """{(fila, col): (valor, estilo, formula)} de toda la hoja."""
    import xml.etree.ElementTree as ET
    M = D._M
    out = {}
    with z.open(sheet_path) as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag == M + "row":
                el.clear()
                continue
            if el.tag != M + "c":
                continue
            m = re.match(r"([A-Z]+)(\d+)", el.get("r", ""))
            if not m:
                continue
            t, v, f = el.get("t"), el.find(M + "v"), el.find(M + "f")
            val = None
            if t == "s" and v is not None:
                val = sst[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in el.iter(M + "t"))
            elif v is not None and v.text is not None:
                if t in ("str", "e"):
                    val = v.text if t == "str" else None
                else:
                    try:
                        val = float(v.text)
                    except ValueError:
                        val = v.text
            out[(int(m.group(2)), D._col_idx(m.group(1)))] = (
                val, int(el.get("s", 0)), f.text if f is not None and f.text else None)
    return out


def _secuencias(cells: dict) -> list[tuple[int, list[int]]]:
    """Columnas con números de bloque 1, 2, 3… espaciados ≥3 filas → [(col, [filas…])]."""
    por_col = {}
    for (r, c), (v, _, f) in cells.items():
        if f is None and isinstance(v, float) and v.is_integer() and 1 <= v <= 99:
            por_col.setdefault(c, []).append((r, int(v)))
    seqs = []
    for c, items in por_col.items():
        items.sort()
        cur = []
        for r, v in items:
            if v == 1:
                if len(cur) >= 2:
                    seqs.append((c, [x[0] for x in cur]))
                cur = [(r, v)]
            elif cur and v == cur[-1][1] + 1 and r - cur[-1][0] >= 3:
                cur.append((r, v))
            elif cur and v == cur[-1][1] + 1:
                cur = []  # filas consecutivas: es una tabla de conteo, no un plano
        if len(cur) >= 2:
            seqs.append((c, [x[0] for x in cur]))
    return seqs


def _rangos_conteo(cells: dict) -> list[tuple[int, int, int, int]]:
    out = []
    for (_, _), (_, _, f) in cells.items():
        if f and "_Suma_QQ" in f:
            for a, b in re.findall(r"([A-Z]+\d+):([A-Z]+\d+)", f):
                out.append(D._parse_ref(f"{a}:{b}"))
    return out


def _titulo_zona(cells: dict, fila: int) -> str:
    cand = []
    for (r, c), (v, _, _) in cells.items():
        if isinstance(v, str) and fila - 5 <= r < fila and re.search(r"carpa|patio|bodega|zona", v, re.I):
            cand.append((fila - r, c, v))
    if not cand:
        return f"Zona (fila {fila})"
    cand.sort()
    return re.sub(r"(?i)^\s*conteo\s+", "", cand[0][2]).strip()


def leer_hoja(cells: dict, estilos: list[dict], fecha: pd.Timestamp) -> tuple[pd.DataFrame, list[dict], dict]:
    """Devuelve (estibas, leyenda, resumen) de una pestaña."""
    def est(s):
        return estilos[s] if s < len(estilos) else {"fill": (None, None), "font": (None, None)}

    # --- leyenda: texto con una celda vacía coloreada a su izquierda
    leyenda = []
    for (r, c), (v, s, _) in cells.items():
        if not isinstance(v, str) or not v.strip() or CELDA.match(v) or c < 2:
            continue
        izq = cells.get((r, c - 1))
        if izq is not None and izq[0] in (None, "") and est(izq[1])["fill"][0] is not None:
            key, hx = est(izq[1])["fill"]
            leyenda.append({"orden": r, "condicion": v.strip().rstrip(".").strip(), "clave": key, "color": hx})
    # «sin desición» → ortografía original se respeta; solo se ordena por fila
    leyenda.sort(key=lambda x: x["orden"])

    def condicion(key, hx):
        if key is None:
            return SIN_COLOR
        for l in leyenda:
            if l["clave"] == key:
                return l["condicion"]
        if key[0] == "theme":
            mismos = [l for l in leyenda if l["clave"] and l["clave"][0] == "theme" and l["clave"][1] == key[1]]
            if len(mismos) == 1:
                return mismos[0]["condicion"]
        if hx:
            def dist(a, b):
                return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (0, 2, 4)) ** .5
            cerca = sorted((dist(hx, l["color"]), l["condicion"]) for l in leyenda if l["color"])
            if cerca and cerca[0][0] < 40:
                return cerca[0][1]
        return OTRO_COLOR

    # --- zonas a partir de los números de bloque
    conteo = _rangos_conteo(cells)
    zonas = []
    for col, filas in _secuencias(cells):
        paso = min(b - a for a, b in zip(filas, filas[1:]))
        r_ini, r_fin = filas[0], filas[-1] + paso - 1
        # columnas de posiciones: las que usan las fórmulas de conteo dentro de la zona;
        # si no hay, encabezado numérico encima del bloque 1; si no, hasta 8 columnas a la derecha
        usadas = set()
        for (ra, ca, rb, cb) in conteo:
            if r_ini <= ra <= r_fin and col < ca <= col + 12:
                usadas.update(range(ca, min(cb, col + 12) + 1))
        cols = sorted(usadas)
        hdr = {c: cells.get((r_ini - 1, c), (None,))[0] for c in range(col + 1, col + 13)}
        hdr_num = {c: int(v) for c, v in hdr.items() if isinstance(v, float) and v.is_integer()}
        if not cols:
            cols = sorted(hdr_num) or list(range(col + 1, col + 9))
        etiquetas = {c: hdr_num.get(c, i + 1) for i, c in enumerate(cols)}
        zonas.append({"zona": _titulo_zona(cells, r_ini), "col_bloque": col, "filas": filas, "paso": paso,
                      "r_ini": r_ini, "r_fin": r_fin, "cols": cols, "etiquetas": etiquetas,
                      "orden": len(zonas)})

    def ubicar(r, c):
        for z in zonas:
            if z["r_ini"] <= r <= z["r_fin"] and z["cols"][0] <= c <= z["cols"][-1]:
                b = max(i for i, fr in enumerate(z["filas"]) if fr <= r)
                return z, b + 1, r - z["filas"][b]
        return None, None, None

    filas_out, raros = [], []
    for (r, c), (v, s, f) in cells.items():
        if not isinstance(v, str) or FECHA_HOJA.match(v):
            continue
        m = CELDA.match(v)
        z, bloque, nivel = ubicar(r, c)
        if not m:
            if z is not None and v.strip():
                raros.append(f"{_ref(r, c)}: «{v.strip()}»")
            continue
        fill_key, fill_hex = est(s)["fill"]
        font_key, font_hex = est(s)["font"]
        filas_out.append({
            "fecha": fecha, "zona": z["zona"] if z else "Sin ubicar", "zona_orden": z["orden"] if z else 99,
            "bloque": bloque, "columna": z["etiquetas"].get(c) if z else None,
            "col_pos": z["cols"].index(c) if z and c in z["cols"] else None, "nivel": nivel,
            "celda": _ref(r, c), "texto": v.strip(),
            "qq": float(m.group(1).replace(",", ".")), "estiba": m.group(2).strip("'´`").lstrip("0") or "0",
            "color": fill_hex, "condicion": condicion(fill_key, fill_hex),
            "color_texto": font_hex if font_hex and _luz(font_hex) > 0.25 else None,  # negro/casi negro = normal
        })
    df = pd.DataFrame(filas_out)
    # total que muestra la hoja («TOTAL GENERAL») para validar la lectura
    total_hoja = None
    for (r, c), (v, _, _) in cells.items():
        if isinstance(v, str) and v.strip().upper() == "TOTAL GENERAL":
            for dc in range(1, 5):
                w = cells.get((r, c + dc))
                if w and isinstance(w[0], float):
                    total_hoja = w[0]
                    break
    resumen = {"fecha": fecha, "total_hoja": total_hoja, "celdas_no_reconocidas": raros,
               "zonas": [{"zona": z["zona"], "orden": z["orden"], "bloques": len(z["filas"]), "niveles": z["paso"],
                          "columnas": [z["etiquetas"][c] for c in z["cols"]],
                          # direcciones en Excel (para escribir un conteo desde la app)
                          "filas_excel": z["filas"], "cols_excel": z["cols"]} for z in zonas]}
    return df, leyenda, resumen


def _luz(hex6: str) -> float:
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


NOMBRE_TEXTO = {"E46C0A": "naranja", "FFFF00": "amarillo", "FF0000": "rojo", "FFFFFF": "blanco"}


def nombre_color_texto(hx) -> str | None:
    if not isinstance(hx, str):
        return None
    return NOMBRE_TEXTO.get(hx, f"#{hx}")


def _ref(r, c) -> str:
    s = ""
    while c:
        c, rem = divmod(c - 1, 26)
        s = chr(65 + rem) + s
    return f"{s}{r}"


# ---------------------------------------------------------------------------
# Libro completo
# ---------------------------------------------------------------------------
def read_workbook(path: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    import xml.etree.ElementTree as ET
    archivo = os.path.basename(path)
    estibas, leyendas, zonas, avisos = [], [], [], []
    with _abrir(path) as z:
        sst = D._shared_strings(z)
        theme = _theme_colors(z)
        estilos = _styles(z, theme)
        wb_rels = D._rels(z, "xl/_rels/workbook.xml.rels")
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        for sh in wb.find("m:sheets", D._NS).findall("m:sheet", D._NS):
            nombre = sh.get("name") or ""
            m = FECHA_HOJA.match(nombre)
            if not m or sh.get("state") in ("hidden", "veryHidden"):
                continue
            fecha = pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            path_h = D._resolve("xl", wb_rels[sh.get("{%s}id" % D._NS["r"])])
            try:
                df, ley, res = leer_hoja(_celdas(z, path_h, sst), estilos, fecha)
            except Exception as e:  # noqa: BLE001
                avisos.append(f"{archivo} · pestaña {nombre}: no se pudo leer ({e})")
                continue
            if not df.empty:
                df["archivo"] = archivo
                estibas.append(df)
            for l in ley:
                leyendas.append({"fecha": fecha, "condicion": l["condicion"], "color": l["color"], "orden": l["orden"]})
            for zz in res["zonas"]:
                zonas.append({"fecha": fecha, "archivo": archivo, "hoja": nombre,
                              **{k: (",".join(str(x) for x in v) if isinstance(v, list) else v)
                                 for k, v in zz.items()}})
            if res["celdas_no_reconocidas"]:
                avisos.append(f"{archivo} · {nombre}: celdas que no tienen la forma «qq-estiba»: "
                              + "; ".join(res["celdas_no_reconocidas"][:8]))
            tot = df["qq"].sum() if not df.empty else 0.0
            if res["total_hoja"] is not None and abs(res["total_hoja"] - tot) > 0.05:
                avisos.append(f"{archivo} · {nombre}: la app suma {tot:,.1f} qq y la hoja muestra "
                              f"TOTAL GENERAL {res['total_hoja']:,.1f} qq (revisar celdas fuera de las zonas "
                              f"o fórmulas de conteo).")
    cat = lambda fr: pd.concat(fr, ignore_index=True) if fr else pd.DataFrame()  # noqa: E731
    return cat(estibas), pd.DataFrame(leyendas), pd.DataFrame(zonas), avisos


def load(data_dir: str) -> dict:
    est, ley, zon, avisos = [], [], [], []
    for path in list_files(data_dir):
        try:
            a, b, c, d = read_workbook(path)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"No se pudo leer {os.path.basename(path)}: {e}")
            continue
        est.append(a); ley.append(b); zon.append(c); avisos += d
    cat = lambda fr: pd.concat([f for f in fr if not f.empty], ignore_index=True) if any(not f.empty for f in fr) \
        else pd.DataFrame()  # noqa: E731
    return {"inv": cat(est), "inv_leyenda": cat(ley), "inv_zonas": cat(zon), "inv_avisos": avisos,
            "inv_archivos": [os.path.basename(f) for f in list_files(data_dir)]}
