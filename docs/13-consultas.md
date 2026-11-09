<div align="center">

# 13 · Consultas

**LINQ que se convierte en SQL: ejecución diferida, proyecciones, carga de relaciones, seguimiento, paginación, SQL crudo y el problema N+1**

[⬅ 12 · Modelado](12-modelado.md) · [🏠 Índice](../README.md) · [14 · Guardado y concurrencia ➡](14-guardado-y-concurrencia.md)

</div>

<!-- ef=10 -->

---

## Contenido

1. [`IQueryable` y la ejecución diferida](#1-iqueryable-y-la-ejecución-diferida)
2. [Qué se traduce y qué no](#2-qué-se-traduce-y-qué-no)
3. [Proyecciones: pide solo lo que usas](#3-proyecciones-pide-solo-lo-que-usas)
4. [Estrategias de carga de datos relacionados](#4-estrategias-de-carga-de-datos-relacionados)
5. [Seguimiento o no](#5-seguimiento-o-no)
6. [Paginación](#6-paginación)
7. [Agrupación y agregados](#7-agrupación-y-agregados)
8. [SQL crudo](#8-sql-crudo)
9. [Funciones de base de datos](#9-funciones-de-base-de-datos)
10. [Consultas compiladas](#10-consultas-compiladas)
11. [Antipatrones](#11-antipatrones)
12. [Referencias](#12-referencias)

---

## 1. `IQueryable` y la ejecución diferida

Un `DbSet<T>` es un `IQueryable<T>`. Cada operador LINQ (`Where`, `OrderBy`, `Select`) **no ejecuta nada**: añade un nodo a un árbol de expresión. La
consulta viaja a la base solo cuando la **enumeras**:

| Provoca la ejecución | No la provoca |
|---|---|
| `ToList()`, `ToArray()`, `ToDictionary()` y sus versiones `Async` | `Where`, `Select`, `OrderBy`, `Include`, `Skip`, `Take` |
| `First()`, `Single()`, `Any()`, `Count()`, `Sum()`, `Max()`… | `AsNoTracking()`, `TagWith()` |
| `foreach` / `await foreach` | Asignar el `IQueryable` a una variable |
| `Find()` (si no está ya en memoria) | `ToQueryString()` (solo genera el SQL) |

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Productos.AddRange(new Producto { Nombre = "Té", Precio = 3 }, new Producto { Nombre = "Café", Precio = 5 });
db.SaveChanges();

IQueryable<Producto> q = db.Productos.Where(p => p.Precio > 2);   // nada se ejecuta todavía
q = q.OrderBy(p => p.Nombre);                                      // la consulta se compone
Console.WriteLine(q.ToQueryString());
// → SELECT "p"."Id", "p"."Nombre", "p"."Precio"
// → FROM "Productos" AS "p"
// → WHERE "p"."Precio" > 2
// → ORDER BY "p"."Nombre"
Console.WriteLine(string.Join(", ", q.Select(p => p.Nombre)));   // → Café, Té

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public int Precio { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

> [!IMPORTANT]
> **`IQueryable` frente a `IEnumerable`.** Si un método de tu repositorio devuelve `IEnumerable<Producto>`, todo `Where` que se añada después se
> ejecuta **en memoria**, tras traer la tabla entera. El tipo de la variable decide dónde se evalúa la consulta. Compón siempre sobre `IQueryable` y
> materializa al final.

> [!TIP]
> `ToQueryString()` y `TagWith("…")` son tus mejores herramientas de depuración: el primero te enseña el SQL sin ejecutarlo; el segundo añade un
> comentario `-- …` al SQL para encontrar la consulta en el *profiler* o en Query Store ([capítulo 17](17-rendimiento-y-diagnostico.md)).

---

## 2. Qué se traduce y qué no

Desde EF Core 3.0 ([capítulo 04](04-ef-core-3-la-gran-ruptura.md)), **una consulta que no se puede traducir lanza una excepción** en lugar de evaluarse
en el cliente en silencio. La única excepción es la **proyección final**: el último `Select` puede llamar a cualquier método de C#.

```csharp run lanza=InvalidOperationException
using var db = new Tienda();
db.Database.EnsureCreated();

// ✅ Válido: el método de C# está en la proyección final
var etiquetas = db.Productos.Select(p => Util.Formatear(p.Nombre)).ToList();

// ❌ InvalidOperationException: "The LINQ expression … could not be translated"
var caros = db.Productos.Where(p => Util.EsCaro(p.Precio)).ToList();

public static class Util
{
    public static string Formatear(string s) => s.ToUpperInvariant();
    public static bool EsCaro(int precio) => precio > 4;
}

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public int Precio { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

| Se traduce (en los proveedores principales) | No se traduce |
|---|---|
| Operadores de comparación, aritméticos y lógicos | Métodos propios de C# en `Where`/`OrderBy` |
| `string.Contains`, `StartsWith`, `EndsWith`, `ToUpper`, `Trim`, `Length`, `Substring`, `IndexOf` | `string.Format`, `Regex` (salvo en algunos proveedores) |
| `Math.Abs`, `Round`, `Max`, `Min`, `Floor`, `Ceiling`, `Pow` | Constructores de tipos propios con lógica |
| `DateTime.Year`/`Month`/`AddDays`, `DateOnly`, `TimeOnly` | `DateTime.ToString("formato")` |
| `Contains` sobre listas en memoria (`IN`) | Llamadas a servicios |
| Navegaciones (`p.Categoria.Nombre` → `JOIN`) | Propiedades `[NotMapped]` o ignoradas |
| `EF.Functions.Like`, `DateDiffDay`, `Collate`… | Expresiones de *pattern matching* complejas |

> [!TIP]
> Si necesitas una lógica que no se traduce, tienes tres caminos: **reescribirla** con operadores traducibles, **mapear una función de base de datos**
> ([sección 9](#9-funciones-de-base-de-datos)), o **traer los datos mínimos** y terminar en memoria con un `AsEnumerable()` explícito y consciente.

---

## 3. Proyecciones: pide solo lo que usas

Cargar entidades completas cuando solo vas a mostrar dos campos es el desperdicio más común en EF Core. Una proyección con `Select`:

- trae **solo las columnas** que nombras (menos red, menos memoria, índices de cobertura posibles),
- **no se sigue** en el *change tracker* (no hace falta `AsNoTracking`),
- genera los `JOIN` necesarios sin `Include`.

```csharp run
using var db = new Blog();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Add(new Autor { Nombre = "Ana", Entradas = [new() { Titulo = "EF Core", Cuerpo = new string('x', 10_000) }] });
db.SaveChanges();
db.ChangeTracker.Clear();                            // olvidamos lo insertado para medir solo la consulta

var resumen = db.Entradas
    .Select(e => new ResumenEntrada(e.Titulo, e.Autor.Nombre, e.Cuerpo.Length))
    .ToList();
Console.WriteLine(resumen[0]);                       // → ResumenEntrada { Titulo = EF Core, Autor = Ana, Longitud = 10000 }
Console.WriteLine(db.ChangeTracker.Entries().Count()); // → 0

public record ResumenEntrada(string Titulo, string Autor, int Longitud);

public class Autor
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public List<Entrada> Entradas { get; set; } = [];
}

public class Entrada
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public required string Cuerpo { get; set; }
    public Autor Autor { get; set; } = null!;
}

public class Blog : DbContext
{
    public DbSet<Entrada> Entradas => Set<Entrada>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=blog.db");
}
```

> [!NOTE]
> El cuerpo de 10 000 caracteres **nunca viaja** por la red: `e.Cuerpo.Length` se traduce a `length("e"."Cuerpo")` y se calcula en la base.

---

## 4. Estrategias de carga de datos relacionados

| Estrategia | Cómo | Consultas | Cuándo |
|---|---|---|---|
| **Proyección** | `Select(x => new { x.A, x.Hijos.Count })` | 1 | Lecturas para mostrar: la opción por defecto |
| **Carga ansiosa** (*eager*) | `Include(x => x.Hijos).ThenInclude(…)` | 1 (o N con *split*) | Necesitas las entidades para modificarlas |
| **Include filtrado** | `Include(x => x.Hijos.Where(h => h.Activo).OrderBy(…).Take(5))` | 1 | Solo una parte de la colección (EF Core 5+) |
| **Consulta dividida** | `AsSplitQuery()` | 1 + una por colección | Varias colecciones grandes en un `Include` |
| **Carga explícita** | `Entry(x).Collection(c => c.Hijos).LoadAsync()` | 1 más, cuando la pides | Decidir en tiempo de ejecución |
| **Carga diferida** (*lazy*) | Proxies + navegaciones `virtual` | 1 más **por cada acceso** | Rara vez en la web: riesgo de N+1 |

### Explosión cartesiana y consultas divididas

Un `Include` de **dos colecciones hermanas** en una sola consulta produce un `JOIN` cuyo número de filas es el **producto** de ambas: un blog con 100
entradas y 50 colaboradores devuelve 5 000 filas para 150 datos útiles. `AsSplitQuery()` lo resuelve con una consulta por colección:

```csharp run
using var db = new Contenido();
var unica = db.Blogs.Include(b => b.Entradas).Include(b => b.Colaboradores);
var dividida = unica.AsSplitQuery();

Console.WriteLine(unica.ToQueryString().Split("LEFT JOIN").Length - 1);          // → 2
Console.WriteLine(dividida.ToQueryString().Contains("LEFT JOIN"));             // → False

public class Blog
{
    public int Id { get; set; }
    public List<Entrada> Entradas { get; set; } = [];
    public List<Colaborador> Colaboradores { get; set; } = [];
}
public class Entrada { public int Id { get; set; } public int BlogId { get; set; } }
public class Colaborador { public int Id { get; set; } public int BlogId { get; set; } }

public class Contenido : DbContext
{
    public DbSet<Blog> Blogs => Set<Blog>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=blogs.db");
}
```

| | Consulta única | Consulta dividida |
|---|---|---|
| Viajes a la base | 1 | 1 + colecciones |
| Datos duplicados | Sí (producto cartesiano) | No |
| Coherencia | Instantánea | Puede variar entre consultas (EF Core 11 lo detecta) |
| Paginación con `Skip`/`Take` | Correcta | Exige un `OrderBy` **único** |
| Configurable por defecto | — | `UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery)` |

> [!WARNING]
> **Carga diferida en una API web = N+1.** Si serializas una lista de 100 trabajos y cada uno tiene una navegación `virtual` a su categoría, el
> serializador la toca y EF lanza **100 consultas adicionales**. En el proyecto de este repositorio las navegaciones son `virtual`, pero sin proxies no
> hay carga diferida: el `virtual` sobra ([capítulo 20](20-caso-practico-jobsdb.md)).

---

## 5. Seguimiento o no

Por defecto, cada entidad que devuelve una consulta queda **registrada** en el *change tracker* ([capítulo 02](02-anatomia-de-ef-core.md#7-el-change-tracker)):
EF guarda una instantánea de sus valores originales para detectar cambios en `SaveChanges`. Eso tiene un coste en memoria y CPU que no necesitas si solo
vas a leer.

| Modo | Instantánea | Resolución de identidad | Úsalo para |
|---|---|---|---|
| `AsTracking()` (por defecto) | ✅ | ✅ | Leer para **modificar** y guardar |
| `AsNoTracking()` | ❌ | ❌ (dos filas iguales → dos objetos) | Lecturas puras: el caso más común en una API |
| `AsNoTrackingWithIdentityResolution()` | ❌ | ✅ | Lecturas con grafos que repiten entidades |
| Proyección a DTO | ❌ | — | Lecturas para mostrar |

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Productos.Add(new Producto { Nombre = "Té" });
db.SaveChanges();
db.ChangeTracker.Clear();

var a = db.Productos.AsNoTracking().Single();
var b = db.Productos.AsNoTracking().Single();
Console.WriteLine(ReferenceEquals(a, b));                    // → False
Console.WriteLine(db.ChangeTracker.Entries().Count());      // → 0

var c = db.Productos.Single();
var d = db.Productos.Single();
Console.WriteLine(ReferenceEquals(c, d));                    // → True
Console.WriteLine(db.ChangeTracker.Entries().Count());      // → 1

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

> [!TIP]
> En un contexto que solo lee (un servicio de informes, un *read model* en CQRS), configura `UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)`
> en las opciones y olvídate de llamar a `AsNoTracking()` en cada consulta.

---

## 6. Paginación

| Técnica | SQL | Coste en la página 10 000 | Estable si se insertan filas |
|---|---|---|---|
| **Desplazamiento** `Skip(n).Take(k)` | `OFFSET n ROWS FETCH NEXT k` | La base lee y descarta `n` filas | ❌ filas repetidas o saltadas |
| **Conjunto de claves** (*keyset*) `Where(x => x.Id > ultimo).Take(k)` | `WHERE Id > @ultimo` | Busca en el índice: constante | ✅ |

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Productos.AddRange(Enumerable.Range(1, 10).Select(i => new Producto { Nombre = $"P{i:00}" }));
db.SaveChanges();

int? ultimo = null;
for (var pagina = 1; pagina <= 3; pagina++)
{
    var filas = db.Productos
        .Where(p => ultimo == null || p.Id > ultimo)
        .OrderBy(p => p.Id)
        .Take(4)
        .ToList();
    Console.WriteLine($"Página {pagina}: {string.Join(" ", filas.Select(p => p.Nombre))}");
    ultimo = filas.LastOrDefault()?.Id;
}
// → Página 1: P01 P02 P03 P04
// → Página 2: P05 P06 P07 P08
// → Página 3: P09 P10

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

> [!IMPORTANT]
> Toda paginación necesita un **`OrderBy` determinista**: si ordenas por `Fecha` y dos filas comparten fecha, añade `ThenBy(x => x.Id)`. Sin orden,
> SQL no garantiza nada, y EF Core emite una advertencia cuando usas `Skip`/`Take` sin `OrderBy`.

---

## 7. Agrupación y agregados

```csharp run
using var db = new Ventas();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Lineas.AddRange(
    new Linea { Pais = "MX", Importe = 10 }, new Linea { Pais = "MX", Importe = 30 },
    new Linea { Pais = "ES", Importe = 25 });
db.SaveChanges();

var porPais = db.Lineas
    .GroupBy(l => l.Pais)
    .Select(g => new { Pais = g.Key, Total = g.Sum(l => l.Importe), Pedidos = g.Count() })
    .OrderByDescending(x => x.Total)
    .ToList();
foreach (var x in porPais) Console.WriteLine($"{x.Pais}: {x.Total} en {x.Pedidos}");
// → MX: 40 en 2
// → ES: 25 en 1

public class Linea
{
    public int Id { get; set; }
    public required string Pais { get; set; }
    public int Importe { get; set; }
}

public class Ventas : DbContext
{
    public DbSet<Linea> Lineas => Set<Linea>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=ventas.db");
}
```

| Patrón | Traducción |
|---|---|
| `GroupBy(k).Select(g => new { g.Key, g.Count() })` | `GROUP BY` + agregado |
| `GroupBy(...).Where(g => g.Count() > 1)` | `HAVING` |
| `GroupBy(...).Select(g => g.OrderBy(...).First())` | Función de ventana `ROW_NUMBER()` (EF Core 6+) |
| `GroupBy(...).ToList()` sin agregado | Se trae todo y se agrupa en memoria (**evítalo**) |
| `string.Join(", ", g.Select(...))` | `STRING_AGG` / `group_concat` (EF Core 7+) |

---

## 8. SQL crudo

Cuando LINQ no basta (una consulta muy optimizada, una función propia del motor, un `WITH` recursivo), EF Core ofrece SQL directo **sin renunciar a la
parametrización**:

| API | Devuelve | Desde |
|---|---|---|
| `DbSet<T>.FromSql($"…")` | Entidades `T`, componible con LINQ | 7.0 (antes `FromSqlInterpolated`) |
| `Database.SqlQuery<T>($"…")` | Cualquier tipo, incluso escalares y DTO no mapeados | 7.0 (escalares), 8.0 (tipos) |
| `Database.ExecuteSql($"…")` | Filas afectadas | 7.0 |
| `FromSqlRaw` / `ExecuteSqlRaw` | Igual, con SQL ya construido y parámetros explícitos | 3.0 |

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Productos.AddRange(new Producto { Nombre = "Té", Precio = 3 }, new Producto { Nombre = "Café", Precio = 5 });
db.SaveChanges();

int minimo = 4;
var caros = db.Database
    .SqlQuery<Precio>($"SELECT Nombre, Precio AS Valor FROM Productos WHERE Precio >= {minimo}")
    .ToList();
Console.WriteLine(caros[0]);                                          // → Precio { Nombre = Café, Valor = 5 }

var total = db.Database.SqlQuery<int>($"SELECT SUM(Precio) AS Value FROM Productos").Single();
Console.WriteLine(total);                                             // → 8

var filas = db.Database.ExecuteSql($"UPDATE Productos SET Precio = Precio + 1 WHERE Precio < {minimo}");
Console.WriteLine(filas);                                             // → 1

public record Precio(string Nombre, int Valor);

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public int Precio { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

> [!NOTE]
> `SqlQuery<int>` exige que la columna se llame **`Value`**, porque EF envuelve tu SQL en una subconsulta para poder componer más LINQ encima.

---

## 9. Funciones de base de datos

| Función | Ejemplo | Traducción |
|---|---|---|
| `EF.Functions.Like` | `Like(p.Nombre, "caf%")` | `LIKE` |
| `EF.Functions.Collate` | `Collate(p.Nombre, "Latin1_General_CI_AI")` | `COLLATE` (búsqueda sin acentos) |
| `EF.Functions.DateDiffDay` | `DateDiffDay(p.Alta, DateTime.UtcNow)` | `DATEDIFF(day, …)` |
| `EF.Functions.Contains` / `FreeText` | Búsqueda de texto completo | `CONTAINS` / `FREETEXT` |
| `EF.Functions.VectorDistance` | Búsqueda semántica | `VECTOR_DISTANCE` ([capítulo 10](10-ef-core-10-lts-vectores-y-json.md)) |
| `EF.Property<T>(e, "Sombra")` | Propiedades sombra | La columna |
| **Función propia** | `[DbFunction]` o `HasDbFunction` | Tu función escalar o de tabla |

```csharp
public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public decimal Precio { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlServer("Server=.;Database=Tienda;Trusted_Connection=True;TrustServerCertificate=True");

    // Se traduce a dbo.PrecioConIva(…); nunca se ejecuta en C#
    [DbFunction("PrecioConIva", "dbo")]
    public static decimal PrecioConIva(decimal precio) => throw new NotSupportedException();

    public IQueryable<Producto> Asequibles() => Productos.Where(p => PrecioConIva(p.Precio) < 100);
}
```

---

## 10. Consultas compiladas

Cada consulta LINQ se traduce **una vez** y se guarda en una caché indexada por la forma del árbol de expresión ([capítulo 02](02-anatomia-de-ef-core.md#la-caché-de-consultas-compiladas)).
Aun así, en cada ejecución EF debe recorrer el árbol para calcular la clave de caché. `EF.CompileQuery` se salta ese paso:

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Productos.Add(new Producto { Nombre = "Té" });
db.SaveChanges();

Console.WriteLine(Tienda.PorNombre(db, "Té")?.Id);          // → 1

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
}

public class Tienda : DbContext
{
    public static readonly Func<Tienda, string, Producto?> PorNombre =
        EF.CompileQuery((Tienda db, string nombre) => db.Productos.FirstOrDefault(p => p.Nombre == nombre));

    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
}
```

> [!TIP]
> El beneficio es de **microsegundos por consulta**: solo se nota en rutas muy calientes (miles de ejecuciones por segundo). Mide antes con
> BenchmarkDotNet ([capítulo 17](17-rendimiento-y-diagnostico.md)). Para el arranque en frío, lo que ayuda son los **modelos compilados** y las
> **consultas precompiladas** de EF Core 9.

---

## 11. Antipatrones

| Antipatrón | Síntoma | Corrección |
|---|---|---|
| **N+1** | 1 consulta para la lista + 1 por elemento | `Include` o, mejor, proyección |
| Traer todo y filtrar en memoria | `ToList().Where(...)` | Filtrar antes de materializar |
| `Count() > 0` | Cuenta todas las filas | `Any()` |
| `Include` para leer un campo | Trae la entidad relacionada entera | `Select(x => x.Relacion.Campo)` |
| Repositorio que devuelve `IEnumerable` | Cada filtro posterior va a memoria | Devolver `IQueryable` o métodos específicos |
| `ToList()` para luego hacer `Count` | Materializa N filas | `CountAsync()` |
| Consultas síncronas en ASP.NET Core | Bloquean hilos del *pool* | `ToListAsync`, `FirstOrDefaultAsync`… |
| `Contains` con miles de elementos | Límite de parámetros (2 100 en SQL Server) | Tabla temporal, `TVP` o modo `Parameter` ([capítulo 10](10-ef-core-10-lts-vectores-y-json.md#5-colecciones-parametrizadas-con-varios-parámetros)) |
| `Skip`/`Take` profundos | Latencia creciente | Paginación por *keyset* |
| Serializar entidades directamente | Ciclos, datos de más, N+1 con *lazy loading* | DTO con proyección |

> [!CAUTION]
> El endpoint `GET /api/jobs` de este repositorio hace `Results.Ok(dbcontext.jobs.Include(p => p.Category))`: devuelve un `IQueryable` **seguido** que
> el serializador enumera de forma **síncrona**, sin paginar y con la entidad completa. El [capítulo 20](20-caso-practico-jobsdb.md) lo reescribe paso a paso.

---

## 12. Referencias

- [Querying data](https://learn.microsoft.com/ef/core/querying/)
- [Loading related data](https://learn.microsoft.com/ef/core/querying/related-data/)
- [Single vs. split queries](https://learn.microsoft.com/ef/core/querying/single-split-queries)
- [Tracking vs. no-tracking queries](https://learn.microsoft.com/ef/core/querying/tracking)
- [Pagination](https://learn.microsoft.com/ef/core/querying/pagination)
- [SQL queries](https://learn.microsoft.com/ef/core/querying/sql-queries)

<div align="center">

[⬅ 12 · Modelado](12-modelado.md) · [🏠 Índice](../README.md) · [14 · Guardado y concurrencia ➡](14-guardado-y-concurrencia.md)

</div>
