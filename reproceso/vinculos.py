"""Pestaña «Trazabilidad tiquetes» de los libros AAAA-Stock-Reproceso.xlsm.

Cada fila tiene la fecha (desde 2025), el tiquete (o varios: «41921-41922-41923») y un vínculo al
PDF con la trazabilidad completa. Los vínculos pueden ser:
  · web (SharePoint/OneDrive) → se pueden abrir desde la app;
  · ruta local (file:///C:\\usuario\\...) → solo existen en el equipo de quien los creó; se guarda
    únicamente el nombre del archivo (no la ruta, que incluye el usuario de esa persona).
"""
from __future__ import annotations

import os
import re
import zipfile
from urllib.parse import unquote
import time as _time
_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia (Streamlit Cloud)

import pandas as pd

from . import data as D

HOJA = "trazabilidad tiquetes"
COLS = {"fecha": "fecha", "tiquete": "tiquete_txt", "trazabilidad": "traz",
        "trazabilidad sap - bodega": "sap", "observacion": "obs"}


def _hyperlinks(z, sheet_path: str) -> dict:
    """{(fila, col): destino} de los hipervínculos de la hoja."""
    import xml.etree.ElementTree as ET
    sdir, sname = os.path.split(sheet_path)
    rels = D._rels(z, f"{sdir}/_rels/{sname}.rels")
    out = {}
    with z.open(sheet_path) as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag == D._M + "row":
                el.clear()
            elif el.tag == D._M + "hyperlink":
                ref = el.get("ref", "")
                tgt = rels.get(el.get("{%s}id" % D._NS["r"])) or (("#" + el.get("location")) if el.get("location") else None)
                if not tgt:
                    continue
                # un mismo vínculo puede aplicarse a un rango (p. ej. C131:C132): vale para todas sus celdas
                if ":" in ref:
                    r1, c1, r2, c2 = D._parse_ref(ref)
                else:
                    m = re.match(r"([A-Z]+)(\d+)", ref)
                    if not m:
                        continue
                    r1 = r2 = int(m.group(2)); c1 = c2 = D._col_idx(m.group(1))
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        out.setdefault((r, c), tgt)
    return out


def _tiquetes(v) -> list[str]:
    """«41921-41922-41923» → ['41921', '41922', '41923']; 35778.0 → ['35778']."""
    if D._is_missing(v):
        return []
    if isinstance(v, float) and v.is_integer():
        return [str(int(v))]
    return re.findall(r"\d{3,}", str(v)) or [str(v).strip()]


def _clasificar(link: str | None) -> tuple[str | None, str | None, str | None]:
    """(tipo, url_abrible, nombre_archivo)."""
    if not isinstance(link, str) or not link:
        return None, None, None
    if re.match(r"https?://", link, re.I):
        return "web", link, None
    nombre = os.path.basename(unquote(link).replace("\\", "/")) or None
    return "archivo local", None, nombre


def read_workbook(path: str) -> pd.DataFrame:
    import xml.etree.ElementTree as ET
    archivo = os.path.basename(path)
    anio = int(archivo[:4])
    with D.abrir_libro(path) as z:
        sst = D._shared_strings(z)
        wb_rels = D._rels(z, "xl/_rels/workbook.xml.rels")
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet_path = None
        for sh in wb.find("m:sheets", D._NS).findall("m:sheet", D._NS):
            if (sh.get("name") or "").strip().lower() == HOJA:
                sheet_path = D._resolve("xl", wb_rels[sh.get("{%s}id" % D._NS["r"])])
        if not sheet_path:
            return pd.DataFrame()
        sdir, sname = os.path.split(sheet_path)
        rng = None
        for target in D._rels(z, f"{sdir}/_rels/{sname}.rels").values():
            if "tables/" not in target:
                continue
            t = ET.fromstring(z.read(D._resolve(sdir, target)))
            names = [D._norm_key(c.get("name")) for c in t.iter(D._M + "tableColumn")]
            if "tiquete" in names:
                rng = D._parse_ref(t.get("ref"))
        if rng is None:
            return pd.DataFrame()
        cells = D._read_cells(z, sheet_path, [rng], sst)
        links = _hyperlinks(z, sheet_path)
    r1, c1, r2, c2 = rng
    hdr = {c: COLS.get(D._norm_key(cells.get((r1, c))) if cells.get((r1, c)) else "") for c in range(c1, c2 + 1)}
    filas = []
    for r in range(r1 + 1, r2 + 1):
        reg = {"anio": anio, "archivo": archivo, "fila": r}
        for c, k in hdr.items():
            if not k:
                continue
            reg[k] = cells.get((r, c))
            if k in ("traz", "sap", "obs"):
                reg[f"{k}_link"] = links.get((r, c))
        if any(reg.get(k) is not None for k in ("tiquete_txt", "traz", "traz_link")):
            filas.append(reg)
    return pd.DataFrame(filas)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    cols = ["anio", "fecha", "tiquete", "tiquete_txt", "n_tiquetes", "pdf_tipo", "pdf_url", "pdf_nombre",
            "sap_tipo", "sap_url", "sap_nombre", "observacion", "archivo", "fila"]
    if raw.empty:
        return pd.DataFrame(columns=cols)
    df = raw.copy()
    for k in ("fecha", "tiquete_txt", "traz", "sap", "obs", "traz_link", "sap_link", "obs_link"):
        if k not in df.columns:
            df[k] = None
    df["fecha"] = pd.to_datetime(df["fecha"].map(D._to_date), errors="coerce")
    for k, pref in (("traz_link", "pdf"), ("sap_link", "sap")):
        cl = df[k].map(_clasificar)
        df[f"{pref}_tipo"] = cl.map(lambda x: x[0])
        df[f"{pref}_url"] = cl.map(lambda x: x[1])
        df[f"{pref}_nombre"] = cl.map(lambda x: x[2])
    df["observacion"] = df["obs"].map(D._clean_text)
    df["lista"] = df["tiquete_txt"].map(_tiquetes)
    df["n_tiquetes"] = df["lista"].map(len)
    df["tiquete_txt"] = df["tiquete_txt"].map(lambda v: None if D._is_missing(v) else
                                              (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip()))
    df = df.explode("lista").rename(columns={"lista": "tiquete"})
    df = df[df["tiquete"].notna()]
    return df[cols].reset_index(drop=True)


def load(data_dir: str) -> tuple[pd.DataFrame, list[str]]:
    frames, avisos = [], []
    for path in D.list_files(data_dir):
        try:
            frames.append(read_workbook(path))
        except Exception as e:  # noqa: BLE001
            avisos.append(f"Trazabilidad tiquetes · no se pudo leer {os.path.basename(path)}: {e}")
    frames = [f for f in frames if not f.empty]
    return clean(pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), avisos
