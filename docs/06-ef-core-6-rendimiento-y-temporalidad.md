<div align="center">

# 06 · EF Core 6: rendimiento y temporalidad

**Tablas temporales, modelos compilados, configuración previa a convenciones, *bundles* de migración y un 70 % más de velocidad (2021, LTS)**

[⬅ 05 · EF Core 5](05-ef-core-5-relaciones-y-diagnostico.md) · [🏠 Índice](../README.md) · [07 · EF Core 7 ➡](07-ef-core-7-json-y-operaciones-masivas.md)

</div>

<!-- ef=10 -->

| Ficha | EF Core 6.0 |
|---|---|
| **Publicación** | 8-nov-2021, junto con .NET 6 y C# 10 |
| **Plataforma** | `net6.0` (primera versión que exige .NET moderno) |
| **Soporte** | ⛔ 12-nov-2024 (**LTS**) |
| **Idea central** | Rendimiento en tiempo de ejecución y en el arranque, y SQL Server de primera |

---

## Contenido

1. [El salto de rendimiento](#1-el-salto-de-rendimiento)
2. [Tablas temporales de SQL Server](#2-tablas-temporales-de-sql-server)
3. [Modelos compilados](#3-modelos-compilados)
4. [Configuración previa a convenciones](#4-configuración-previa-a-convenciones)
5. [*Bundles* de migración](#5-bundles-de-migración)
6. [Atributos nuevos](#6-atributos-nuevos)
7. [EF Core en Minimal APIs](#7-ef-core-en-minimal-apis)
8. [Más novedades de EF Core 6](#8-más-novedades-de-ef-core-6)
9. [Cambios incompatibles](#9-cambios-incompatibles)
10. [Referencias](#10-referencias)

---

## 1. El salto de rendimiento

El objetivo declarado de EF Core 6 era **acercarse a Dapper** en consultas simples. En el benchmark **TechEmpower Fortunes**, EF Core 6 fue un
**70 % más rápido** que EF Core 5, y la distancia con Dapper bajó a un dígito porcentual.

| Mejora | Efecto |
|---|---|
| Menos asignaciones al crear un `DbContext` | Arranque de cada petición más barato |
| Registro con `LoggerMessage` y comprobaciones de nivel tempranas | Menos coste cuando el registro está desactivado |
| Agrupación de contextos sin inyección de dependencias | `PooledDbContextFactory<T>` utilizable en cualquier aplicación |
| Caché de consultas más rápida | Menos coste por consulta repetida |
| Materialización optimizada | Menos *boxing* al leer valores |

> [!NOTE]
> El rendimiento de un ORM no es un número, sino un **perfil**: EF es excelente en lecturas proyectadas y escrituras por lotes, y puede ser lento si sigue
> miles de entidades innecesariamente. El [capítulo 17](17-rendimiento-y-diagnostico.md) es la guía completa.

---

## 2. Tablas temporales de SQL Server

Las **tablas temporales** (SQL Server 2016+) guardan automáticamente el historial de cada fila. EF Core 6 las crea con migraciones y añade cinco
operadores para consultar el pasado:

```csharp
public class Empleado
{
    public Guid Id { get; set; }
    public required string Nombre { get; set; }
    public required string Puesto { get; set; }
}

public class Rrhh : DbContext
{
    public DbSet<Empleado> Empleados => Set<Empleado>();

    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlServer("Server=.;Database=Rrhh;Trusted_Connection=True;TrustServerCertificate=True");

    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Empleado>().ToTable("Empleados", t => t.IsTemporal(h =>
        {
            h.HasPeriodStart("ValidoDesde");
            h.HasPeriodEnd("ValidoHasta");
            h.UseHistoryTable("EmpleadosHistorial");
        }));

    public Task<List<Empleado>> ComoEstabaEl(DateTime instanteUtc)
        => Empleados.TemporalAsOf(instanteUtc).OrderBy(e => e.Nombre).ToListAsync();

    public Task<List<(string Puesto, DateTime Desde)>> CarreraDe(Guid id)
        => Empleados.TemporalAll()
            .Where(e => e.Id == id)
            .OrderBy(e => EF.Property<DateTime>(e, "ValidoDesde"))
            .Select(e => ValueTuple.Create(e.Puesto, EF.Property<DateTime>(e, "ValidoDesde")))
            .ToListAsync();
}
```

| Operador | SQL | Devuelve |
|---|---|---|
| `TemporalAsOf(t)` | `FOR SYSTEM_TIME AS OF` | El estado en un instante |
| `TemporalAll()` | `FOR SYSTEM_TIME ALL` | Todas las versiones |
| `TemporalFromTo(a, b)` | `FROM a TO b` | Versiones activas en el intervalo (excluye `b`) |
| `TemporalBetween(a, b)` | `BETWEEN a AND b` | Igual, incluyendo las que empiezan en `b` |
| `TemporalContainedIn(a, b)` | `CONTAINED IN (a, b)` | Versiones que empezaron y terminaron dentro |

> [!TIP]
> Las columnas de periodo son **propiedades de sombra**: se leen con `EF.Property<DateTime>(e, "ValidoDesde")`. **EF Core 11** permite por fin
> mapearlas a propiedades CLR normales ([capítulo 11](11-ef-core-11-rc.md#6-sql-server-y-azure-sql)). Las entidades devueltas por los operadores
> temporales **no se siguen**: no puedes modificarlas y guardarlas.

---

## 3. Modelos compilados

Construir el modelo en el arranque (el paso del [capítulo 02](02-anatomia-de-ef-core.md#3-el-modelo-la-fuente-de-verdad)) puede llevar segundos con
cientos de entidades. Un **modelo compilado** es ese mismo modelo **generado como código C#**:

```bash
dotnet ef dbcontext optimize --output-dir ModeloCompilado --namespace Tienda.Modelo
```

```csharp omitir
// Código generado: TiendaContextModel.cs, ProductoEntityType.cs, …
protected override void OnConfiguring(DbContextOptionsBuilder o)
    => o.UseModel(TiendaContextModel.Instance)       // en EF Core 9+ ya no hace falta: se detecta solo
        .UseSqlServer(cadena);
```

| Aspecto | Modelo normal | Modelo compilado |
|---|---|---|
| Arranque con 450 entidades (medición de Microsoft) | ~10 s | ~1,5 s |
| Hay que regenerarlo al cambiar el modelo | No | **Sí** (o con MSBuild en EF Core 9+) |
| Filtros globales, *seeding* con lambdas | Sí | Con limitaciones en EF Core 6–8 |
| Requisito para Native AOT | — | **Sí** (EF Core 9+) |

---

## 4. Configuración previa a convenciones

Antes de EF Core 6, decir "todas las cadenas tienen como máximo 200 caracteres" exigía recorrer el modelo a mano. `ConfigureConventions` establece reglas
**por tipo .NET** que se aplican antes de las convenciones:

```csharp run
using var db = new Tienda();
var producto = db.Model.FindEntityType(typeof(Producto))!;
foreach (var p in producto.GetProperties().Where(p => !p.IsPrimaryKey()))
    Console.WriteLine($"{p.Name}: longitud {p.GetMaxLength()?.ToString() ?? "-"}, precisión {p.GetPrecision()?.ToString() ?? "-"}, {p.GetProviderClrType()?.Name ?? p.ClrType.Name}");
// → Codigo: longitud 20, precisión -, String
// → Estado: longitud -, precisión -, String
// → Nombre: longitud 200, precisión -, String
// → Precio: longitud -, precisión 18, Decimal

public enum Estado { Activo, Retirado }

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public required string Codigo { get; set; }
    public decimal Precio { get; set; }
    public Estado Estado { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");

    protected override void ConfigureConventions(ModelConfigurationBuilder c)
    {
        c.Properties<string>().HaveMaxLength(200);           // todas las cadenas
        c.Properties<decimal>().HavePrecision(18, 2);        // todos los decimales
        c.Properties<Estado>().HaveConversion<string>();     // todos los enums Estado como texto
    }

    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Producto>().Property(p => p.Codigo).HasMaxLength(20);   // la API fluida sigue ganando
}
```

Fíjate en `Estado`: se guarda como texto, pero **no** recibió la longitud 200. Las reglas `Properties<T>()` se aplican por **tipo CLR** de la propiedad
(`Estado`), no por el tipo al que se convierte (`string`). Si quieres limitarla, añade `.HaveMaxLength(20)` a la regla de `Estado`.

> [!TIP]
> Es el lugar ideal para **tipos de valor de dominio** (`Email`, `Dinero`, `ClienteId`): `c.Properties<Email>().HaveConversion<EmailConverter>()` y no
> tendrás que repetir la conversión en cada entidad.

---

## 5. *Bundles* de migración

Un *bundle* es un **ejecutable autónomo** que aplica las migraciones. Resuelve el problema clásico de los despliegues: no hace falta el SDK, ni el
código fuente, ni `dotnet ef` en el servidor.

```bash
# En CI: generar el ejecutable (para Linux x64, autocontenido)
dotnet ef migrations bundle --self-contained -r linux-x64 -o efbundle --configuration Release

# En el despliegue: aplicar las migraciones pendientes
./efbundle --connection "$CONNECTION_STRING"
```

| Estrategia de despliegue | Ventaja | Riesgo |
|---|---|---|
| `Database.Migrate()` al arrancar | Sencillo | Varias réplicas compitiendo; la app necesita permisos DDL |
| Script SQL idempotente | Revisable por un DBA | Pasos manuales |
| **Bundle** | Un artefacto, sin SDK, con código de salida | Hay que gestionar el secreto de conexión en el pipeline |

La comparación completa, con el bloqueo de migraciones de EF Core 9, está en el [capítulo 15](15-migraciones-y-despliegue.md#7-estrategias-de-despliegue).

---

## 6. Atributos nuevos

| Atributo | Equivale a | Ejemplo |
|---|---|---|
| `[Unicode(false)]` | `IsUnicode(false)` | `varchar` en lugar de `nvarchar` |
| `[Precision(18, 2)]` | `HasPrecision(18, 2)` | `decimal(18,2)` |
| `[EntityTypeConfiguration(typeof(ProductoConfig))]` | `ApplyConfiguration(new ProductoConfig())` | Asocia la clase de configuración a la entidad |
| `[Column(Order = 1)]` | `HasColumnOrder(1)` | Orden de columnas al crear la tabla |

```csharp
[EntityTypeConfiguration(typeof(FacturaConfig))]
public class Factura
{
    public int Id { get; set; }
    [Unicode(false), MaxLength(12)] public required string Numero { get; set; }
    [Precision(18, 2)] public decimal Total { get; set; }
}

public class FacturaConfig : IEntityTypeConfiguration<Factura>
{
    public void Configure(EntityTypeBuilder<Factura> b) => b.HasIndex(f => f.Numero).IsUnique();
}
```

---

## 7. EF Core en Minimal APIs

.NET 6 trajo las Minimal APIs, y EF Core 6 añadió métodos de registro de una línea, **los que usa este repositorio** en [`Program.cs`](../Program.cs):

```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSqlServer<JobsDbContext>(builder.Configuration.GetConnectionString("sql"));
var app = builder.Build();

app.MapGet("/api/jobs", async (JobsDbContext db) => await db.Jobs.AsNoTracking().ToListAsync());
app.Run();

public class Job { public Guid JobId { get; set; } public required string Title { get; set; } }

public class JobsDbContext(DbContextOptions<JobsDbContext> options) : DbContext(options)
{
    public DbSet<Job> Jobs => Set<Job>();
}
```

| Método | Equivale a |
|---|---|
| `AddSqlServer<T>(cadena)` | `AddDbContext<T>(o => o.UseSqlServer(cadena))` |
| `AddSqlite<T>(cadena)` | `AddDbContext<T>(o => o.UseSqlite(cadena))` |
| `AddNpgsql<T>(cadena)` (Npgsql) | `AddDbContext<T>(o => o.UseNpgsql(cadena))` |
| `AddCosmos<T>(cadena, base)` | `AddDbContext<T>(o => o.UseCosmos(cadena, base))` |

> [!NOTE]
> Los métodos `AddXxx<T>` aceptan acciones opcionales para el proveedor y para las opciones, pero **no** usan agrupación. Para *pooling*, usa
> `AddDbContextPool<T>`.

---

## 8. Más novedades de EF Core 6

| Novedad | Descripción |
|---|---|
| Columnas dispersas | `IsSparse()` en SQL Server |
| `AddPooledDbContextFactory<T>` | Fábrica y agrupación combinadas |
| `TagWithCallSite()` | Etiqueta con archivo y línea |
| Mejoras de `GroupBy` | Más formas traducibles, incluido `GroupBy` seguido de `FirstOrDefault` |
| `EF.Functions.Random()` | `RAND()`/`random()` en la base |
| `string.Concat` con varios argumentos | Traducido |
| Comentarios en tablas y columnas | `HasComment` / `[Comment]` llevados al DDL |
| Cosmos | Colecciones primitivas, `FromSqlRaw`, diagnósticos, `TimeToLive` |
| SQLite | Conexiones agrupadas, `DateOnly`/`TimeOnly` |
| Convenciones de conversión | `ValueComparer` automático para conversiones comunes |

---

## 9. Cambios incompatibles

| Cambio | Impacto |
|---|---|
| Los dependientes opcionales anidados en tablas compartidas sin propiedades obligatorias no se admiten | 🔴 Alto |
| Cambiar el dueño de una entidad propia lanza excepción | 🟠 Medio |
| Cosmos: las colecciones de entidades propias se guardan dentro del documento padre | 🟠 Medio |
| Las tablas temporales requieren SQL Server 2016+ | 🟡 Bajo |
| `Microsoft.Data.Sqlite`: `DateTime` y `DateTimeOffset` con formato ISO 8601 con `T` opcional | 🟡 Bajo |
| Las columnas de discriminador en TPH pasan a tener longitud máxima | 🟡 Bajo |

Lista completa: [Breaking changes in EF Core 6.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-6.0/breaking-changes).

---

## 10. Referencias

- [What's new in EF Core 6.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-6.0/whatsnew)
- [Using SQL Server temporal tables with EF Core](https://learn.microsoft.com/ef/core/providers/sql-server/temporal-tables)
- [Compiled models](https://learn.microsoft.com/ef/core/performance/advanced-performance-topics#compiled-models)
- [Pre-convention model configuration](https://learn.microsoft.com/ef/core/modeling/bulk-configuration#pre-convention-configuration)
- [Migration bundles](https://learn.microsoft.com/ef/core/managing-schemas/migrations/applying#bundles)

<div align="center">

[⬅ 05 · EF Core 5](05-ef-core-5-relaciones-y-diagnostico.md) · [🏠 Índice](../README.md) · [07 · EF Core 7 ➡](07-ef-core-7-json-y-operaciones-masivas.md)

</div>
