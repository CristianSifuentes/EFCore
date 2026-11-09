<div align="center">

# 05 · EF Core 5: relaciones y diagnóstico

**Muchos a muchos implícito, TPT, `Include` filtrado, consultas divididas, `ToQueryString`, `LogTo` e interceptores de `SaveChanges` (2020)**

[⬅ 04 · EF Core 3](04-ef-core-3-la-gran-ruptura.md) · [🏠 Índice](../README.md) · [06 · EF Core 6 ➡](06-ef-core-6-rendimiento-y-temporalidad.md)

</div>

<!-- ef=10 -->

| Ficha | EF Core 5.0 |
|---|---|
| **Publicación** | 10-nov-2020, junto con .NET 5 |
| **Plataforma** | .NET Standard 2.1 (.NET Core 3.1 y .NET 5) |
| **Soporte** | ⛔ 10-may-2022 (STS) |
| **Numeración** | Salta del 3 al 5 para alinearse con .NET 5 ([capítulo 01](01-modelo-de-versiones.md#3-por-qué-no-existe-ef-core-4)) |
| **Idea central** | Cerrar la brecha con EF6 y hacer visible lo que EF hace |

---

## Contenido

1. [Muchos a muchos sin entidad de unión](#1-muchos-a-muchos-sin-entidad-de-unión)
2. [Herencia TPT](#2-herencia-tpt)
3. [`Include` filtrado](#3-include-filtrado)
4. [Consultas divididas](#4-consultas-divididas)
5. [Diagnóstico al alcance de la mano](#5-diagnóstico-al-alcance-de-la-mano)
6. [Interceptores y eventos de `SaveChanges`](#6-interceptores-y-eventos-de-savechanges)
7. [Más novedades de EF Core 5](#7-más-novedades-de-ef-core-5)
8. [Cambios incompatibles](#8-cambios-incompatibles)
9. [Referencias](#9-referencias)

---

## 1. Muchos a muchos sin entidad de unión

Hasta EF Core 5, una relación muchos a muchos **exigía una clase intermedia** (`ArticuloEtiqueta`) y dos relaciones uno a muchos. EF6 la creaba sola;
EF Core 5 recuperó ese comportamiento con **navegaciones de salto** (*skip navigations*):

```csharp run
using var db = new Revista();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

var ef = new Etiqueta { Nombre = "ef-core" };
var net = new Etiqueta { Nombre = "dotnet" };
db.AddRange(
    new Articulo { Titulo = "Muchos a muchos", Etiquetas = { ef, net } },
    new Articulo { Titulo = "Novedades de .NET 5", Etiquetas = { net } });
db.SaveChanges();

var conNet = db.Etiquetas.Where(e => e.Nombre == "dotnet").Select(e => e.Articulos.Count).Single();
Console.WriteLine(conNet);                                                        // → 2

var tabla = db.Model.FindEntityType("ArticuloEtiqueta")!;
Console.WriteLine(tabla.GetTableName());                                          // → ArticuloEtiqueta
Console.WriteLine(string.Join(", ", tabla.GetProperties().Select(p => p.Name)));  // → ArticulosId, EtiquetasId

public class Articulo
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public List<Etiqueta> Etiquetas { get; } = [];
}

public class Etiqueta
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public List<Articulo> Articulos { get; } = [];
}

public class Revista : DbContext
{
    public DbSet<Articulo> Articulos => Set<Articulo>();
    public DbSet<Etiqueta> Etiquetas => Set<Etiqueta>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=revista.db");
}
```

La tabla de unión existe en la base de datos y en el modelo, como un **tipo de entidad compartido** de tipo `Dictionary<string, object>`. Si necesitas
datos en la relación (la fecha en que se etiquetó un artículo), configúrala explícitamente:

```csharp
public class Articulo
{
    public int Id { get; set; }
    public List<Etiqueta> Etiquetas { get; } = [];
}

public class Etiqueta
{
    public int Id { get; set; }
    public List<Articulo> Articulos { get; } = [];
}

public class Revista : DbContext
{
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Articulo>()
            .HasMany(a => a.Etiquetas)
            .WithMany(e => e.Articulos)
            .UsingEntity(
                "Etiquetado",
                j => j.Property<DateTime>("EtiquetadoEn").HasDefaultValueSql("CURRENT_TIMESTAMP"));
}
```

---

## 2. Herencia TPT

**Tabla por tipo**: la clase base tiene su tabla con las columnas comunes y cada clase derivada tiene la suya, enlazada por la clave primaria.

```csharp run
using var db = new Pagos();
Console.WriteLine(db.Database.GenerateCreateScript().Trim());
// → CREATE TABLE "Pagos" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_Pagos" PRIMARY KEY,
// →     "Importe" TEXT NOT NULL
// → );
// →
// →
// → CREATE TABLE "PagosConTarjeta" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_PagosConTarjeta" PRIMARY KEY,
// →     "UltimosDigitos" TEXT NOT NULL,
// →     CONSTRAINT "FK_PagosConTarjeta_Pagos_Id" FOREIGN KEY ("Id") REFERENCES "Pagos" ("Id") ON DELETE CASCADE
// → );
// →
// →
// → CREATE TABLE "Transferencias" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_Transferencias" PRIMARY KEY,
// →     "Iban" TEXT NOT NULL,
// →     CONSTRAINT "FK_Transferencias_Pagos_Id" FOREIGN KEY ("Id") REFERENCES "Pagos" ("Id") ON DELETE CASCADE
// → );

public abstract class Pago
{
    public int Id { get; set; }
    public decimal Importe { get; set; }
}

public class PagoConTarjeta : Pago { public required string UltimosDigitos { get; set; } }
public class Transferencia : Pago { public required string Iban { get; set; } }

public class Pagos : DbContext
{
    public DbSet<Pago> Todos => Set<Pago>();
    public DbSet<PagoConTarjeta> ConTarjeta => Set<PagoConTarjeta>();
    public DbSet<Transferencia> Transferencias => Set<Transferencia>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=pagos.db");
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Pago>().UseTptMappingStrategy().ToTable("Pagos");
        b.Entity<PagoConTarjeta>().ToTable("PagosConTarjeta");
        b.Entity<Transferencia>().ToTable("Transferencias");
    }
}
```

> [!NOTE]
> En EF Core 5 se configuraba con `ToTable` en cada tipo derivado; `UseTptMappingStrategy()` llegó en EF Core 7. La comparación de TPH, TPT y TPC, con
> sus costes de consulta, está en el [capítulo 12](12-modelado.md#8-herencia-tph-tpt-y-tpc).

---

## 3. `Include` filtrado

Antes de EF Core 5, `Include` cargaba **la colección entera**. Ahora admite `Where`, `OrderBy`, `Skip` y `Take` dentro:

```csharp run
using var db = new Revista();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
var blog = new Blog { Nombre = "Atlas" };
for (var i = 1; i <= 5; i++) blog.Entradas.Add(new Entrada { Titulo = $"Entrada {i}", Publicada = i % 2 == 1 });
db.Add(blog);
db.SaveChanges();
db.ChangeTracker.Clear();

var conUltimas = db.Blogs
    .Include(b => b.Entradas.Where(e => e.Publicada).OrderByDescending(e => e.Id).Take(2))
    .Single();
Console.WriteLine(string.Join(", ", conUltimas.Entradas.Select(e => e.Titulo)));    // → Entrada 5, Entrada 3

public class Blog
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public List<Entrada> Entradas { get; } = [];
}

public class Entrada
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public bool Publicada { get; set; }
}

public class Revista : DbContext
{
    public DbSet<Blog> Blogs => Set<Blog>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=revista.db");
}
```

> [!WARNING]
> Con seguimiento, el *fix-up* de navegaciones puede **añadir** a la colección entidades que ya estaban en el contexto aunque no cumplan el filtro.
> Si la precisión importa, usa `AsNoTracking()` o un contexto limpio.

---

## 4. Consultas divididas

EF Core 3 cargaba todas las colecciones incluidas con **una** sentencia (y su explosión cartesiana). EF Core 5 permite elegir:

```csharp run
var comandos = 0;
using var db = new Revista(() => comandos++);
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Add(new Blog { Nombre = "Atlas", Entradas = { new() { Titulo = "a" } }, Autores = { new() { Nombre = "x" } } });
db.SaveChanges();
db.ChangeTracker.Clear();

comandos = 0;
_ = db.Blogs.Include(b => b.Entradas).Include(b => b.Autores).AsSingleQuery().ToList();
Console.WriteLine($"Una consulta: {comandos} comando(s)");          // → Una consulta: 1 comando(s)

comandos = 0;
_ = db.Blogs.Include(b => b.Entradas).Include(b => b.Autores).AsSplitQuery().ToList();
Console.WriteLine($"Dividida: {comandos} comando(s)");              // → Dividida: 3 comando(s)

public class Blog
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public List<Entrada> Entradas { get; } = [];
    public List<Autor> Autores { get; } = [];
}

public class Entrada { public int Id { get; set; } public required string Titulo { get; set; } }
public class Autor { public int Id { get; set; } public required string Nombre { get; set; } }

public class Revista(Action alEjecutar) : DbContext
{
    public DbSet<Blog> Blogs => Set<Blog>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlite("Data Source=revista.db")
            .LogTo(_ => alEjecutar(), [RelationalEventId.CommandExecuted]);
}
```

| | `AsSingleQuery()` (por defecto) | `AsSplitQuery()` |
|---|---|---|
| Sentencias | 1 con `JOIN` | 1 + una por colección incluida |
| Filas transferidas | Producto cartesiano de las colecciones | La suma de las colecciones |
| Consistencia | Siempre consistente | Sin transacción, otra escritura puede colarse entre sentencias |
| Viajes de red | 1 | N |
| Ideal para | Referencias y una colección | Varias colecciones grandes |

> [!TIP]
> Puedes hacer de la división el comportamiento por defecto con `UseSqlServer(..., o => o.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery))`
> y volver a una sola consulta con `AsSingleQuery()` donde convenga. EF Core 10 corrigió la ordenación de las subconsultas divididas y EF Core 11
> **lanza `DbQueryConcurrencyException`** cuando detecta modificaciones concurrentes entre las sentencias, en lugar de devolver colecciones vacías en
> silencio ([capítulo 11](11-ef-core-11-rc.md#9-cambios-incompatibles)).

---

## 5. Diagnóstico al alcance de la mano

EF Core 5 hizo que ver lo que EF hace fuera **una línea de código**:

| Herramienta | Uso | Ejemplo |
|---|---|---|
| `ToQueryString()` | SQL de una consulta sin ejecutarla | `Console.WriteLine(q.ToQueryString())` |
| `LogTo(Console.WriteLine)` | Registro simple, sin configurar `ILoggerFactory` | `o.LogTo(Console.WriteLine, LogLevel.Information)` |
| `ChangeTracker.DebugView` | Estado de cada entidad seguida | `ShortView` / `LongView` |
| `Model.DebugView` | Modelo completo | `db.Model.ToDebugString()` |
| `EnableSensitiveDataLogging()` | Incluir valores de parámetros en el registro | Solo en desarrollo |
| `EnableDetailedErrors()` | Mensajes más precisos al materializar | Solo en desarrollo |
| Contadores de eventos | `dotnet-counters monitor Microsoft.EntityFrameworkCore` | Consultas por segundo, aciertos de caché |

```csharp
public class Tienda : DbContext
{
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlServer("Server=.;Database=Tienda;Trusted_Connection=True;TrustServerCertificate=True")
            .LogTo(Console.WriteLine, LogLevel.Information)       // solo SQL ejecutado y avisos
            .EnableSensitiveDataLogging()                          // ⚠️ nunca en producción
            .EnableDetailedErrors();
}
```

> [!CAUTION]
> `EnableSensitiveDataLogging()` escribe en el registro los **valores** de los parámetros: contraseñas, correos, datos personales. Actívalo solo con
> `if (entorno.IsDevelopment())`.

---

## 6. Interceptores y eventos de `SaveChanges`

EF Core 5 añadió `ISaveChangesInterceptor` y los eventos `SavingChanges`, `SavedChanges` y `SaveChangesFailed`. Es el lugar natural para
**auditoría transversal**:

```csharp run
using var db = new Tienda(new Auditoria());
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

var p = new Producto { Nombre = "Altavoz" };
db.Add(p);
db.SaveChanges();
Console.WriteLine(p.CreadoEn == p.ModificadoEn);        // → True

p.Nombre = "Altavoz Bluetooth";
db.SaveChanges();
Console.WriteLine(p.ModificadoEn > p.CreadoEn);         // → True

public interface IAuditable
{
    DateTime CreadoEn { get; set; }
    DateTime ModificadoEn { get; set; }
}

public class Auditoria : SaveChangesInterceptor
{
    private long _reloj = DateTime.UnixEpoch.Ticks;      // reloj determinista para el ejemplo

    public override InterceptionResult<int> SavingChanges(DbContextEventData e, InterceptionResult<int> result)
    {
        foreach (var entrada in e.Context!.ChangeTracker.Entries<IAuditable>())
        {
            var ahora = new DateTime(_reloj += TimeSpan.TicksPerSecond, DateTimeKind.Utc);
            if (entrada.State == EntityState.Added) entrada.Entity.CreadoEn = ahora;
            if (entrada.State is EntityState.Added or EntityState.Modified) entrada.Entity.ModificadoEn = entrada.State == EntityState.Added ? entrada.Entity.CreadoEn : ahora;
        }
        return result;
    }
}

public class Producto : IAuditable
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public DateTime CreadoEn { get; set; }
    public DateTime ModificadoEn { get; set; }
}

public class Tienda(Auditoria auditoria) : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlite("Data Source=tienda.db").AddInterceptors(auditoria);
}
```

> [!TIP]
> Implementa siempre también `SavingChangesAsync` si tu interceptor hace E/S. La clase base `SaveChangesInterceptor` redirige la versión asíncrona a la
> síncrona solo cuando no la sobrescribes; si la sobrescribes, debes cubrir ambas.

---

## 7. Más novedades de EF Core 5

| Novedad | Descripción |
|---|---|
| Relaciones uno a uno **obligatorias** | `Navigation(x => x.Dependiente).IsRequired()` |
| **Colaciones** | `UseCollation("SQL_Latin1_General_CP1_CS_AS")` y `EF.Functions.Collate(...)` |
| **Funciones con valores de tabla** | TVF mapeadas a métodos y componibles con LINQ |
| **Tipos de entidad compartidos** | El mismo tipo CLR (`Dictionary<string, object>`) para varias entidades |
| Atributo `[Index]` | Índices declarados sobre la clase |
| `IDbContextFactory<T>` | `AddDbContextFactory` para Blazor Server y trabajos en segundo plano |
| `ChangeTracker.Clear()` | Desconectar todas las entidades en una línea |
| `AsNoTrackingWithIdentityResolution()` | Sin seguimiento pero con una instancia por clave |
| Puntos de guardado | `SaveChanges` crea *savepoints* dentro de transacciones explícitas |
| `dotnet ef migrations list` y `--connection` | Ver migraciones aplicadas y apuntar a otra base |
| Mapeo flexible de entidades | `ToTable` para escribir y `ToView`/`ToSqlQuery` para leer |
| `DbContext.Database.CanConnect()` mejorado | Comprobaciones de salud |
| Primer soporte de tablas temporales en el roadmap | Llegaron en EF Core 6 |

### `[Index]` en lugar de API fluida

```csharp
[Index(nameof(Correo), IsUnique = true)]
[Index(nameof(Apellido), nameof(Nombre), Name = "IX_NombreCompleto")]
public class Usuario
{
    public int Id { get; set; }
    public required string Correo { get; set; }
    public required string Nombre { get; set; }
    public required string Apellido { get; set; }
}
```

---

## 8. Cambios incompatibles

| Cambio | Impacto |
|---|---|
| `Required` en una navegación de dependiente tiene otra semántica | 🟠 Medio |
| La consulta definitoria (*defining query*) se sustituye por `ToSqlQuery` y `ToInMemoryQuery` | 🟡 Bajo |
| `IMigrationsModelDiffer` usa `IRelationalModel` | 🟡 Bajo |
| Columnas discriminadoras con longitud máxima calculada | 🟡 Bajo |
| SQLite: `DateTimeOffset` y `decimal` con limitaciones de orden explícitas | 🟡 Bajo |
| Cosmos: la clave de partición se añade a la clave primaria | 🟡 Bajo |

Lista completa: [Breaking changes in EF Core 5.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-5.0/breaking-changes).

---

## 9. Referencias

- [What's new in EF Core 5.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-5.0/whatsnew)
- [Many-to-many relationships](https://learn.microsoft.com/ef/core/modeling/relationships/many-to-many)
- [Single vs. split queries](https://learn.microsoft.com/ef/core/querying/single-split-queries)
- [Simple logging](https://learn.microsoft.com/ef/core/logging-events-diagnostics/simple-logging)
- [Inheritance](https://learn.microsoft.com/ef/core/modeling/inheritance)

<div align="center">

[⬅ 04 · EF Core 3](04-ef-core-3-la-gran-ruptura.md) · [🏠 Índice](../README.md) · [06 · EF Core 6 ➡](06-ef-core-6-rendimiento-y-temporalidad.md)

</div>
