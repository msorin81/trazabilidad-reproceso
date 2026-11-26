# Trazabilidad del PPR de reproceso · Ingenio Sancarlos

Aplicación Streamlit para el control y la visualización del azúcar en reproceso (no conforme,
avería, barredura y rechazado): ingreso, stock de fin de mes, disolución, reproceso diario,
conciliación físico vs tiquete de báscula, indicadores del modelo Power BI y control de calidad
de los registros.

## Cómo funciona

| Dónde se abre | De dónde lee los datos | Qué tan actualizados están |
|---|---|---|
| **Local** (`run_app.bat`, en el equipo con OneDrive) | Directamente los libros `AAAA-Stock-Reproceso.xlsm` (hojas 1–12) | Siempre al día (botón «Recargar datos») |
| **Web** (enlace de Streamlit Cloud) | La instantánea `data/*.parquet` publicada en GitHub | Hasta la última vez que se ejecutó `actualizar_datos.bat` |

La fecha de **última actualización** aparece debajo del encabezado de cada página.
La versión web **no publica nombres de personas** (responsable de laboratorio, de elaboración y
quién autoriza); la versión local sí los muestra.

## Proceso de actualización (rutina)

1. Diligenciar como siempre la hoja del mes en el libro `AAAA-Stock-Reproceso.xlsm` y **guardar**.
2. En la app local, barra lateral → **«🌐 Actualizar la app web» → Publicar ahora**
   (o doble clic en **`actualizar_datos.bat`**). El proceso:
   - lee los seis libros (≈ 4 s),
   - guarda la instantánea en `data/` con la fecha de actualización,
   - hace *commit* y *push* a GitHub.
3. Streamlit Cloud detecta el cambio y la app web se actualiza sola en 1–2 minutos.
   Los usuarios solo tienen que recargar la página.

### Actualización automática diaria

Una tarea programada de Windows («Reproceso - actualizar app web») ejecuta
`actualizar_datos.py --auto` con tu usuario (sin ventana):

- **cada 2 horas entre las 7:00 a. m. y las 7:00 p. m.** y siempre a las **6:00 p. m.**;
- **cada vez que inicias sesión** en Windows (un minuto después, para que OneDrive y la red estén listos);
- si el equipo estaba apagado o **suspendido** a la hora programada, apenas vuelva a estar disponible.

Solo publica si los Excel cambiaron (si no, termina en segundos). Si algún libro no se puede leer, no
publica nada. El resultado de cada ejecución, con la hora de cada paso, queda en `logs/actualizacion_auto.log`.

- Cambiar la hora: `powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1 -Hora 07:30`
- Quitar la tarea: `powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1 -Quitar`
- Ejecutarla ya: Programador de tareas → «Reproceso - actualizar app web» → Ejecutar.

Año nuevo: basta con dejar el libro `2027-Stock-Reproceso.xlsm` en la misma carpeta, con las hojas
`1`…`12` y sus tablas `Tabla_trazabilidad_…` y `Tabla_tiquetes_…`. No hay que tocar el código.

## Publicación inicial (una sola vez)

1. **Instalar Git for Windows**: <https://git-scm.com/download/win> (opciones por defecto).
2. **Crear el repositorio** en <https://github.com/new>: nombre `trazabilidad-reproceso`,
   **Public**, sin README ni .gitignore (vacío).
3. Doble clic en **`publicar_primera_vez.bat`** (la primera vez Git abre el navegador para iniciar
   sesión en GitHub).
4. Entrar a <https://share.streamlit.io> con la cuenta de GitHub → **Create app** →
   repositorio `msorin81/trazabilidad-reproceso`, rama `main`, archivo `app.py` → **Deploy**.
   En *Advanced settings* elegir Python 3.12.
5. Copiar el enlace (p. ej. `https://trazabilidad-reproceso.streamlit.app`) y compartirlo.

> Nota: en el plan gratuito, la app se «duerme» si nadie la abre en varios días; el primer usuario
> que entre verá un botón para despertarla (tarda menos de un minuto).

## Estructura

```
app.py                 navegación, filtros globales, origen de datos
reproceso/data.py      lectura de los .xlsm, limpieza, reglas de negocio y medidas Power BI
reproceso/ui.py        gráficos, formatos, tarjetas e íconos
reproceso/brand.py     identidad corporativa, tamaño de letra, fecha de actualización
views/                 una página por archivo
data/                  instantánea publicada (la genera actualizar_datos.bat)
```

## Módulos de bodega y soporte (PPR · ISO 22002-1)

- **Inventario físico** (menú *Bodega*): lee `AAAA-Inventario_Fisico_Reproceso.xlsx` (formato F-RPR-266) de
  la misma carpeta que los libros de stock. Cada pestaña con nombre de fecha `AAAA-MM-DD` es un conteo; la
  app toma por defecto la más reciente. Cada celda `qq-estiba` (p. ej. `40-320`) es una estiba; el color de
  relleno es el tipo de producto según la leyenda de la hoja. El lector detecta solo las zonas (números de
  bloque 1, 2, 3… en una columna), por eso sirve para todas las fechas y para el libro de cada año nuevo.
  Incluye plano interactivo, evolución diaria y conciliación con el stock «Cuantificado» de la trazabilidad.
- **Registrar conteo** (solo app local, opcional): el Excel sigue siendo el registro principal. Esta página
  parte del último conteo, permite retirar / agregar / trasladar estibas (con sugerencias de las que la
  trazabilidad ya reporta como disueltas o mezcladas) y escribe la pestaña del día **en el mismo libro**
  usando Excel (conserva formato, leyenda y fórmulas). Antes de guardar deja una copia en `respaldos/`.
  Si el libro está abierto en tu Excel, escribe en esa ventana.
- **Trazabilidad por tiquete** (menú *Control*): lee la pestaña «Trazabilidad tiquetes» de cada libro de
  stock (2022 en adelante) y cruza cada tiquete con la báscula y las estibas disueltas. Los vínculos web
  (SharePoint) se abren desde la app; los que apuntan a una ruta local (`file:///C:\…`) solo muestran el
  nombre del PDF (no se publica la ruta).

## Reglas de negocio (iguales al reporte Power BI)

- **Stock de fin de mes** = registros con Estado «Cuantificado» en la hoja del mes.
- **Disolución** = Estado «Disuelto» o «Mezclado».
- **Ingreso del mes** = registros cuya fecha de ingreso cae en el año-mes de la hoja.
- **Días en stock** = fecha de reproceso (o fin de mes / hoy) − fecha de ingreso.
