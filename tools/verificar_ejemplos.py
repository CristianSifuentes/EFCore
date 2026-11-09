#!/usr/bin/env python3
"""Compila (y opcionalmente ejecuta) cada bloque ```csharp del atlas contra EF Core real.

Cada bloque se convierte en el Program.cs de un proyecto de consola (.NET 10, SDK Web) que referencia
EF Core 10 con los proveedores SQLite, SQL Server, Cosmos, InMemory, PostgreSQL (Npgsql) y Proxies.
Los bloques marcados con `run` se ejecutan sobre SQLite y su salida se compara con los comentarios `// →`.

Marcas en Markdown
  <!-- ef=N -->                 versión de EF Core de los bloques siguientes del archivo (informativa)
  ```csharp                     se compila
  ```csharp run                 se compila, se ejecuta y se compara la salida con los comentarios `// → texto`
  ```csharp lanza=Tipo          se ejecuta y DEBE terminar con esa excepción (p. ej. InvalidOperationException)
  ```csharp err=CS1234          el bloque DEBE fallar al compilar con ese error
  ```csharp ef11                API de EF Core 11 (RC): se omite hasta que exista un SDK de .NET 11 estable
  ```csharp omitir              no se compila (fragmento, pseudocódigo o código generado)

Uso:
  python3 tools/verificar_ejemplos.py [--solo 13-] [--lista] [--hilos 6] [--conservar]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EF = "10.0.14"
NPGSQL = "10.0.3"
FLAGS = {"run", "ef11", "omitir"}

PROYECTO = f"""<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <AssemblyName>Ejemplo</AssemblyName>
    <NoWarn>$(NoWarn);CS1591;CS8618;CS0162;CS0168;CS0219;CS1998;CS8321;ASP0000;EF1001;EF1002;EF9100;NU1902;NU1903</NoWarn>
    <InvariantGlobalization>true</InvariantGlobalization>
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="{EF}" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="{EF}" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Cosmos" Version="{EF}" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.InMemory" Version="{EF}" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Proxies" Version="{EF}" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer.HierarchyId" Version="{EF}" />
    <PackageReference Include="Npgsql.EntityFrameworkCore.PostgreSQL" Version="{NPGSQL}" />
  </ItemGroup>
  <ItemGroup>
    <Using Include="Microsoft.EntityFrameworkCore" />
    <Using Include="Microsoft.EntityFrameworkCore.ChangeTracking" />
    <Using Include="Microsoft.EntityFrameworkCore.Diagnostics" />
    <Using Include="Microsoft.EntityFrameworkCore.Metadata.Builders" />
    <Using Include="Microsoft.EntityFrameworkCore.Storage.ValueConversion" />
    <Using Include="System.ComponentModel.DataAnnotations" />
    <Using Include="System.ComponentModel.DataAnnotations.Schema" />
    <Using Include="Microsoft.Data.Sqlite" />
  </ItemGroup>
</Project>
"""


@dataclass
class Bloque:
    archivo: Path
    linea: int
    codigo: str
    ef: str
    flags: set[str] = field(default_factory=set)
    err: str | None = None
    lanza: str | None = None

    @property
    def nombre(self) -> str:
        return f"{self.archivo.relative_to(RAIZ)}:{self.linea}"


def leer_bloques(archivo: Path) -> list[Bloque]:
    bloques: list[Bloque] = []
    ef = "10"
    lineas = archivo.read_text(encoding="utf-8").split("\n")
    i = 0
    while i < len(lineas):
        texto = lineas[i]
        directiva = re.fullmatch(r"\s*<!--\s*ef=([\d.]+)\s*-->\s*", texto)
        if directiva:
            ef = directiva.group(1)
        apertura = re.fullmatch(r"\s*```csharp(.*)", texto)
        if apertura:
            inicio = i + 1
            info = apertura.group(1).split()
            cuerpo: list[str] = []
            i += 1
            while not re.fullmatch(r"\s*```\s*", lineas[i]):
                cuerpo.append(lineas[i])
                i += 1
            b = Bloque(archivo, inicio, "\n".join(cuerpo), ef)
            for palabra in info:
                if palabra.startswith("err="):
                    b.err = palabra[4:]
                elif palabra.startswith("lanza="):
                    b.lanza = palabra[6:]
                elif palabra in FLAGS:
                    b.flags.add(palabra)
                else:
                    raise SystemExit(f"{archivo}:{inicio}: marca desconocida {palabra!r}")
            if b.ef == "11" and not b.flags & {"omitir"}:
                b.flags.add("ef11")
            bloques.append(b)
        i += 1
    return bloques


def preparar_plantilla(dotnet: str, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "Ejemplo.csproj").write_text(PROYECTO, encoding="utf-8")
    (destino / "Program.cs").write_text('Console.WriteLine("ok");\n', encoding="utf-8")
    r = subprocess.run([dotnet, "build", "-v", "q", "-nologo"], cwd=destino, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("No se pudo preparar el proyecto plantilla:\n" + r.stdout[-3000:])


def verificar(b: Bloque, dotnet: str, plantilla: Path, trabajo: Path) -> tuple[Bloque, str | None]:
    d = trabajo
    (d / "Program.cs").write_text(b.codigo + "\n", encoding="utf-8")
    for f in d.glob("*.db*"):
        f.unlink()
    def compilar(*extra: str) -> tuple[subprocess.CompletedProcess, str, list[str]]:
        r = subprocess.run([dotnet, "build", "--no-restore", "-v", "q", "-nologo", "-clp:NoSummary", *extra],
                           cwd=d, capture_output=True, text=True)
        salida = r.stdout + r.stderr
        return r, salida, sorted(set(re.findall(r"error ([A-Z]+\d+)", salida)))

    r, salida, errores = compilar()
    if errores == ["CS5001"]:                       # bloque sin instrucciones de nivel superior: es una biblioteca
        r, salida, errores = compilar("-p:OutputType=Library")
    if b.err:
        return (b, None) if b.err in errores else (b, f"se esperaba {b.err}; errores: {errores or 'ninguno'}")
    if r.returncode != 0:
        lineas = [l.split("Program.cs", 1)[-1] for l in salida.splitlines() if " error " in l]
        return b, "\n".join(dict.fromkeys(lineas))[:1500]
    if not ({"run"} & b.flags or b.lanza):
        return b, None
    try:
        e = subprocess.run([dotnet, str(d / "bin" / "Debug" / "net10.0" / "Ejemplo.dll")], cwd=d,
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return b, "la ejecución excedió 60 s"
    if b.lanza:
        if e.returncode != 0 and b.lanza in e.stderr:
            return b, None
        return b, f"se esperaba la excepción {b.lanza}; código {e.returncode}\n{e.stderr[:600]}"
    esperado = [x.rstrip() for x in re.findall(r"//\s*→ ?(.*)$", b.codigo, flags=re.M)]
    obtenido = [l.rstrip() for l in e.stdout.splitlines()]
    if e.returncode != 0 or obtenido != esperado:
        diferencias = [f"  {i + 1}: esperado {x!r}\n     obtenido {y!r}" for i, (x, y) in
                       enumerate(zip(esperado + [""] * 99, obtenido + [""] * 99)) if x != y][:6]
        return b, "salida distinta\n" + "\n".join(diferencias) + ("\n" + e.stderr[:800] if e.stderr else "")
    return b, None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dotnet", default=os.environ.get("DOTNET_ATLAS", "dotnet"))
    p.add_argument("--solo", help="filtra archivos cuyo nombre contenga este texto")
    p.add_argument("--lista", action="store_true", help="solo cuenta los bloques")
    p.add_argument("--hilos", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    a = p.parse_args()

    archivos = [RAIZ / "README.md", *sorted((RAIZ / "docs").glob("*.md"))]
    bloques = [b for f in archivos if not a.solo or a.solo in f.name for b in leer_bloques(f)]
    activos = [b for b in bloques if not b.flags & {"omitir", "ef11"}]
    ef11 = sum("ef11" in b.flags for b in bloques)
    if a.lista:
        print(f"{len(bloques)} bloques · {len(activos)} verificables · {sum('run' in b.flags for b in activos)} se ejecutan · "
              f"{ef11} de EF Core 11 · {sum('omitir' in b.flags for b in bloques)} omitidos")
        return 0

    with tempfile.TemporaryDirectory(prefix="efatlas-") as tmp:
        base = Path(tmp)
        plantilla = base / "plantilla"
        print(f"Preparando plantilla con EF Core {EF}…")
        preparar_plantilla(a.dotnet, plantilla)
        trabajos = []
        for n in range(a.hilos):
            t = base / f"w{n}"
            shutil.copytree(plantilla, t)
            trabajos.append(t)
        colas = [activos[n::a.hilos] for n in range(a.hilos)]

        def procesar(n: int) -> list[tuple[Bloque, str | None]]:
            return [verificar(b, a.dotnet, plantilla, trabajos[n]) for b in colas[n]]

        fallos = 0
        with cf.ThreadPoolExecutor(a.hilos) as ex:
            for resultados in ex.map(procesar, range(a.hilos)):
                for b, error in resultados:
                    if error:
                        fallos += 1
                        print(f"\n✗ {b.nombre}\n{error}")
    ejecutados = sum(bool("run" in b.flags or b.lanza) for b in activos)
    negativos = sum(bool(b.err) for b in activos)
    print(f"\n{len(activos) - fallos}/{len(activos)} correctos · {ejecutados} ejecutados sobre SQLite · "
          f"{negativos} con error de compilación esperado · {ef11} de EF Core 11 sin verificar · "
          f"{sum('omitir' in b.flags for b in bloques)} omitidos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
