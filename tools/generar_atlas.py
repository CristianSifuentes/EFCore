#!/usr/bin/env python3
"""Genera el catálogo A–Z, la tabla periódica, la espiral y el banner de EF Core Atlas.

Fuente única de verdad: data/caracteristicas.csv
Salidas:
  - docs/22-catalogo-a-z.md
  - assets/efcore-atlas-tabla-periodica.svg
  - assets/efcore-atlas-espiral.svg
  - assets/efcore-atlas-banner.svg

Uso:  python3 tools/generar_atlas.py   (solo biblioteca estándar, Python 3.9+)
"""
from __future__ import annotations

import csv
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "data" / "caracteristicas.csv"
CATALOGO = RAIZ / "docs" / "22-catalogo-a-z.md"
POSTER = RAIZ / "assets" / "efcore-atlas-tabla-periodica.svg"
ESPIRAL = RAIZ / "assets" / "efcore-atlas-espiral.svg"
BANNER = RAIZ / "assets" / "efcore-atlas-banner.svg"

EDICION = "noviembre 2026"
FECHA_CORTE = "8 de noviembre de 2026"
FUENTE = "Segoe UI, Inter, Helvetica Neue, Arial, sans-serif"

FAMILIAS = [
    ("modelado", "Modelado", "#A78BFA"),
    ("consultas", "Consultas LINQ", "#38BDF8"),
    ("guardado", "Guardado y concurrencia", "#F472B6"),
    ("migraciones", "Migraciones y esquema", "#FB923C"),
    ("rendimiento", "Rendimiento y AOT", "#F87171"),
    ("json", "JSON y documentos", "#FACC15"),
    ("proveedores", "Proveedores", "#2DD4BF"),
    ("diagnostico", "Diagnóstico y resiliencia", "#CBD5E1"),
    ("herramientas", "Herramientas y CLI", "#60A5FA"),
    ("ia", "Búsqueda e IA", "#34D399"),
]
NOMBRE_FAMILIA = {k: n for k, n, _ in FAMILIAS}
COLOR_FAMILIA = {k: c for k, _, c in FAMILIAS}

# Versión -> (año, capítulo)
VERSIONES = {
    "1.0": ("2016", "03-ef-core-1-2-cimientos.md"),
    "1.1": ("2016", "03-ef-core-1-2-cimientos.md"),
    "2.0": ("2017", "03-ef-core-1-2-cimientos.md"),
    "2.1": ("2018", "03-ef-core-1-2-cimientos.md"),
    "2.2": ("2018", "03-ef-core-1-2-cimientos.md"),
    "3.0": ("2019", "04-ef-core-3-la-gran-ruptura.md"),
    "3.1": ("2019", "04-ef-core-3-la-gran-ruptura.md"),
    "5.0": ("2020", "05-ef-core-5-relaciones-y-diagnostico.md"),
    "6.0": ("2021", "06-ef-core-6-rendimiento-y-temporalidad.md"),
    "7.0": ("2022", "07-ef-core-7-json-y-operaciones-masivas.md"),
    "8.0": ("2023", "08-ef-core-8-tipos-complejos.md"),
    "9.0": ("2024", "09-ef-core-9-cosmos-aot-y-siembra.md"),
    "10": ("2025", "10-ef-core-10-lts-vectores-y-json.md"),
    "11": ("2026", "11-ef-core-11-rc.md"),
}
# Columnas del póster: las versiones menores se agrupan con su versión mayor.
COLUMNAS = [
    ("1", ["1.0", "1.1"], "2016"), ("2", ["2.0", "2.1", "2.2"], "2017–18"), ("3", ["3.0", "3.1"], "2019"),
    ("5", ["5.0"], "2020"), ("6", ["6.0"], "2021"), ("7", ["7.0"], "2022"), ("8", ["8.0"], "2023"),
    ("9", ["9.0"], "2024"), ("10", ["10"], "2025"), ("11", ["11"], "2026"),
]
AMBITO = {"N": "Núcleo", "R": "Relacional", "S": "SQL Server", "L": "SQLite", "C": "Cosmos DB", "T": "Herramientas"}
ESTADO = {"GA": "🟢", "RC": "🟡 RC"}


def clave_orden(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


def leer() -> list[dict]:
    with CSV.open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    errores = []
    for i, r in enumerate(filas, start=2):
        if None in r or any(v is None for v in r.values()):
            errores.append(f"línea {i}: número de columnas incorrecto")
        elif r["familia"] not in NOMBRE_FAMILIA or r["version"] not in VERSIONES or r["ambito"] not in AMBITO \
                or r["estado"] not in ESTADO:
            errores.append(f"línea {i}: valor desconocido en {r['nombre']!r}")
    repetidos = [k for k, n in Counter(r["simbolo"] for r in filas).items() if n > 1]
    if repetidos:
        errores.append(f"símbolos repetidos: {repetidos}")
    if errores:
        raise SystemExit("Errores en el CSV:\n  " + "\n  ".join(errores))
    return filas


def celda(texto: str) -> str:
    return texto.replace("|", "\\|")


# --------------------------------------------------------------------------- catálogo
def generar_catalogo(filas: list[dict]) -> str:
    total = len(filas)
    lineas = [
        '<div align="center">', "",
        "# 22 · Catálogo A–Z de características de EF Core", "",
        f"**{total} características con su versión, familia, ámbito y capítulo · edición {EDICION}**", "",
        "[⬅ 21 · Guías de decisión](21-guias-de-decision.md) · [🏠 Índice](../README.md) · "
        "[23 · Migración entre versiones ➡](23-migracion-entre-versiones.md)", "",
        "</div>", "",
        "> [!NOTE]",
        "> Este archivo se **genera automáticamente** desde [`data/caracteristicas.csv`](../data/caracteristicas.csv) con",
        "> `python3 tools/generar_atlas.py`. Para corregir o añadir una característica, edita el CSV y ejecuta el script.", "",
        '<a href="../assets/efcore-atlas-tabla-periodica.svg"><img src="../assets/efcore-atlas-tabla-periodica.svg" '
        'alt="Tabla periódica de características de EF Core" width="100%"></a>', "",
        "## Resumen por versión", "",
        "| Versión | Año | Características | " + " | ".join(AMBITO.values()) + " |",
        "|---|---|---:|" + "---:|" * len(AMBITO),
    ]
    por_version: dict[str, Counter] = defaultdict(Counter)
    for r in filas:
        por_version[r["version"]][r["ambito"]] += 1
    for v, (anio, capitulo) in VERSIONES.items():
        c = por_version[v]
        lineas.append(f"| [EF Core {v}]({capitulo}) | {anio} | {sum(c.values())} | "
                      + " | ".join(str(c[k]) for k in AMBITO) + " |")
    c = Counter(r["ambito"] for r in filas)
    lineas += ["| **Total** | | **" + str(total) + "** | " + " | ".join(f"**{c[k]}**" for k in AMBITO) + " |", "",
               "## Resumen por familia", "", "| Familia | Características | Primera | Última |", "|---|---:|---|---|"]
    orden_v = list(VERSIONES)
    for k, n, _ in FAMILIAS:
        vs = sorted((r["version"] for r in filas if r["familia"] == k), key=orden_v.index)
        lineas.append(f"| {n} | {len(vs)} | {vs[0]} | {vs[-1]} |")
    lineas += ["",
               "**Leyenda.** Estado: 🟢 estable · 🟡 RC *release candidate* (EF Core 11, a la espera de su lanzamiento). "
               "Ámbito: **Núcleo** funciona con cualquier proveedor · **Relacional** exige un proveedor relacional · "
               "**SQL Server**, **SQLite** y **Cosmos DB** son específicas de ese proveedor · **Herramientas** pertenece a `dotnet ef` o MSBuild.", "",
               "## Catálogo", ""]
    letra = ""
    for r in sorted(filas, key=lambda x: clave_orden(x["nombre"])):
        inicial = clave_orden(r["nombre"])[0].upper()
        if inicial != letra:
            letra = inicial
            lineas += ["", f"### {letra}", "", "| Característica | EF Core | Familia | Ámbito | Estado | Descripción |",
                       "|---|---|---|---|---|---|"]
        cap = VERSIONES[r["version"]][1]
        lineas.append(f"| {celda(r['nombre'])} | [{r['version']}]({cap}) | {NOMBRE_FAMILIA[r['familia']]} | "
                      f"{AMBITO[r['ambito']]} | {ESTADO[r['estado']]} | {celda(r['descripcion'])} |")
    return "\n".join(lineas) + "\n"


# --------------------------------------------------------------------------- póster
TILE, GAP, MARGEN, CABECERA = 118, 10, 48, 214

FONDO = ('<linearGradient id="fondo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#030B14"/>'
         '<stop offset="0.55" stop-color="#071C2C"/><stop offset="1" stop-color="#0C2E44"/></linearGradient>'
         '<radialGradient id="halo" cx="0.85" cy="0.1" r="0.7"><stop offset="0" stop-color="#2DD4BF" stop-opacity="0.22"/>'
         '<stop offset="1" stop-color="#2DD4BF" stop-opacity="0"/></radialGradient>'
         '<radialGradient id="halo2" cx="0.1" cy="0.95" r="0.6"><stop offset="0" stop-color="#A78BFA" stop-opacity="0.18"/>'
         '<stop offset="1" stop-color="#A78BFA" stop-opacity="0"/></radialGradient>'
         '<pattern id="rejilla" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" '
         'stroke="#FFFFFF" stroke-opacity="0.035"/></pattern>'
         '<linearGradient id="trazo" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2DD4BF"/>'
         '<stop offset="0.5" stop-color="#38BDF8"/><stop offset="1" stop-color="#A78BFA"/></linearGradient>')


def fondo(ancho: int, alto: int) -> str:
    return (f'<rect width="{ancho}" height="{alto}" fill="url(#fondo)"/><rect width="{ancho}" height="{alto}" fill="url(#rejilla)"/>'
            f'<rect width="{ancho}" height="{alto}" fill="url(#halo)"/><rect width="{ancho}" height="{alto}" fill="url(#halo2)"/>')


def tile(r: dict, x: int, y: int) -> list[str]:
    color = COLOR_FAMILIA[r["familia"]]
    borde = 'stroke-dasharray="7 5"' if r["estado"] != "GA" else ""
    partes = [
        f'<g transform="translate({x},{y})">',
        f'<rect width="{TILE}" height="{TILE}" rx="12" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.6" {borde}/>',
        f'<rect x="1" y="1" width="{TILE - 2}" height="26" rx="11" fill="{color}" fill-opacity="0.10"/>',
        f'<text x="10" y="18" font-size="11" fill="#CBD5E1">{escape(r["version"])}</text>',
        f'<text x="{TILE - 10}" y="18" font-size="10" fill="{color}" text-anchor="end">{escape(AMBITO[r["ambito"]])}</text>',
        f'<text x="{TILE // 2}" y="62" font-size="32" font-weight="700" fill="{color}" text-anchor="middle">{escape(r["simbolo"])}</text>',
    ]
    lineas = r["etiqueta"].split("|")
    y0 = 86 if len(lineas) == 2 else 94
    for i, l in enumerate(lineas):
        partes.append(f'<text x="{TILE // 2}" y="{y0 + i * 15}" font-size="12.5" fill="#F1F5F9" text-anchor="middle">{escape(l)}</text>')
    partes.append("</g>")
    return partes


def leyenda(x0: int, y0: int, por_fila: int, paso: int) -> list[str]:
    s = []
    for i, (k, n, c) in enumerate(FAMILIAS):
        x = x0 + (i % por_fila) * paso
        y = y0 + (i // por_fila) * 26
        s.append(f'<rect x="{x}" y="{y}" width="16" height="16" rx="4" fill="{c}"/>')
        s.append(f'<text x="{x + 24}" y="{y + 13}" font-size="15" fill="#E2E8F0">{escape(n)}</text>')
    return s


def generar_poster(filas: list[dict]) -> str:
    columnas = []
    for nombre, versiones, anio in COLUMNAS:
        items = [r for v in versiones for r in filas if r["version"] == v and r["poster"] == "1"]
        columnas.append((nombre, anio, items))
    alto_max = max(len(i) for _, _, i in columnas)
    ancho = MARGEN * 2 + len(columnas) * (TILE + GAP) - GAP
    alto = CABECERA + 56 + alto_max * (TILE + GAP) + 96
    total = sum(len(i) for _, _, i in columnas)
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" width="{ancho}" height="{alto}" font-family="{FUENTE}" role="img" aria-labelledby="pt">',
        f'<title id="pt">Tabla periódica de las características de EF Core, edición {EDICION}</title>',
        f"<defs>{FONDO}</defs>", fondo(ancho, alto),
        f'<text x="{MARGEN}" y="80" font-size="48" font-weight="700" fill="#F8FAFC">Tabla periódica de EF Core</text>',
        f'<text x="{MARGEN}" y="118" font-size="19" fill="#99F6E4">{total} elementos esenciales de {len(filas)} catalogados · '
        f'cada columna es una versión, de EF Core 1.0 (2016) a EF Core 11 (2026) · edición {EDICION}</text>',
    ]
    s += leyenda(MARGEN, 146, 5, 250)
    for ci, (nombre, anio, items) in enumerate(columnas):
        x = MARGEN + ci * (TILE + GAP)
        y = CABECERA + 14
        lts = nombre in {"2", "3", "6", "8", "10"}
        s.append(f'<text x="{x + TILE // 2}" y="{y + 10}" font-size="21" font-weight="700" fill="#F8FAFC" text-anchor="middle">EF {nombre}</text>')
        s.append(f'<text x="{x + TILE // 2}" y="{y + 30}" font-size="13" fill="#7DD3FC" text-anchor="middle">{anio}{" · LTS" if lts else ""}</text>')
        s.append(f'<line x1="{x + 8}" y1="{y + 42}" x2="{x + TILE - 8}" y2="{y + 42}" stroke="url(#trazo)" stroke-opacity="0.6"/>')
        for ti, r in enumerate(items):
            s += tile(r, x, CABECERA + 64 + ti * (TILE + GAP))
    s.append(f'<text x="{MARGEN}" y="{alto - 36}" font-size="14" fill="#94A3B8">Borde discontinuo: EF Core 11, en release candidate al '
             f'{FECHA_CORTE}. EF Core 4 no existe: la numeración saltó de 3.1 a 5.0. Fuente: data/caracteristicas.csv · guía no oficial.</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


# --------------------------------------------------------------------------- espiral
def generar_espiral(filas: list[dict]) -> str:
    """Cada característica es un punto sobre una espiral de Arquímedes: el ángulo avanza con el tiempo
    y el radio crece versión a versión. El color indica la familia; el tamaño, si es un elemento del póster."""
    w, h = 1400, 1500
    cx, cy = w / 2, h / 2 + 70
    orden = list(VERSIONES)
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{FUENTE}" role="img" aria-labelledby="et">',
        f'<title id="et">Espiral de EF Core: {len(filas)} características de 2016 a 2026</title>',
        f'<defs>{FONDO}<filter id="brillo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
        fondo(w, h),
        '<text x="60" y="86" font-size="46" font-weight="700" fill="#F8FAFC">La espiral de EF Core</text>',
        f'<text x="60" y="124" font-size="19" fill="#99F6E4">{len(filas)} características, una vuelta por cada era · '
        'del centro (2016) al borde (2026)</text>',
    ]
    s += leyenda(60, 150, 5, 255)
    total = len(filas)
    vueltas = 3.2
    r0, r1 = 120, 560

    def punto(t: float) -> tuple[float, float, float]:
        ang = -math.pi / 2 + t * vueltas * 2 * math.pi
        rad = r0 + (r1 - r0) * t
        return cx + rad * math.cos(ang), cy + rad * math.sin(ang), ang

    # Guía: la propia espiral, muestreada finamente para repartir los puntos a igual distancia de arco
    muestras = [punto(i / 4000) for i in range(4001)]
    arco = [0.0]
    for (xa, ya, _), (xb, yb, _) in zip(muestras, muestras[1:]):
        arco.append(arco[-1] + math.hypot(xb - xa, yb - ya))

    def en_arco(fraccion: float) -> tuple[float, float, float]:
        objetivo = fraccion * arco[-1]
        lo, hi = 0, len(arco) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if arco[mid] < objetivo:
                lo = mid + 1
            else:
                hi = mid
        return muestras[lo]

    puntos = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in muestras[::5])
    s.append(f'<polyline points="{puntos}" fill="none" stroke="url(#trazo)" stroke-width="2" stroke-opacity="0.35"/>')
    filas_ordenadas = sorted(filas, key=lambda r: orden.index(r["version"]))
    inicio_version: dict[str, float] = {}
    for i, r in enumerate(filas_ordenadas):
        inicio_version.setdefault(r["version"], (i + 0.5) / total)
    marcas = {}
    for v, t in inicio_version.items():
        if v not in {"1.0", "1.1", "2.1", "2.2", "3.1"}:
            xa, ya, ang = en_arco(t)
            marcas[v] = (xa - 40 * math.cos(ang), ya - 40 * math.sin(ang))
    cajas: list[tuple[float, float, float, float]] = [(mx - 24, my - 24, mx + 24, my + 24) for mx, my in marcas.values()]
    cajas.append((cx - 46, cy - 46, cx + 46, cy + 46))
    posiciones = [en_arco((i + 0.5) / total) for i in range(total)]
    cajas += [(px - 6, py - 6, px + 6, py + 6) for px, py, _ in posiciones]

    def libre(caja: tuple[float, float, float, float]) -> bool:
        x0, y0, x1, y1 = caja
        return all(x1 < a0 or x0 > a1 or y1 < b0 or y0 > b1 for a0, b0, a1, b1 in cajas)

    etiquetas = []
    for i, r in enumerate(filas_ordenadas):
        x, y, ang = posiciones[i]
        color = COLOR_FAMILIA[r["familia"]]
        grande = r["poster"] == "1"
        radio = 9 if grande else 5.5
        trazo = ' stroke="#F8FAFC" stroke-width="1.2" stroke-dasharray="2 2"' if r["estado"] != "GA" else ""
        filtro = ' filter="url(#brillo)"' if grande else ""
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radio}" fill="{color}" fill-opacity="0.92"{trazo}{filtro}><title>'
                 f'{escape(r["nombre"])} · EF Core {r["version"]}</title></circle>')
        if not grande:
            continue
        texto = r["etiqueta"].replace("|", " ")
        ancho_txt = 6.4 * len(texto)
        elegida = None
        # Candidatas: hacia fuera y hacia dentro de la espiral, cada vez más lejos del punto
        for distancia in (16, 30, 46):
            for lado in (1, -1):
                ux, uy = lado * math.cos(ang), lado * math.sin(ang)
                tx, ty = x + distancia * ux, y + distancia * uy + 4
                ancla = "start" if ux >= 0.35 else ("end" if ux <= -0.35 else "middle")
                x0 = {"start": tx, "end": tx - ancho_txt, "middle": tx - ancho_txt / 2}[ancla]
                caja = (x0 - 2, ty - 12, x0 + ancho_txt + 2, ty + 3)
                if libre(caja):
                    elegida = (tx, ty, ancla, caja)
                    break
            if elegida:
                break
        if elegida is None:
            ux, uy = math.cos(ang), math.sin(ang)
            tx, ty = x + 16 * ux, y + 16 * uy + 4
            elegida = (tx, ty, "start" if ux >= 0 else "end", (0, 0, 0, 0))
        tx, ty, ancla, caja = elegida
        cajas.append(caja)
        etiquetas.append(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="12" fill="#E2E8F0" text-anchor="{ancla}">{escape(texto)}</text>')
    s += etiquetas
    # Marcas de versión
    for v, (x, y) in marcas.items():
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="21" fill="#030B14" stroke="url(#trazo)" stroke-width="2"/>')
        s.append(f'<text x="{x:.1f}" y="{y + 5:.1f}" font-size="14" font-weight="700" fill="#F8FAFC" text-anchor="middle">{v.replace(".0", "")}</text>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="44" fill="#030B14" stroke="#2DD4BF" stroke-width="2"/>')
    s.append(f'<text x="{cx}" y="{cy - 2}" font-size="17" font-weight="700" fill="#99F6E4" text-anchor="middle">2016</text>')
    s.append(f'<text x="{cx}" y="{cy + 17}" font-size="12" fill="#CBD5E1" text-anchor="middle">nace EF Core</text>')
    s.append(f'<text x="60" y="{h - 40}" font-size="14" fill="#94A3B8">Puntos grandes: elementos de la tabla periódica · borde punteado: '
             f'EF Core 11 en release candidate · fuente: data/caracteristicas.csv</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


# --------------------------------------------------------------------------- banner
HITOS = [("1.0", "DbContext"), ("2.1", "Lazy · HasData"), ("3.0", "Sin eval. cliente"), ("5", "Muchos a muchos"),
         ("6", "Temporales"), ("7", "JSON · Execute"), ("8", "Complex types"), ("9", "AOT · Cosmos"),
         ("10", "Vectores"), ("11", "FullJoin")]


def generar_banner(filas: list[dict]) -> str:
    w, h = 1600, 440
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{FUENTE}" role="img" aria-labelledby="bt">',
        '<title id="bt">EF Core Atlas · Guía técnica de Entity Framework Core, versión por versión</title>',
        f"<defs>{FONDO}</defs>", fondo(w, h),
        # Emblema: un cilindro de base de datos atravesado por un grafo de objetos
        '<g transform="translate(70,64)">'
        '<ellipse cx="56" cy="16" rx="56" ry="16" fill="#0C2E44" stroke="url(#trazo)" stroke-width="3"/>'
        '<path d="M0 16 V100 A56 16 0 0 0 112 100 V16" fill="#0C2E44" fill-opacity="0.85" stroke="url(#trazo)" stroke-width="3"/>'
        '<path d="M0 44 A56 16 0 0 0 112 44 M0 72 A56 16 0 0 0 112 72" fill="none" stroke="#2DD4BF" stroke-opacity="0.5" stroke-width="2"/>'
        '<g stroke="#F8FAFC" stroke-width="2" stroke-opacity="0.85"><line x1="30" y1="52" x2="82" y2="38"/><line x1="30" y1="52" x2="62" y2="88"/>'
        '<line x1="82" y1="38" x2="62" y2="88"/></g>'
        '<circle cx="30" cy="52" r="8" fill="#A78BFA"/><circle cx="82" cy="38" r="8" fill="#38BDF8"/><circle cx="62" cy="88" r="8" fill="#FACC15"/>'
        '</g>',
        '<text x="216" y="118" font-size="74" font-weight="700" fill="#F8FAFC">EF Core Atlas</text>',
        '<text x="218" y="164" font-size="27" fill="#99F6E4">Entity Framework Core: el ORM moderno de .NET, versión por versión</text>',
        f'<text x="218" y="200" font-size="19" fill="#7DD3FC">De EF Core 1.0 a EF Core 11 · {len(filas)} características · '
        f'ejemplos ejecutados · {EDICION}</text>',
    ]
    x0, x1, y = 92, 1508, 322
    s.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="url(#trazo)" stroke-width="3"/>')
    paso = (x1 - x0) / (len(HITOS) - 1)
    for i, (v, nombre) in enumerate(HITOS):
        x = x0 + i * paso
        ultimo = i == len(HITOS) - 1
        lts = v in {"2.1", "6", "8", "10"}
        color = "#FACC15" if ultimo else ("#2DD4BF" if lts else "#A5B4FC")
        s.append(f'<circle cx="{x:.0f}" cy="{y}" r="{13 if lts else 10}" fill="#030B14" stroke="{color}" stroke-width="3"/>')
        if lts:
            s.append(f'<circle cx="{x:.0f}" cy="{y}" r="4" fill="{color}"/>')
        s.append(f'<text x="{x:.0f}" y="{y - 26}" font-size="19" font-weight="700" fill="#F8FAFC" text-anchor="middle">EF {v}</text>')
        s.append(f'<text x="{x:.0f}" y="{y + 40}" font-size="15" fill="{color}" text-anchor="middle">{escape(nombre)}</text>')
    s.append(f'<text x="{x0}" y="{h - 22}" font-size="14" fill="#64748B">● con punto: versión LTS · amarillo: release candidate</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


def main() -> None:
    filas = leer()
    CATALOGO.write_text(generar_catalogo(filas), encoding="utf-8")
    POSTER.write_text(generar_poster(filas), encoding="utf-8")
    ESPIRAL.write_text(generar_espiral(filas), encoding="utf-8")
    BANNER.write_text(generar_banner(filas), encoding="utf-8")
    print(f"{len(filas)} características → {CATALOGO.name}, {POSTER.name}, {ESPIRAL.name}, {BANNER.name}")


if __name__ == "__main__":
    main()
