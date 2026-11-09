<div align="center">

# 08 · EF Core 8: tipos complejos y colecciones primitivas

**Objetos de valor de verdad, `List<string>` en una columna, SQL crudo con tipos no mapeados, `HierarchyId` y `DateOnly` (2023, LTS)**

[⬅ 07 · EF Core 7](07-ef-core-7-json-y-operaciones-masivas.md) · [🏠 Índice](../README.md) · [09 · EF Core 9 ➡](09-ef-core-9-cosmos-aot-y-siembra.md)

</div>

<!-- ef=10 -->

| Ficha | EF Core 8.0 |
|---|---|
| **Publicación** | 14-nov-2023, junto con .NET 8 y C# 12 |
| **Plataforma** | `net8.0` |
| **Soporte** | 🟠 **LTS hasta el 10-nov-2026**: termina dentro de dos días |
| **Idea central** | Modelado orientado a valores y JSON como ciudadano de primera |

> [!WARNING]
> **EF Core 8 deja de tener soporte el 10 de noviembre de 2026.** Si tu aplicación está en EF Core 8, el plan de migración a EF Core 10 está en el
> [capítulo 23](23-migracion-entre-versiones.md#2-de-ef-core-8-o-9-a-ef-core-10).

---

## Contenido

1. [Entidades, tipos propios y tipos complejos](#1-entidades-tipos-propios-y-tipos-complejos)
2. [Tipos complejos](#2-tipos-complejos)
3. [Colecciones primitivas](#3-colecciones-primitivas)
4. [Colecciones parametrizadas: el fin del `IN` con constantes](#4-colecciones-parametrizadas-el-fin-del-in-con-constantes)
5. [SQL crudo con tipos no mapeados](#5-sql-crudo-con-tipos-no-mapeados)
6. [Buscar entidades seguidas](#6-buscar-entidades-seguidas)
7. [Más novedades de EF Core 8](#7-más-novedades-de-ef-core-8)
8. [Cambios incompatibles](#8-cambios-incompatibles)
9. [Referencias](#9-referencias)

---

## 1. Entidades, tipos propios y tipos complejos

En el diseño guiado por el dominio (DDD) hay dos tipos de objetos: **entidades** (tienen identidad: dos clientes con el mismo nombre son distintos) y
**objetos de valor** (se definen por su contenido: dos direcciones con los mismos datos son la misma dirección). EF Core tuvo durante años una sola
herramienta para los objetos de valor, los **tipos propios**, que **por dentro eran entidades**.

| | Entidad | Tipo propio (2.0) | **Tipo complejo (8.0)** |
|---|---|---|---|
| Identidad | Clave primaria | Clave **oculta** heredada del dueño | **Ninguna** |
| Semántica | Referencia | Referencia | **Valor** |
| Compartir una instancia entre dos propiedades | ✅ | ❌ error | ✅ se copia |
| Comparar en LINQ (`a.Envio == a.Facturacion`) | Por clave | Por clave | **Por contenido** |
| `struct` | ❌ | ❌ | ✅ (EF Core 10) |
| Opcional (`Direccion?`) | ✅ | ✅ | ✅ (EF Core 10) |
| Colecciones | ✅ | `OwnsMany` | ✅ solo en JSON (EF Core 10) |
| JSON | — | `ToJson` (7.0) | `ToJson` (EF Core 10) |
| `ExecuteUpdate` | ✅ | ❌ | ✅ (EF Core 9 en columnas, 10 en JSON) |

> [!TIP]
> **Regla actual (2026):** usa **tipos complejos** para objetos de valor, tanto en columnas como en JSON. Los tipos propios siguen funcionando, pero el
> equipo de EF recomienda migrar y EF Core 11 marca como obsoletas las colecciones propias JSON sin clave.

---

## 2. Tipos complejos

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

var direccion = new Direccion { Calle = "Gran Vía 1", Ciudad = "Madrid" };
var cliente = new Cliente { Nombre = "Lucía", Envio = direccion, Facturacion = direccion };   // la misma instancia, dos veces
db.Add(cliente);
db.SaveChanges();                                         // con tipos propios, esto lanzaría una excepción

var mismas = db.Clientes.Count(c => c.Envio == c.Facturacion);
Console.WriteLine(mismas);                                // → 1

Console.WriteLine(db.Database.GenerateCreateScript().Trim());
// → CREATE TABLE "Clientes" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_Clientes" PRIMARY KEY AUTOINCREMENT,
// →     "Nombre" TEXT NOT NULL,
// →     "Envio_Calle" TEXT NOT NULL,
// →     "Envio_Ciudad" TEXT NOT NULL,
// →     "Facturacion_Calle" TEXT NOT NULL,
// →     "Facturacion_Ciudad" TEXT NOT NULL
// → );

public record Direccion
{
    public required string Calle { get; init; }
    public required string Ciudad { get; init; }
}

public class Cliente
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public required Direccion Envio { get; set; }
    public required Direccion Facturacion { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Cliente> Clientes => Set<Cliente>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
    protected override void OnModelCreating(ModelBuilder b) => b.Entity<Cliente>(c =>
    {
        c.ComplexProperty(x => x.Envio);
        c.ComplexProperty(x => x.Facturacion);
    });
}
```

`c.Envio == c.Facturacion` se tradujo comparando **columna a columna**. Y un `record` con propiedades `init` es el compañero natural de un tipo complejo:
inmutable y con igualdad por valor también en .NET.

> [!NOTE]
> También existe el atributo `[ComplexType]` sobre la clase, que evita repetir `ComplexProperty` en cada entidad que la use.

---

## 3. Colecciones primitivas

Un `List<string>`, `int[]` o `HashSet<DateOnly>` ya no necesita una tabla aparte: EF Core 8 lo guarda como **un arreglo JSON en una columna** y
**traduce consultas sobre él**:

```csharp run
using var db = new Blog();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.AddRange(
    new Entrada { Titulo = "Novedades de EF8", Etiquetas = ["ef-core", "dotnet"] },
    new Entrada { Titulo = "Patrones de LINQ", Etiquetas = ["linq"] });
db.SaveChanges();

var guardado = db.Database.SqlQuery<string>($"SELECT Etiquetas AS Value FROM Entradas WHERE Id = 1").Single();
Console.WriteLine(guardado);                                                   // → ["ef-core","dotnet"]

var consulta = db.Entradas.Where(e => e.Etiquetas.Contains("dotnet")).Select(e => e.Titulo);
Console.WriteLine(consulta.ToQueryString());
// → SELECT "e"."Titulo"
// → FROM "Entradas" AS "e"
// → WHERE 'dotnet' IN (
// →     SELECT "e0"."value"
// →     FROM json_each("e"."Etiquetas") AS "e0"
// → )
Console.WriteLine(consulta.Single());                                          // → Novedades de EF8
Console.WriteLine(db.Entradas.Count(e => e.Etiquetas.Count > 1));              // → 1

public class Entrada
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public List<string> Etiquetas { get; set; } = [];
}

public class Blog : DbContext
{
    public DbSet<Entrada> Entradas => Set<Entrada>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=blog.db");
}
```

| Proveedor | Almacenamiento | Desempaquetado en SQL |
|---|---|---|
| SQL Server ≤ 2022 | `nvarchar(max)` con JSON | `OPENJSON` |
| SQL Server 2025 / Azure SQL | tipo `json` (EF Core 10) | `OPENJSON`, `JSON_CONTAINS` (EF Core 11) |
| SQLite | `TEXT` con JSON | `json_each` |
| PostgreSQL | **arreglos nativos** (`text[]`, `int[]`) | `= ANY(...)`, `unnest` |
| Cosmos DB | arreglos JSON nativos | `ARRAY_CONTAINS` |

---

## 4. Colecciones parametrizadas: el fin del `IN` con constantes

El otro lado de las colecciones primitivas son las **colecciones de tu código** dentro de una consulta: `ids.Contains(x.Id)`. Su traducción ha cambiado
tres veces:

| Versión | Traducción por defecto | Problema que resolvía | Problema que creaba |
|---|---|---|---|
| ≤ 7 | `IN (1, 2, 3)` con **constantes** | — | Un SQL distinto por cada lista: caché de planes inflada |
| **8 y 9** | **Un parámetro JSON** (`OPENJSON(@ids)`, `json_each(@ids)`) | Un único SQL para cualquier lista | El optimizador no conoce el tamaño de la lista |
| 10 | Varios parámetros con relleno: `IN (@ids1, @ids2, @ids3)` | Plan reutilizable **y** cardinalidad conocida | — |

EF Core 9 y 10 permiten elegir la estrategia, global o por consulta. Esta es la traducción de EF Core 8, que puedes forzar hoy con `EF.Parameter`:

```csharp run
using var db = new Tienda();
int[] ids = [1, 2, 3];
Console.WriteLine(db.Productos.Where(p => EF.Parameter(ids).Contains(p.Id)).ToQueryString());
// → .param set @ids '[1,2,3]'
// →
// → SELECT "p"."Id", "p"."Nombre"
// → FROM "Productos" AS "p"
// → WHERE "p"."Id" IN (
// →     SELECT "i"."value"
// →     FROM json_each(@ids) AS "i"
// → )

public class Producto { public int Id { get; set; } public required string Nombre { get; set; } }

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

La comparación de las tres estrategias con el SQL de EF Core 10 está en el
[capítulo 10](10-ef-core-10-lts-vectores-y-json.md#5-colecciones-parametrizadas-con-varios-parámetros).

> [!CAUTION]
> **El cambio incompatible más famoso de EF Core 8**: `OPENJSON` exige **nivel de compatibilidad 130** (SQL Server 2016). Bases antiguas, o actualizadas
> sin subir el nivel de compatibilidad, empezaron a fallar con `Incorrect syntax near '$'`. La solución es
> `UseSqlServer(cadena, o => o.UseCompatibilityLevel(120))` o subir el nivel en la base.

---

## 5. SQL crudo con tipos no mapeados

EF Core 7 permitía `SqlQuery<int>`; EF Core 8 permite **cualquier tipo**, incluidos DTO que no son entidades del modelo. Es el "Dapper integrado":

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.AddRange(
    new Producto { Nombre = "A", Categoria = "Oficina", Stock = 3 },
    new Producto { Nombre = "B", Categoria = "Oficina", Stock = 7 },
    new Producto { Nombre = "C", Categoria = "Hogar", Stock = 1 });
db.SaveChanges();

var minimo = 2;
var resumen = db.Database.SqlQuery<ResumenCategoria>($"""
    SELECT Categoria, COUNT(*) AS Productos, SUM(Stock) AS Unidades
    FROM Productos
    GROUP BY Categoria
    """)
    .Where(r => r.Productos >= minimo)            // ¡componible con LINQ!
    .ToList();

foreach (var r in resumen)
    Console.WriteLine($"{r.Categoria}: {r.Productos} productos, {r.Unidades} unidades");   // → Oficina: 2 productos, 10 unidades

public record ResumenCategoria(string Categoria, int Productos, int Unidades);

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public required string Categoria { get; set; }
    public int Stock { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

| API | Devuelve | Seguimiento | Parametrización |
|---|---|---|---|
| `DbSet<T>.FromSql($"...")` | Entidades del modelo | Sí | Interpolación segura |
| `Database.SqlQuery<T>($"...")` | Escalares (7.0) o DTO (8.0) | No | Interpolación segura |
| `Database.SqlQueryRaw<T>("...", params)` | Igual | No | **Manual**: cuidado con la inyección SQL |
| `Database.ExecuteSql($"...")` | Filas afectadas | — | Interpolación segura |

---

## 6. Buscar entidades seguidas

`DbSet<T>.Local.FindEntry` y sus variantes consultan **solo el *change tracker***, sin ir a la base de datos:

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.AddRange(new Producto { Nombre = "Atril" }, new Producto { Nombre = "Bolígrafo" });
db.SaveChanges();

var entrada = db.Productos.Local.FindEntry(2);
Console.WriteLine(entrada?.Entity.Nombre);                                           // → Bolígrafo
Console.WriteLine(entrada?.State);                                                   // → Unchanged

var porNombre = db.Productos.Local.GetEntries(nameof(Producto.Nombre), "Atril").Single();
Console.WriteLine(porNombre.Entity.Id);                                              // → 1

public class Producto { public int Id { get; set; } public required string Nombre { get; set; } }

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

---

## 7. Más novedades de EF Core 8

| Novedad | Descripción |
|---|---|
| **Carga diferida sin seguimiento** | Las navegaciones de entidades `AsNoTracking` también pueden cargarse bajo demanda |
| **`HierarchyId`** | Árboles con el tipo `hierarchyid` de SQL Server (paquete `…SqlServer.HierarchyId`) |
| **`DateOnly` y `TimeOnly`** en SQL Server | Mapeo nativo a `date` y `time` |
| **JSON en SQLite** | Columnas JSON y colecciones primitivas sobre `json_each` y `->>` |
| **Valores centinela** | `HasSentinel(valor)`: qué valor CLR significa "no establecido" para valores por defecto de la base |
| `[DeleteBehavior]` | Comportamiento en cascada como atributo |
| Mapeo de columnas JSON a colecciones de tipos propios en Cosmos | Mejoras de consulta |
| Mejoras de `Math.Max`/`Min` | Traducciones nuevas |
| Modelos compilados más completos | Soportan más características |
| Discriminadores de longitud máxima automática | Columnas más pequeñas |

### Valores centinela: un error sutil corregido

```csharp
public class Cuenta
{
    public int Id { get; set; }
    public int Credito { get; set; }               // la base tiene DEFAULT 100
}

public class Banco : DbContext
{
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Cuenta>().Property(c => c.Credito)
            .HasDefaultValue(100)
            .HasSentinel(-1);   // sin esto, Credito = 0 se interpreta como "no establecido" y la base pone 100
}
```

---

## 8. Cambios incompatibles

| Cambio | Impacto | Mitigación |
|---|---|---|
| `Contains` con colecciones usa `OPENJSON`: falla en SQL Server < 2016 o compatibilidad < 130 | 🔴 Alto | `UseCompatibilityLevel(120)` |
| Enums dentro de JSON se guardan como enteros | 🟠 Medio | Conversión explícita a texto |
| SQL Server: `DateOnly`/`TimeOnly` se mapean nativamente | 🟡 Bajo | Revisa migraciones de columnas existentes |
| SQLite: las conversiones de valor de `decimal` cambian el orden | 🟡 Bajo | — |
| `IProperty.GetValueComparer` devuelve un comparador más estricto | 🟡 Bajo | — |
| Cosmos: los discriminadores se añaden a la clave | 🟡 Bajo | — |

---

## 9. Referencias

- [What's new in EF Core 8.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-8.0/whatsnew)
- [Complex types](https://learn.microsoft.com/ef/core/modeling/complex-types)
- [Primitive collections](https://learn.microsoft.com/ef/core/what-is-new/ef-core-8.0/whatsnew#primitive-collections)
- [SQL queries](https://learn.microsoft.com/ef/core/querying/sql-queries)
- [Breaking changes in EF Core 8.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-8.0/breaking-changes)

<div align="center">

[⬅ 07 · EF Core 7](07-ef-core-7-json-y-operaciones-masivas.md) · [🏠 Índice](../README.md) · [09 · EF Core 9 ➡](09-ef-core-9-cosmos-aot-y-siembra.md)

</div>
