"""Escribe un conteo de inventario físico en el libro oficial F-RPR-266 usando el propio Excel (COM).

Se usa Excel y no openpyxl porque el libro tiene logo, formas, fórmulas LAMBDA (_Suma_QQ) y matrices
dinámicas (BYROW/BYCOL) que una librería de Python no conserva. Solo funciona en Windows con Excel
instalado (app local); la versión web no escribe nada.

Antes de cualquier cambio se guarda una copia de respaldo del libro en app_reproceso/respaldos/.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import time as _time
_CARGADO = _time.time()  # ver app.py: recarga del módulo si el archivo cambia

XL_NONE, XL_AUTO, XL_WHOLE, XL_VALUES = -4142, -4105, 1, -4163


def disponible() -> bool:
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def _hex_a_bgr(hx: str) -> int:
    hx = hx.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return r + (g << 8) + (b << 16)


def _libro(path: str):
    """Devuelve (excel, libro, lo_abri_yo). Si el libro ya está abierto en Excel, usa esa ventana."""
    import win32com.client
    nombre = os.path.basename(path).lower()
    ruta = os.path.normcase(os.path.abspath(path))
    try:
        xl = win32com.client.GetActiveObject("Excel.Application")
        for wb in xl.Workbooks:
            full = str(wb.FullName)
            # misma ruta; o abierto desde OneDrive (la ruta aparece como https://…) con el mismo nombre
            if os.path.normcase(full) == ruta or (full.lower().startswith("http") and wb.Name.lower() == nombre
                                                   and "onedrive" in ruta):
                return xl, wb, False
    except Exception:  # noqa: BLE001 - Excel no está abierto
        pass
    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(os.path.abspath(path), UpdateLinks=0)
    return xl, wb, True


def _leyenda(ws) -> dict:
    """{texto de la leyenda: celda muestra de color} buscando en las celdas usadas de la hoja."""
    out = {}
    ur = ws.UsedRange
    vals = ur.Value
    if not isinstance(vals, tuple):
        return out
    r0, c0 = ur.Row, ur.Column
    for i, fila in enumerate(vals):
        for j, v in enumerate(fila):
            if isinstance(v, str) and v.strip() and j > 0:
                izq = fila[j - 1]
                if izq in (None, ""):
                    cel = ws.Cells(r0 + i, c0 + j - 1)
                    if cel.Interior.Pattern != XL_NONE:
                        out.setdefault(v.strip().rstrip(".").strip(), cel)
    return out


def guardar_conteo(path: str, hoja_base: str, hoja_nueva: str, ops: list[dict], respaldo_dir: str,
                   colores: dict[str, str] | None = None) -> dict:
    """ops: [{"accion": "borrar", "celda": "B15"},
             {"accion": "escribir", "celda": "C20", "texto": "40-320", "condicion": "No Conforme",
              "formato_de": "B15" | None}]   (formato_de = mover conservando colores de la celda de origen)
    colores: {condición: hex} de respaldo por si la leyenda no se encuentra en la hoja."""
    import pythoncom
    pythoncom.CoInitialize()
    os.makedirs(respaldo_dir, exist_ok=True)
    respaldo = os.path.join(respaldo_dir, f"{dt.datetime.now():%Y%m%d_%H%M%S}_{os.path.basename(path)}")
    shutil.copy2(path, respaldo)
    xl = wb = None
    propio = False
    try:
        xl, wb, propio = _libro(path)
        if wb.ReadOnly:
            raise RuntimeError("El libro está abierto solo lectura (¿lo tiene abierto otra persona?). "
                               "Ciérralo o espera y vuelve a intentar.")
        nombres = [s.Name for s in wb.Worksheets]
        if hoja_base not in nombres:
            raise RuntimeError(f"No existe la pestaña base «{hoja_base}».")
        base = wb.Worksheets(hoja_base)
        if hoja_nueva == hoja_base:
            ws, creada = base, False
        else:
            if hoja_nueva in nombres:
                raise RuntimeError(f"Ya existe la pestaña «{hoja_nueva}».")
            base.Copy(None, base)  # Copy(Before, After): copia completa, con formato, fórmulas y dibujos
            ws = wb.Worksheets(base.Index + 1)
            ws.Name = hoja_nueva
            creada = True

        ley = _leyenda(ws)
        # 1) leer el formato de las celdas de origen de los traslados ANTES de borrar
        fmt = {}
        for op in ops:
            src = op.get("formato_de")
            if op["accion"] == "escribir" and src and src not in fmt:
                c = ws.Range(src)
                fmt[src] = (c.Interior.Pattern, c.Interior.Color, c.Font.Color)
        # 2) borrar
        borradas = 0
        for op in ops:
            if op["accion"] == "borrar":
                c = ws.Range(op["celda"])
                c.ClearContents()
                c.Interior.Pattern = XL_NONE
                c.Font.ColorIndex = XL_AUTO
                borradas += 1
        # 3) escribir
        escritas, sin_color = 0, []
        for op in ops:
            if op["accion"] != "escribir":
                continue
            c = ws.Range(op["celda"])
            c.NumberFormat = "@"  # texto: evita que Excel convierta «3-12» en fecha
            c.Value = op["texto"]
            src = op.get("formato_de")
            if src and src in fmt and fmt[src][0] != XL_NONE:
                c.Interior.Color = fmt[src][1]
                c.Font.Color = fmt[src][2]
            else:
                cond = (op.get("condicion") or "").strip()
                muestra = ley.get(cond)
                if muestra is not None:
                    c.Interior.Color = muestra.Interior.Color
                elif colores and colores.get(cond):
                    c.Interior.Color = _hex_a_bgr(colores[cond])
                else:
                    sin_color.append(op["celda"])
                c.Font.ColorIndex = XL_AUTO
            escritas += 1
        ws.Calculate()
        wb.Save()
        return {"hoja": hoja_nueva, "creada": creada, "borradas": borradas, "escritas": escritas,
                "sin_color": sin_color, "respaldo": respaldo, "libro_abierto": not propio}
    finally:
        if propio and wb is not None:
            try:
                wb.Close(False)
            except Exception:  # noqa: BLE001
                pass
        if propio and xl is not None:
            try:
                xl.Quit()
            except Exception:  # noqa: BLE001
                pass
        pythoncom.CoUninitialize()
