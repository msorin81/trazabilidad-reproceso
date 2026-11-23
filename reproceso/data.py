"""Carga y limpieza de los libros «AAAA-Stock-Reproceso.xlsm».

Cada libro tiene hojas «1» … «12» (una por mes). En cada hoja hay dos tablas de Excel:

* ``Tabla_trazabilidad_*``: foto del PPR de reproceso al cierre del mes. Las estibas que
  siguen en stock («Cuantificado») se arrastran de un mes al siguiente, y las que se
  disolvieron en el mes aparecen con Estado «Disuelto»/«Mezclado».
* ``Tabla_tiquetes_*``: tiquetes de báscula de lo disuelto en el mes.

El mes se toma del nombre de la hoja (no del nombre de la tabla, que en 2021 está
desfasado un mes) y el año del nombre del archivo.
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import unicodedata
import warnings
import time as _time
_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia (Streamlit Cloud)

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
TRAZ_COLS = {
    "# estiba": "estiba",
    "quintales": "qq",
    "estado": "estado",
    "categoria": "categoria",
    "codigo de producto": "codigo",
    "fecha de produccion": "fecha_produccion_txt",
    "fecha de ingreso": "fecha_ingreso",
    "rango marcacion": "rango_marcacion",
    "causa de ingreso": "causa_original",
    "fecha de pesaje (liberacion)": "fecha_pesaje",
    "medida de control": "medida_control",
    "clasificacion": "clasificacion",
    "punto de disolucion": "punto_disolucion",
    "tiquete pesaje": "tiquete",
    "fecha de reproceso": "fecha_reproceso",
    "responsable de laboratorio": "resp_laboratorio",
    "etapa o equipo": "equipo",
    "responsable de la adicion por elaboracion": "resp_elaboracion",
    "autoriza": "autoriza",
    "tiempo de retencion (dias)": "dias_retencion_excel",
    "cantidad de sacos resultante": "sacos",
    "observaciones": "observaciones",
    "tipo de azucar": "tipo_azucar",
    "presentacion kg": "presentacion_kg",
}

TIQ_COLS = {
    "fecha": "fecha",
    "tiquete": "tiquete",
    "peso real tinas": "peso_tinas",
    "peso real-averias": "peso_averias",
    "quintales enteros (no conforme)": "qq_enteros",
    "quintales totales (tiquete)": "qq_tiquete",
    "quintales fisico": "qq_fisico",
    "diferencia": "diferencia_excel",
}

# Etiquetas para mostrar en pantalla / exportar
LABELS = {
    "periodo": "Mes (hoja)",
    "anio": "Año",
    "mes": "Mes",
    "estiba": "# Estiba",
    "qq": "Quintales",
    "estado": "Estado",
    "categoria": "Categoría",
    "codigo": "Código de producto",
    "fecha_produccion": "Fecha de producción",
    "fecha_produccion_txt": "Fecha de producción (original)",
    "fecha_ingreso": "Fecha de ingreso",
    "rango_marcacion": "Rango marcación",
    "causa": "Causa de ingreso",
    "causa_original": "Causa de ingreso (original)",
    "fecha_pesaje": "Fecha de pesaje (liberación)",
    "medida_control": "Medida de control",
    "clasificacion": "Clasificación",
    "punto_disolucion": "Punto de disolución",
    "tiquete": "Tiquete pesaje",
    "fecha_reproceso": "Fecha de reproceso",
    "resp_laboratorio": "Responsable laboratorio",
    "equipo": "Etapa o equipo",
    "resp_elaboracion": "Responsable elaboración",
    "autoriza": "Autoriza",
    "dias_retencion_excel": "Retención Excel (días)",
    "dias_en_stock": "Días en stock",
    "sacos": "Sacos resultantes",
    "observaciones": "Observaciones",
    "tipo_azucar": "Tipo de azúcar",
    "presentacion_kg": "Presentación (kg)",
    "es_ingreso_mes": "Ingresó en el mes",
    "archivo": "Archivo",
    "hoja": "Hoja",
    "fecha": "Fecha",
    "peso_tinas": "Peso real tinas (kg)",
    "peso_averias": "Peso real averías (kg)",
    "qq_enteros": "QQ enteros (no conforme)",
    "qq_tiquete": "QQ tiquete",
    "qq_fisico": "QQ físico",
    "diferencia": "Diferencia (tiquete − físico)",
}

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES_LARGO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
               "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Lógica tomada del reporte Power BI (filtros por defecto de cada página)
ESTADOS_STOCK = ["Cuantificado"]
ESTADOS_DISOLUCION = ["Disuelto", "Mezclado"]

FILE_PATTERN = "20[0-9][0-9]-Stock-Reproceso.xlsm"


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------
def _norm_key(s: str) -> str:
    """minúsculas, sin tildes, espacios colapsados (para comparar textos)."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s.replace("\n", " ")).strip().lower()
    return s


def _is_missing(v) -> bool:
    try:
        return v is None or bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _clean_text(v):
    if _is_missing(v):
        return None
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


def _canonical(series: pd.Series) -> pd.Series:
    """Agrupa variantes de escritura (mayúsculas/tildes/espacios) y usa la más frecuente."""
    s = series.map(_clean_text)
    keys = s.map(lambda x: _norm_key(x) if x else None)
    counts = pd.DataFrame({"k": keys, "v": s}).dropna().value_counts().reset_index()
    best = counts.sort_values("count", ascending=False).drop_duplicates("k").set_index("k")["v"]
    out = keys.map(best)
    # primera letra en mayúscula para homogeneizar
    return out.map(lambda x: x[0].upper() + x[1:] if isinstance(x, str) and x else x)


def _to_date(v):
    if _is_missing(v):
        return pd.NaT
    if isinstance(v, dt.datetime):
        return pd.Timestamp(v.date())
    if isinstance(v, dt.date):
        return pd.Timestamp(v)
    if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
        # número serial de Excel
        if 20000 < v < 80000:
            return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(v))
        return pd.NaT
    if isinstance(v, str):
        ts = pd.to_datetime(v.strip(), dayfirst=True, errors="coerce")
        # textos con hora y zona horaria («2020-12-22 20:21-06»): solo interesa la fecha; una sola fecha con
        # zona horaria hacía que pandas descartara toda la columna al mezclarla con las demás
        return pd.Timestamp(ts.date()) if isinstance(ts, pd.Timestamp) and not pd.isna(ts) else pd.NaT
    return pd.NaT


def _to_num(v):
    if _is_missing(v) or isinstance(v, (dt.date, dt.datetime)):
        return np.nan
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return np.nan


def _tiquete_key(v):
    """Normaliza el número de tiquete para cruzar trazabilidad ↔ báscula."""
    s = _clean_text(v)
    if not s:
        return None
    digits = re.sub(r"\.0$", "", s)
    return digits if digits.isdigit() else s


# ---------------------------------------------------------------------------
# Lectura de libros
# ---------------------------------------------------------------------------
def list_files(data_dir: str) -> list[str]:
    files = sorted(glob.glob(os.path.join(data_dir, FILE_PATTERN)))
    return [f for f in files if not os.path.basename(f).startswith("~$")]


def files_signature(data_dir: str) -> tuple:
    """Firma (nombre, tamaño, fecha) para invalidar la caché cuando cambie un archivo."""
    return tuple((os.path.basename(f), os.path.getsize(f), int(os.path.getmtime(f)))
                 for f in list_files(data_dir))


# Lector directo del XML del libro: openpyxl tarda ~1 min por archivo con estos libros
# (mucho formato); aquí solo se leen las celdas de las tablas que interesan.
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
_M = "{%s}" % _NS["m"]


def _col_idx(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def _parse_ref(ref: str) -> tuple[int, int, int, int]:
    a, b = ref.split(":")
    ma, mb = re.match(r"([A-Z]+)(\d+)", a), re.match(r"([A-Z]+)(\d+)", b)
    return int(ma.group(2)), _col_idx(ma.group(1)), int(mb.group(2)), _col_idx(mb.group(1))


def _resolve(base_dir: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return os.path.normpath(os.path.join(base_dir, target)).replace("\\", "/")


def _rels(z, path: str) -> dict:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(z.read(path))
    except KeyError:
        return {}
    return {r.get("Id"): r.get("Target") for r in root.findall("pr:Relationship", _NS)}


def _shared_strings(z) -> list[str]:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(_M + "t")) for si in root.findall("m:si", _NS)]


def _read_cells(z, sheet_path: str, ranges: list[tuple[int, int, int, int]], sst: list[str]) -> dict:
    import xml.etree.ElementTree as ET
    rmin = min(r[0] for r in ranges); rmax = max(r[2] for r in ranges)
    cmin = min(r[1] for r in ranges); cmax = max(r[3] for r in ranges)
    cells = {}
    with z.open(sheet_path) as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag == _M + "row":
                el.clear()
                continue
            if el.tag != _M + "c":
                continue
            m = re.match(r"([A-Z]+)(\d+)", el.get("r", ""))
            if not m:
                continue
            row, col = int(m.group(2)), _col_idx(m.group(1))
            if rmin <= row <= rmax and cmin <= col <= cmax:
                t = el.get("t")
                v = el.find(_M + "v")
                val = None
                if t == "s" and v is not None:
                    val = sst[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in el.iter(_M + "t"))
                elif t in ("str",) and v is not None:
                    val = v.text
                elif t == "b" and v is not None:
                    val = v.text == "1"
                elif t == "e":
                    val = None
                elif v is not None and v.text is not None:
                    try:
                        val = float(v.text)
                    except ValueError:
                        val = v.text
                if val is not None and val != "":
                    cells[(row, col)] = val
    return cells


def _table_frame(cells: dict, rng: tuple, mapping: dict) -> pd.DataFrame:
    r1, c1, r2, c2 = rng
    hdr = [mapping.get(_norm_key(cells.get((r1, c))), None) if cells.get((r1, c)) else None
           for c in range(c1, c2 + 1)]
    data = [[cells.get((r, c)) for c in range(c1, c2 + 1)] for r in range(r1 + 1, r2 + 1)]
    data = [row for row in data if any(v is not None for v in row)]
    df = pd.DataFrame(data, columns=[h or f"_x{i}" for i, h in enumerate(hdr)], dtype=object)
    return df[[c for c in df.columns if not c.startswith("_x")]]


def read_workbook(path: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    import xml.etree.ElementTree as ET
    import zipfile

    anio = int(os.path.basename(path)[:4])
    archivo = os.path.basename(path)
    trazs, tiqs, avisos = [], [], []
    with zipfile.ZipFile(path) as z:
        sst = _shared_strings(z)
        wb_rels = _rels(z, "xl/_rels/workbook.xml.rels")
        wb_xml = ET.fromstring(z.read("xl/workbook.xml"))
        for sh in wb_xml.find("m:sheets", _NS).findall("m:sheet", _NS):
            title = (sh.get("name") or "").strip()
            if not title.isdigit() or not 1 <= int(title) <= 12:
                continue
            mes = int(title)
            sheet_path = _resolve("xl", wb_rels[sh.get("{%s}id" % _NS["r"])])
            sdir, sname = os.path.split(sheet_path)
            tables = []
            for target in _rels(z, f"{sdir}/_rels/{sname}.rels").values():
                if "tables/" not in target:
                    continue
                t = ET.fromstring(z.read(_resolve(sdir, target)))
                name = t.get("displayName") or t.get("name") or ""
                low = name.lower()
                if low.startswith("tabla_trazabilidad"):
                    tables.append(("traz", name, _parse_ref(t.get("ref"))))
                elif low.startswith("tabla_tiquetes"):
                    tables.append(("tiq", name, _parse_ref(t.get("ref"))))
            kinds = {k for k, _, _ in tables}
            for k in ("traz", "tiq"):
                if k not in kinds:
                    avisos.append(f"{archivo} hoja {title}: no se encontró la tabla de "
                                  f"{'trazabilidad' if k == 'traz' else 'tiquetes'}")
            if not tables:
                continue
            cells = _read_cells(z, sheet_path, [r for _, _, r in tables], sst)
            for k, name, rng in tables:
                df = _table_frame(cells, rng, TRAZ_COLS if k == "traz" else TIQ_COLS)
                df["anio"], df["mes"] = anio, mes
                df["archivo"], df["hoja"], df["tabla"] = archivo, title, name
                (trazs if k == "traz" else tiqs).append(df)
    return _concat(trazs), _concat(tiqs), avisos


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f.astype(object) for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------
def clean_trazabilidad(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    for c in TRAZ_COLS.values():
        if c not in df.columns:
            df[c] = None

    df["qq"] = df["qq"].map(_to_num)
    df["estado"] = _canonical(df["estado"])
    # filas vacías de la tabla de Excel (sin estado ni quintales) se descartan
    df = df[~(df["estado"].isna() & df["qq"].isna())].copy()

    df["periodo"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
    for c in ["fecha_ingreso", "fecha_pesaje", "fecha_reproceso"]:
        df[c] = df[c].map(_to_date)
    df["fecha_produccion"] = df["fecha_produccion_txt"].map(_to_date)
    df["fecha_produccion_txt"] = [
        f.strftime("%Y-%m-%d") if not pd.isna(f) else _clean_text(v)
        for f, v in zip(df["fecha_produccion"], df["fecha_produccion_txt"])
    ]
    df["fecha_produccion"] = pd.to_datetime(df["fecha_produccion"], errors="coerce")

    for c in ["estiba", "codigo", "rango_marcacion", "observaciones", "resp_laboratorio",
              "resp_elaboracion", "autoriza", "medida_control", "clasificacion",
              "punto_disolucion", "equipo", "sacos"]:
        df[c] = df[c].map(_clean_text)
    for c in ["categoria", "medida_control", "clasificacion",
              "punto_disolucion", "equipo", "tipo_azucar"]:
        df[c] = _canonical(df[c])
    df["causa"] = _canonical(df["causa_original"])
    df["causa_original"] = df["causa_original"].map(_clean_text)
    df["tipo_azucar"] = df["tipo_azucar"].replace({"N.A": "N.A.", "N.a": "N.A."})
    df["presentacion_kg"] = df["presentacion_kg"].map(_clean_text)
    df["tiquete"] = df["tiquete"].map(_tiquete_key)
    df["dias_retencion_excel"] = df["dias_retencion_excel"].map(_to_num)

    for c in ["categoria", "estado", "causa", "tipo_azucar", "presentacion_kg", "codigo"]:
        df[c] = df[c].fillna("(Sin dato)")

    # Ingreso del mes: la fecha de ingreso cae en el mismo año-mes de la hoja
    df["es_ingreso_mes"] = df["fecha_ingreso"].dt.to_period("M") == df["periodo"].dt.to_period("M")

    # Días en stock calculados (independiente de la fórmula de Excel)
    fin_mes = df["periodo"] + pd.offsets.MonthEnd(0)
    hoy = pd.Timestamp(dt.date.today())
    corte = fin_mes.where(fin_mes < hoy, hoy)
    salida = df["fecha_reproceso"].where(df["estado"].isin(ESTADOS_DISOLUCION))
    df["dias_en_stock"] = ((salida.fillna(corte)) - df["fecha_ingreso"]).dt.days

    cols = ["periodo", "anio", "mes"] + [c for c in LABELS if c in df.columns and c not in
                                         ("periodo", "anio", "mes")] + ["tabla"]
    return df[list(dict.fromkeys(cols))].reset_index(drop=True)


def clean_tiquetes(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    for c in TIQ_COLS.values():
        if c not in df.columns:
            df[c] = None
    for c in ["peso_tinas", "peso_averias", "qq_enteros", "qq_tiquete", "qq_fisico", "diferencia_excel"]:
        df[c] = df[c].map(_to_num)
    df["fecha"] = df["fecha"].map(_to_date)
    df["tiquete"] = df["tiquete"].map(_tiquete_key)
    df = df[~(df["tiquete"].isna() & df["qq_tiquete"].isna() & df["qq_fisico"].isna())].copy()
    df["periodo"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
    df["diferencia"] = df["qq_tiquete"].fillna(0) - df["qq_fisico"].fillna(0)
    cols = ["periodo", "anio", "mes", "fecha", "tiquete", "peso_tinas", "peso_averias",
            "qq_enteros", "qq_tiquete", "qq_fisico", "diferencia", "archivo", "hoja", "tabla"]
    return df[cols].reset_index(drop=True)


def load_all(data_dir: str, cache_dir: str | None = None) -> dict:
    """Lee todos los libros. Usa una caché parquet por archivo (se invalida con la fecha
    de modificación) para que recargar sea rápido."""
    trazs, tiqs, avisos = [], [], []
    for path in list_files(data_dir):
        stamp = f"{os.path.basename(path)}_{os.path.getsize(path)}_{int(os.path.getmtime(path))}"
        cached = None
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            p_tr = os.path.join(cache_dir, stamp + "_traz.pkl")
            p_tq = os.path.join(cache_dir, stamp + "_tiq.pkl")
            if os.path.exists(p_tr) and os.path.exists(p_tq):
                try:
                    cached = (pd.read_pickle(p_tr), pd.read_pickle(p_tq), [])
                except Exception:
                    cached = None
        if cached is None:
            try:
                cached = read_workbook(path)
            except Exception as e:  # archivo abierto/bloqueado o dañado
                avisos.append(f"No se pudo leer {os.path.basename(path)}: {e}")
                continue
            if cache_dir:
                base = os.path.basename(path)
                for old in glob.glob(os.path.join(cache_dir, base + "_*")):
                    try:
                        os.remove(old)
                    except OSError:
                        pass
                cached[0].to_pickle(p_tr)
                cached[1].to_pickle(p_tq)
        trazs.append(cached[0]); tiqs.append(cached[1]); avisos += cached[2]

    extra = ["anio", "mes", "archivo", "hoja", "tabla"]
    traz_raw = _concat(trazs)
    if traz_raw.empty:
        traz_raw = pd.DataFrame(columns=list(TRAZ_COLS.values()) + extra)
    tiq_raw = _concat(tiqs)
    if tiq_raw.empty:
        tiq_raw = pd.DataFrame(columns=list(TIQ_COLS.values()) + extra)
    traz_raw[["anio", "mes"]] = traz_raw[["anio", "mes"]].astype(int)
    tiq_raw[["anio", "mes"]] = tiq_raw[["anio", "mes"]].astype(int)
    return {
        "traz": clean_trazabilidad(traz_raw),
        "tiq": clean_tiquetes(tiq_raw),
        "avisos": avisos,
        "cargado": dt.datetime.now(),
    }


# ---------------------------------------------------------------------------
# Instantánea (snapshot) para publicar la app en la nube sin los .xlsm
# ---------------------------------------------------------------------------
SNAP_TRAZ, SNAP_TIQ, SNAP_META = "trazabilidad.parquet", "tiquetes.parquet", "metadata.json"
# Módulos adicionales: vínculos a PDF por tiquete e inventario físico (opcionales en la instantánea)
SNAP_EXTRA = {"vinculos": "vinculos_tiquetes.parquet", "inv": "inventario_fisico.parquet",
              "inv_leyenda": "inventario_leyenda.parquet", "inv_zonas": "inventario_zonas.parquet"}


def load_extras(data_dir: str) -> dict:
    """Vínculos «Trazabilidad tiquetes» (libros Stock) + inventario físico (libros Inventario_Fisico)."""
    from . import inventario as I
    from . import vinculos as V
    vinc, av = V.load(data_dir)
    out = I.load(data_dir)
    out["vinculos"] = vinc
    out["extra_avisos"] = av + out.pop("inv_avisos", [])
    return out


def extras_signature(data_dir: str) -> tuple:
    from . import inventario as I
    return files_signature(data_dir) + I.files_signature(data_dir)
# Nombres de personas: no se publican en la versión web (repositorio público)
PERSONAL_COLS = ["resp_laboratorio", "resp_elaboracion", "autoriza"]


def files_info(data_dir: str) -> list[dict]:
    from . import inventario as I
    return [{"archivo": os.path.basename(f),
             "modificado": dt.datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="minutes")}
            for f in list_files(data_dir) + I.list_files(data_dir)]


def ultimo_movimiento(traz: pd.DataFrame, tiq: pd.DataFrame):
    fechas = [traz["fecha_ingreso"].max(), traz["fecha_reproceso"].max(), tiq["fecha"].max()]
    hoy = pd.Timestamp(dt.date.today())
    fechas = [f for f in fechas if pd.notna(f) and f <= hoy]
    return max(fechas) if fechas else None


def _huella(*frames: pd.DataFrame) -> str:
    """Huella (hash) del contenido de los datos, para saber si cambiaron desde la última publicación."""
    import hashlib
    h = hashlib.sha256()
    for f in frames:
        h.update(pd.util.hash_pandas_object(f.astype(str), index=False).values.tobytes())
    return h.hexdigest()


def export_snapshot(datos: dict, data_dir: str, out_dir: str, solo_si_cambia: bool = False) -> dict | None:
    """Guarda los datos limpios en parquet + metadata.json (fecha de actualización).
    Con solo_si_cambia=True devuelve None (y no escribe nada) si los datos son iguales a los publicados."""
    import json
    os.makedirs(out_dir, exist_ok=True)
    traz = datos["traz"].copy()
    traz[PERSONAL_COLS] = None
    extras = {k: datos[k] for k in SNAP_EXTRA if isinstance(datos.get(k), pd.DataFrame)}
    huella = _huella(traz, datos["tiq"], *extras.values())
    meta_path = os.path.join(out_dir, SNAP_META)
    if solo_si_cambia and os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as fh:
                if json.load(fh).get("huella") == huella:
                    return None
        except (OSError, ValueError):
            pass
    traz.to_parquet(os.path.join(out_dir, SNAP_TRAZ), index=False)
    datos["tiq"].to_parquet(os.path.join(out_dir, SNAP_TIQ), index=False)
    for k, df in extras.items():
        df.to_parquet(os.path.join(out_dir, SNAP_EXTRA[k]), index=False)
    um = ultimo_movimiento(datos["traz"], datos["tiq"])
    meta = {
        "publicado": dt.datetime.now().isoformat(timespec="minutes"),
        "archivos": files_info(data_dir),
        "ultimo_movimiento": um.strftime("%Y-%m-%d") if um is not None else None,
        "registros_trazabilidad": int(len(datos["traz"])),
        "registros_tiquetes": int(len(datos["tiq"])),
        "avisos": datos.get("avisos", []) + datos.get("extra_avisos", []),
        "inventario_ultima_fecha": (datos["inv"]["fecha"].max().strftime("%Y-%m-%d")
                                    if isinstance(datos.get("inv"), pd.DataFrame) and not datos["inv"].empty else None),
        "huella": huella,
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return meta


def snapshot_exists(snap_dir: str) -> bool:
    return all(os.path.exists(os.path.join(snap_dir, f)) for f in (SNAP_TRAZ, SNAP_TIQ, SNAP_META))


def snapshot_signature(snap_dir: str) -> tuple:
    return tuple((f, int(os.path.getmtime(os.path.join(snap_dir, f))))
                 for f in (SNAP_TRAZ, SNAP_TIQ, SNAP_META, *SNAP_EXTRA.values())
                 if os.path.exists(os.path.join(snap_dir, f)))


def load_snapshot(snap_dir: str) -> dict:
    import json
    with open(os.path.join(snap_dir, SNAP_META), encoding="utf-8") as fh:
        meta = json.load(fh)
    out = {
        "traz": pd.read_parquet(os.path.join(snap_dir, SNAP_TRAZ)),
        "tiq": pd.read_parquet(os.path.join(snap_dir, SNAP_TIQ)),
        "avisos": meta.get("avisos", []),
        "cargado": dt.datetime.now(),
        "meta": meta,
    }
    for k, fname in SNAP_EXTRA.items():
        p = os.path.join(snap_dir, fname)
        out[k] = pd.read_parquet(p) if os.path.exists(p) else pd.DataFrame()
    return out


def info_actualizacion(datos: dict, data_dir: str | None) -> dict:
    """Fecha de última actualización: última modificación de los Excel (o de la publicación)."""
    meta = datos.get("meta")
    if meta:
        archivos = meta.get("archivos", [])
        publicado = pd.Timestamp(meta["publicado"])
    else:
        archivos = files_info(data_dir) if data_dir else []
        publicado = None
    mod = max((pd.Timestamp(a["modificado"]) for a in archivos), default=None)
    ult = max(archivos, key=lambda a: a["modificado"])["archivo"] if archivos else None
    return {"excel_modificado": mod, "archivo": ult, "publicado": publicado,
            "ultimo_movimiento": ultimo_movimiento(datos["traz"], datos["tiq"])}


# ---------------------------------------------------------------------------
# Métricas (equivalentes a las medidas DAX del reporte)
# ---------------------------------------------------------------------------
def ingreso(df: pd.DataFrame) -> pd.DataFrame:
    """Sum Quintales_Ingreso: quintales cuya fecha de ingreso cae en el mes de la hoja."""
    return df[df["es_ingreso_mes"]]


def stock(df: pd.DataFrame, estados=None) -> pd.DataFrame:
    """Sum Quintales_Mes con Estado = Cuantificado: stock al cierre de cada mes."""
    return df[df["estado"].isin(estados or ESTADOS_STOCK)]


def disolucion(df: pd.DataFrame, estados=None) -> pd.DataFrame:
    """Sum Quintales_Mes con Estado = Disuelto/Mezclado: lo reprocesado en cada mes."""
    return df[df["estado"].isin(estados or ESTADOS_DISOLUCION)]


def reproceso_diario(df: pd.DataFrame, estados=None) -> pd.DataFrame:
    d = disolucion(df, estados).dropna(subset=["fecha_reproceso"])
    return (d.groupby("fecha_reproceso", as_index=False)
             .agg(qq=("qq", "sum"), estibas=("estiba", "count"))
             .rename(columns={"fecha_reproceso": "fecha"}))


def mensual(df: pd.DataFrame, value="qq", by: str | None = None) -> pd.DataFrame:
    keys = ["periodo"] + ([by] if by else [])
    return df.groupby(keys, as_index=False)[value].sum()


def medidas_pbi(df: pd.DataFrame) -> pd.DataFrame:
    """Medidas de la tabla «Medidas» del modelo Power BI, calculadas por mes (hoja).

    - Sum Quintales_Ingreso, QQ Ingreso Mes Anterior, Var MoM, Var YoY, QQ Ingreso YTD
    - Sum Quintales_Repro_día (disuelto) y QQ Disueltos YTD
    - Sum Quintales_Mes (total de la hoja), QQ Stock (Cuantificado), % Disolución, % Stock Pendiente
    - Índice Rotación Mensual = disuelto / total de la hoja
    - Promedio Móvil 3M Ingreso (promedio simple de los 3 últimos meses)
    - Promedio/Máx retención (días) y Estibas > 30 / > 60 días (sobre el stock)
    """
    if df.empty:
        return pd.DataFrame()
    per = pd.date_range(df["periodo"].min(), df["periodo"].max(), freq="MS")
    ing = ingreso(df).groupby("periodo")["qq"].sum().reindex(per, fill_value=0)
    dis = disolucion(df).groupby("periodo")["qq"].sum().reindex(per, fill_value=0)
    tot = df.groupby("periodo")["qq"].sum().reindex(per, fill_value=0)
    stk_df = stock(df)
    stk = stk_df.groupby("periodo")["qq"].sum().reindex(per, fill_value=0)
    out = pd.DataFrame(index=per)
    out["Ingreso (qq)"] = ing
    out["Ingreso mes anterior (qq)"] = ing.shift(1)
    out["Var. MoM ingreso"] = (ing - ing.shift(1)) / ing.shift(1).replace(0, np.nan)
    prev_year = ing.copy()
    prev_year.index = prev_year.index + pd.DateOffset(years=1)
    py = prev_year.reindex(per)
    out["Ingreso mismo mes año anterior (qq)"] = py
    out["Var. YoY ingreso"] = (ing - py) / py.replace(0, np.nan)
    out["Ingreso acumulado año (qq)"] = ing.groupby(ing.index.year).cumsum()
    out["Prom. móvil 3M ingreso (qq)"] = ing.rolling(3, min_periods=1).mean()
    out["Disuelto (qq)"] = dis
    out["Disuelto acumulado año (qq)"] = dis.groupby(dis.index.year).cumsum()
    out["Total hoja (qq)"] = tot
    out["Stock fin de mes (qq)"] = stk
    out["% Disolución"] = dis / tot.replace(0, np.nan)
    out["% Stock pendiente"] = stk / tot.replace(0, np.nan)
    out["Índice rotación (disuelto/total)"] = out["% Disolución"]
    g = stk_df.groupby("periodo")
    out["Prom. días en stock"] = g["dias_en_stock"].mean().reindex(per)
    out["Máx. días en stock"] = g["dias_en_stock"].max().reindex(per)
    out["Estibas > 30 días"] = stk_df[stk_df["dias_en_stock"] > 30].groupby("periodo")["estiba"].nunique().reindex(per, fill_value=0)
    out["Estibas > 60 días"] = stk_df[stk_df["dias_en_stock"] > 60].groupby("periodo")["estiba"].nunique().reindex(per, fill_value=0)
    out["Causas distintas (ingreso)"] = ingreso(df).groupby("periodo")["causa"].nunique().reindex(per, fill_value=0)
    out = out[out.index.isin(df["periodo"].unique())]
    out.index.name = "periodo"
    return out


def periodo_label(p) -> str:
    p = pd.Timestamp(p)
    return f"{MESES[p.month - 1]} {p.year}"
