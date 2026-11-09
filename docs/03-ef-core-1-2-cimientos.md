<div align="center">

# 03 · EF Core 1 y 2: los cimientos

**La reescritura de 2016, los primeros años de vida y las piezas que todavía sostienen cada aplicación (2016–2018)**

[⬅ 02 · Anatomía](02-anatomia-de-ef-core.md) · [🏠 Índice](../README.md) · [04 · EF Core 3 ➡](04-ef-core-3-la-gran-ruptura.md)

</div>

<!-- ef=10 -->

| Ficha | EF Core 1.0 | 1.1 | 2.0 | 2.1 | 2.2 |
|---|---|---|---|---|---|
| **Publicación** | 27-jun-2016 | 16-nov-2016 | 14-ago-2017 | 30-may-2018 | 4-dic-2018 |
| **Plataforma** | .NET Standard 1.3 | .NET Standard 1.3 | .NET Standard 2.0 | .NET Standard 2.0 | .NET Standard 2.0 |
| **Acompañaba a** | ASP.NET Core 1.0 | ASP.NET Core 1.1 | ASP.NET Core 2.0 | ASP.NET Core 2.1 | ASP.NET Core 2.2 |
| **Soporte** | ⛔ | ⛔ | ⛔ | ⛔ (LTS) | ⛔ |
| **Idea central** | Reescritura ligera | Completar huecos | Modelado rico | Productividad | Datos espaciales |

> [!NOTE]
> Los ejemplos de este capítulo **se compilan y ejecutan con EF Core 10**: las piezas de 2016–2018 siguen vigentes. Cuando una API cambió de nombre o
> desapareció, el capítulo lo indica y muestra la forma moderna.

---

## Contenido

1. [El punto de partida](#1-el-punto-de-partida)
2. [EF Core 1.0: junio de 2016](#2-ef-core-10-junio-de-2016)
3. [EF Core 1.1: noviembre de 2016](#3-ef-core-11-noviembre-de-2016)
4. [EF Core 2.0: agosto de 2017](#4-ef-core-20-agosto-de-2017)
5. [EF Core 2.1: mayo de 2018](#5-ef-core-21-mayo-de-2018)
6. [EF Core 2.2: diciembre de 2018](#6-ef-core-22-diciembre-de-2018)
7. [La deuda que heredó EF Core 3](#7-la-deuda-que-heredó-ef-core-3)
8. [Referencias](#8-referencias)

---

## 1. El punto de partida

EF Core 1.0 nació con un objetivo explícito: **ser pequeño, rápido y multiplataforma antes que completo**. El equipo publicó una tabla de "lo que falta
respecto a EF6" y fue tachando filas versión a versión.

| Capacidad de EF6 | EF Core 1.0 | Llegó en |
|---|---|---|
| Carga diferida | ❌ | 2.1 |
| `GroupBy` en el servidor | ❌ (en memoria) | 2.1 |
| Muchos a muchos sin entidad intermedia | ❌ | 5.0 |
| Herencia TPT | ❌ | 5.0 |
| Herencia TPC | ❌ | 7.0 |
| Tipos complejos | ❌ | 2.0 (tipos propios) y 8.0 (tipos complejos) |
| Procedimientos almacenados para CUD | ❌ | 7.0 |
| Datos espaciales | ❌ | 2.2 |
| Siembra de datos | ❌ | 2.1 |
| Interceptores | ❌ | 3.0 |

---

## 2. EF Core 1.0: junio de 2016

### Lo que trajo

| Pieza | Descripción |
|---|---|
| `DbContext`, `DbSet<T>` | La misma API que EF 4.1+, sin `ObjectContext` |
| Convenciones, anotaciones y API fluida | El sistema de modelado de tres capas del [capítulo 02](02-anatomia-de-ef-core.md#3-el-modelo-la-fuente-de-verdad) |
| **Propiedades de sombra** | Columnas que existen en el modelo pero no en la clase |
| **Claves alternativas** | Restricciones `UNIQUE` que pueden ser destino de claves foráneas |
| Migraciones en código | `Up`/`Down` en C#, sin el `__MigrationHistory` binario de EF6 |
| `Include`/`ThenInclude` | Carga ansiosa, con `ThenInclude` para varios niveles |
| `FromSql` | SQL propio componible con LINQ |
| Lotes en `SaveChanges` | Varias sentencias en un viaje: la gran mejora de rendimiento frente a EF6 |
| Proveedores | SQL Server, SQLite, InMemory; la comunidad añadió PostgreSQL y MySQL |
| `dotnet ef` | Migraciones y *scaffolding* desde la línea de comandos |

### Propiedades de sombra y claves alternativas

Una **propiedad de sombra** vive en el modelo y en la tabla, pero no en tu clase. Es útil para metadatos de infraestructura (fechas de auditoría,
claves foráneas que el dominio no necesita ver).

```csharp run
using var db = new Blog();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

var entrada = new Entrada { Titulo = "Hola, EF Core", Slug = "hola-ef-core" };
db.Add(entrada);
db.Entry(entrada).Property("CreadaEn").CurrentValue = new DateTime(2016, 6, 27);
db.SaveChanges();

var fecha = db.Entradas
    .Where(e => e.Slug == "hola-ef-core")
    .Select(e => EF.Property<DateTime>(e, "CreadaEn"))
    .Single();
Console.WriteLine(fecha.ToString("yyyy-MM-dd"));        // → 2016-06-27

var columnas = db.Model.FindEntityType(typeof(Entrada))!.GetProperties().Select(p => p.Name);
Console.WriteLine(string.Join(", ", columnas));        // → Id, CreadaEn, Slug, Titulo

public class Entrada
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public required string Slug { get; set; }
}

public class Blog : DbContext
{
    public DbSet<Entrada> Entradas => Set<Entrada>();

    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=blog.db");

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Entrada>().Property<DateTime>("CreadaEn");     // propiedad de sombra
        b.Entity<Entrada>().HasAlternateKey(e => e.Slug);       // UNIQUE, puede ser destino de una FK
    }
}
```

> [!TIP]
> Las **claves foráneas de sombra** son las más comunes sin que lo notes: si una entidad tiene una navegación `Cliente` pero no una propiedad
> `ClienteId`, EF crea `ClienteId` como propiedad de sombra.

### Lo que todavía no funcionaba bien

EF Core 1.x y 2.x tenían **evaluación mixta**: cuando no podían traducir parte de una consulta, la ejecutaban en memoria **sin avisar**
(solo con una advertencia en el registro). Un `Where` con un método propio podía descargar la tabla entera. Esa decisión, cómoda al principio,
fue la causa de la gran ruptura de [EF Core 3.0](04-ef-core-3-la-gran-ruptura.md#2-el-fin-de-la-evaluación-implícita-en-cliente).

---

## 3. EF Core 1.1: noviembre de 2016

| Novedad | Para qué |
|---|---|
| `DbSet<T>.Find` | Buscar por clave **mirando primero en el *change tracker*** |
| **Carga explícita** | `Entry(x).Reference(...).Load()` y `Collection(...).Load()` |
| **Campos de respaldo** | Mapear campos privados: encapsulación al estilo DDD |
| Resiliencia de conexión | `EnableRetryOnFailure()` para errores transitorios de Azure SQL |
| Tablas optimizadas en memoria | `IsMemoryOptimized()` para In-Memory OLTP de SQL Server |
| `Reload`, `GetDatabaseValues` | Releer el estado de la base |

### Campos de respaldo y carga explícita

Con un **campo de respaldo**, la colección pública es de solo lectura y solo el agregado puede modificarla. EF lee y escribe el campo privado.

```csharp run
using var db = new Escuela();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

var curso = new Curso("EF Core desde cero");
curso.Inscribir("Ana");
curso.Inscribir("Luis");
db.Add(curso);
db.SaveChanges();
db.ChangeTracker.Clear();

var cargado = db.Cursos.Find(curso.Id)!;
// La colección no se cargó: Find solo trae el curso
Console.WriteLine(cargado.Alumnos.Count);                      // → 0

db.Entry(cargado).Collection(c => c.Alumnos).Load();           // carga explícita
Console.WriteLine(cargado.Alumnos.Count);                      // → 2
// Find encuentra el curso en el change tracker y no va a la base
Console.WriteLine(db.Cursos.Find(curso.Id) == cargado);        // → True

public class Curso
{
    private readonly List<Alumno> _alumnos = [];
    private Curso() { Titulo = ""; }                           // para EF
    public Curso(string titulo) => Titulo = titulo;

    public int Id { get; private set; }
    public string Titulo { get; private set; }
    public IReadOnlyCollection<Alumno> Alumnos => _alumnos;    // EF usa el campo _alumnos

    public void Inscribir(string nombre) => _alumnos.Add(new Alumno { Nombre = nombre });
}

public class Alumno
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
}

public class Escuela : DbContext
{
    public DbSet<Curso> Cursos => Set<Curso>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=escuela.db");
}
```

> [!NOTE]
> EF descubre el campo `_alumnos` **por convención** (mismo nombre con guion bajo, `m_` o en minúscula). Si el nombre no sigue la convención,
> configúralo con `HasField("nombre")` o con `[BackingField]`.

---

## 4. EF Core 2.0: agosto de 2017

EF Core 2.0 llegó con .NET Standard 2.0, que abrió la puerta a .NET Framework 4.6.1, y con un salto de **modelado**:

| Novedad | Descripción |
|---|---|
| **Tipos propios** (`OwnsOne`) | Objetos de valor sin identidad propia, en la tabla del dueño |
| División de tablas | Varias entidades en una misma tabla |
| **Filtros de consulta globales** | `HasQueryFilter`: borrado lógico y multitenencia |
| **Agrupación de contextos** | `AddDbContextPool` reutiliza instancias |
| **Consultas compiladas explícitas** | `EF.CompileQuery` |
| SQL interpolado seguro | `FromSql($"... {x}")` convierte cada hueco en parámetro |
| `EF.Functions.Like` | Primera función de la base expuesta en LINQ |
| Funciones escalares mapeadas | `HasDbFunction` |
| `IEntityTypeConfiguration<T>` | Configuración por entidad en clases separadas |

### Filtros globales: borrado lógico

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.AddRange(new Producto { Nombre = "Activo" }, new Producto { Nombre = "Retirado", Eliminado = true });
db.SaveChanges();

Console.WriteLine(db.Productos.Count());                        // → 1
Console.WriteLine(db.Productos.IgnoreQueryFilters().Count());   // → 2

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public bool Eliminado { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Producto>().HasQueryFilter(p => !p.Eliminado);
}
```

> [!IMPORTANT]
> Durante ocho años solo pudo haber **un filtro por entidad**: un segundo `HasQueryFilter` reemplazaba al primero, y `IgnoreQueryFilters()` los
> desactivaba todos. **EF Core 10** introdujo los [filtros con nombre](10-ef-core-10-lts-vectores-y-json.md#6-filtros-de-consulta-con-nombre).

### Tipos propios

```csharp run
using var db = new Crm();
Console.WriteLine(db.Database.GenerateCreateScript().Trim());
// → CREATE TABLE "Clientes" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_Clientes" PRIMARY KEY AUTOINCREMENT,
// →     "Nombre" TEXT NOT NULL,
// →     "Direccion_Calle" TEXT NOT NULL,
// →     "Direccion_Ciudad" TEXT NOT NULL
// → );

public class Cliente
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public required Direccion Direccion { get; set; }
}

public class Direccion
{
    public required string Calle { get; set; }
    public required string Ciudad { get; set; }
}

public class Crm : DbContext
{
    public DbSet<Cliente> Clientes => Set<Cliente>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=crm.db");
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Cliente>().OwnsOne(c => c.Direccion);
        b.Entity<Cliente>().Navigation(c => c.Direccion).IsRequired();
    }
}
```

`GenerateCreateScript()` imprime el DDL que EF ejecutaría: es la forma más rápida de comprobar un mapeo. Los tipos propios **son entidades por dentro**
(tienen una clave de sombra) y eso trae limitaciones que en 2023 resolvieron los [tipos complejos](08-ef-core-8-tipos-complejos.md#2-tipos-complejos).

### Consultas compiladas

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.AddRange(new Producto { Nombre = "A", Stock = 1 }, new Producto { Nombre = "B", Stock = 8 });
db.SaveChanges();

foreach (var p in Consultas.ConStock(db, 5))
    Console.WriteLine(p.Nombre);                                // → B

public static class Consultas
{
    // Se compila una sola vez: evita la búsqueda en la caché y el análisis del árbol en cada llamada
    public static readonly Func<Tienda, int, IEnumerable<Producto>> ConStock =
        EF.CompileQuery((Tienda db, int minimo) => db.Productos.Where(p => p.Stock >= minimo));
}

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public int Stock { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

### `FromSql` en 2017 y hoy

```csharp omitir
// EF Core 2.0: un único FromSql aceptaba texto o cadena interpolada (y era fácil equivocarse)
var r = db.Productos.FromSql($"SELECT * FROM Productos WHERE Nombre = {nombre}");
```

| Versión | API | Seguridad |
|---|---|---|
| 2.x | `FromSql(string)` y `FromSql(FormattableString)` sobrecargados | Ambiguo: una variable `string` interpolada antes perdía la parametrización |
| 3.0–6.0 | `FromSqlRaw(string, params object[])` y `FromSqlInterpolated(FormattableString)` | Explícito |
| 7.0+ | `FromSql(FormattableString)` vuelve, solo interpolado | Seguro por diseño; `FromSqlRaw` para SQL dinámico |
| 10 | Analizador que avisa si concatenas dentro de `FromSqlRaw` | [Capítulo 10](10-ef-core-10-lts-vectores-y-json.md#9-seguridad-registros-y-sql-crudo) |

---

## 5. EF Core 2.1: mayo de 2018

La versión que convirtió EF Core en una opción seria para equipos que venían de EF6, y la primera **LTS**:

| Novedad | Descripción |
|---|---|
| **Carga diferida** | Con proxies (`UseLazyLoadingProxies`) o inyectando `ILazyLoader` |
| **Conversiones de valores** | `HasConversion`: enums como texto, tipos propios, cifrado |
| **Siembra de datos** | `HasData`: datos de referencia que viajan con las migraciones |
| Tipos de consulta | `DbQuery<T>` para vistas sin clave (en 3.0 pasaron a ser entidades sin clave) |
| Constructores con parámetros | EF puede usar tu constructor al materializar |
| Eventos `Tracked` y `StateChanged` | Reaccionar a cambios del *change tracker* |
| `System.Transactions` | `TransactionScope` con los proveedores que lo admiten |
| `GroupBy` traducido | `GROUP BY` con agregados en el servidor |
| Subconsultas correlacionadas optimizadas | Resolvió el N+1 de las proyecciones de colecciones |

### Conversiones de valores

```csharp run
using var db = new Ventas();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Add(new Pedido { Estado = EstadoPedido.Enviado });
db.SaveChanges();

var guardado = db.Database.SqlQuery<string>($"SELECT Estado AS Value FROM Pedidos").Single();
Console.WriteLine(guardado);                                         // → Enviado

var enviados = db.Pedidos.Count(p => p.Estado == EstadoPedido.Enviado);
Console.WriteLine(enviados);                                         // → 1

public enum EstadoPedido { Pendiente, Enviado, Entregado }

public class Pedido
{
    public int Id { get; set; }
    public EstadoPedido Estado { get; set; }
}

public class Ventas : DbContext
{
    public DbSet<Pedido> Pedidos => Set<Pedido>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=ventas.db");
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Pedido>().Property(p => p.Estado).HasConversion<string>();
}
```

> [!TIP]
> Guardar enums **como texto** cuesta unos bytes más, pero hace la base legible y **sobrevive a reordenar el enum**. Guardarlos como entero
> (la opción por defecto) es más compacto pero frágil: insertar un valor en medio cambia el significado de todas las filas existentes. El proyecto de este
> repositorio guarda `Priority` como `int`; ver [capítulo 20](20-caso-practico-jobsdb.md).

### Siembra con `HasData`

`HasData` describe datos **en el modelo**. Las migraciones calculan la diferencia y generan `InsertData`, `UpdateData` y `DeleteData`. Es exactamente lo que
hacen las migraciones `_03` y `_06` de este repositorio.

```csharp run
using var db = new Catalogo();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();                   // también aplica HasData

foreach (var c in db.Categorias.OrderBy(c => c.Id))
    Console.WriteLine($"{c.Id} {c.Nombre}");
// → 1 Pendiente
// → 2 Personal

public class Categoria
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
}

public class Catalogo : DbContext
{
    public DbSet<Categoria> Categorias => Set<Categoria>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=catalogo.db");
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Categoria>().HasData(
            new Categoria { Id = 1, Nombre = "Pendiente" },
            new Categoria { Id = 2, Nombre = "Personal" });
}
```

| Regla de `HasData` | Por qué |
|---|---|
| Hay que dar **la clave explícitamente**, aunque sea autogenerada | La migración necesita saber qué fila actualizar o borrar |
| Los valores deben ser **deterministas** | `DateTime.Now` o `Guid.NewGuid()` generan una migración nueva cada vez |
| No sirve para datos de prueba masivos ni dependientes del entorno | Para eso, `UseSeeding` ([EF Core 9](09-ef-core-9-cosmos-aot-y-siembra.md#5-siembra-con-useseeding)) |

### Carga diferida

```csharp run
using var db = new Blog();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
var autor = new Autor { Nombre = "Rowan" };
autor.Entradas.Add(new Entrada { Titulo = "Lazy loading" });
db.Add(autor);
db.SaveChanges();
db.ChangeTracker.Clear();

var a = db.Autores.Single();
Console.WriteLine(a.GetType().Namespace);     // → Castle.Proxies
// Tocar la navegación ejecuta aquí una segunda consulta
Console.WriteLine(a.Entradas.Count);          // → 1

public class Autor
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public virtual ICollection<Entrada> Entradas { get; set; } = new List<Entrada>();
}

public class Entrada
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public virtual Autor? Autor { get; set; }
}

public class Blog : DbContext
{
    public DbSet<Autor> Autores => Set<Autor>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlite("Data Source=blog.db").UseLazyLoadingProxies();
}
```

> [!CAUTION]
> La carga diferida es **cómoda y peligrosa**: un bucle `foreach (var a in autores) Console.WriteLine(a.Entradas.Count)` lanza **una consulta por autor**
> (el problema N+1). Y si el contexto ya se desechó cuando se toca la navegación, lanza una excepción. Úsala con conciencia; el
> [capítulo 13](13-consultas.md#4-estrategias-de-carga-de-datos-relacionados) compara las cuatro estrategias de carga.

---

## 6. EF Core 2.2: diciembre de 2018

| Novedad | Descripción |
|---|---|
| **Datos espaciales** | `NetTopologySuite`: `Point`, `Polygon`… traducidos a `geography`/`geometry` en SQL Server, PostGIS en PostgreSQL y SpatiaLite |
| **Colecciones de tipos propios** | `OwnsMany` |
| **Etiquetas de consulta** | `TagWith("...")` añade un comentario al SQL |

### `TagWith`: encontrar el origen de una consulta lenta

Cuando un DBA te enseña una consulta lenta en el monitor del servidor, `TagWith` te dice de qué línea de código vino:

```csharp run
using var db = new Tienda();
var sql = db.Productos
    .TagWith("Listado de la portada · ProductosController.Index")
    .Where(p => p.Stock > 0)
    .ToQueryString();
Console.WriteLine(sql);
// → -- Listado de la portada · ProductosController.Index
// →
// → SELECT "p"."Id", "p"."Nombre", "p"."Stock"
// → FROM "Productos" AS "p"
// → WHERE "p"."Stock" > 0

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public int Stock { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

> [!TIP]
> `TagWithCallSite()` (EF Core 6) añade automáticamente **archivo y línea** del llamador.

---

## 7. La deuda que heredó EF Core 3

A finales de 2018, EF Core era productivo pero tenía tres problemas estructurales que no se podían arreglar sin romper código:

| Problema | Síntoma | Solución en 3.0 |
|---|---|---|
| Evaluación en cliente silenciosa | Consultas que descargaban tablas enteras sin avisar | Excepción si algo no se traduce |
| Canalización LINQ basada en *re-linq* | Traducciones frágiles, una consulta LINQ podía generar N sentencias SQL | Canalización nueva, una sentencia por consulta |
| `DbQuery<T>` separado de `DbSet<T>` | Dos conceptos para casi lo mismo | Entidades sin clave (`HasNoKey`) |

---

## 8. Referencias

- [Announcing Entity Framework Core 1.0](https://devblogs.microsoft.com/dotnet/entity-framework-core-1-0-0-available/)
- [Announcing EF Core 2.0](https://devblogs.microsoft.com/dotnet/announcing-entity-framework-core-2-0/),
  [2.1](https://devblogs.microsoft.com/dotnet/announcing-entity-framework-core-2-1/),
  [2.2](https://devblogs.microsoft.com/dotnet/announcing-entity-framework-core-2-2/)
- [Shadow properties](https://learn.microsoft.com/ef/core/modeling/shadow-properties) ·
  [Backing fields](https://learn.microsoft.com/ef/core/modeling/backing-field) ·
  [Owned entity types](https://learn.microsoft.com/ef/core/modeling/owned-entities)
- [Value conversions](https://learn.microsoft.com/ef/core/modeling/value-conversions) ·
  [Data seeding](https://learn.microsoft.com/ef/core/modeling/data-seeding) ·
  [Lazy loading](https://learn.microsoft.com/ef/core/querying/related-data/lazy)

<div align="center">

[⬅ 02 · Anatomía](02-anatomia-de-ef-core.md) · [🏠 Índice](../README.md) · [04 · EF Core 3 ➡](04-ef-core-3-la-gran-ruptura.md)

</div>
