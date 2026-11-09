<div align="center">

# 17 · Rendimiento y diagnóstico

**Medir antes de optimizar: registros, etiquetas, *pooling*, modelos compilados, AOT, métricas, interceptores y el mapa de costos de EF Core**

[⬅ 16 · Proveedores](16-proveedores.md) · [🏠 Índice](../README.md) · [18 · Pruebas ➡](18-pruebas.md)

</div>

<!-- ef=10 -->

---

## Contenido

1. [El método](#1-el-método)
2. [Ver el SQL: registros y etiquetas](#2-ver-el-sql-registros-y-etiquetas)
3. [Agrupación de contextos](#3-agrupación-de-contextos)
4. [Modelos compilados](#4-modelos-compilados)
5. [Consultas precompiladas y Native AOT](#5-consultas-precompiladas-y-native-aot)
6. [Lista de comprobación de consultas](#6-lista-de-comprobación-de-consultas)
7. [Métricas y trazas](#7-métricas-y-trazas)
8. [Interceptores](#8-interceptores)
9. [*Benchmarks* con BenchmarkDotNet](#9-benchmarks-con-benchmarkdotnet)
10. [El mapa de costos](#10-el-mapa-de-costos)
11. [Referencias](#11-referencias)

---

## 1. El método

> **Casi todos los problemas de rendimiento de EF Core son problemas de SQL**: demasiadas consultas, demasiadas filas, demasiadas columnas o un plan sin
> índice. La sobrecarga propia de EF (traducir, materializar, seguir) rara vez supera el 10–20 % del tiempo de una petición.

```mermaid
flowchart LR
    A["① Detectar<br/>métricas, APM,<br/>quejas de usuarios"] --> B["② Aislar<br/>TagWith, logs,<br/>ToQueryString"]
    B --> C["③ Explicar<br/>plan de ejecución,<br/>Query Store"]
    C --> D["④ Corregir<br/>índice, proyección,<br/>split, AsNoTracking"]
    D --> E["⑤ Medir<br/>BenchmarkDotNet,<br/>antes y después"]
    E --> A
    classDef p fill:#450A0A,stroke:#F87171,color:#F8FAFC
    class A,B,C,D,E p
```

| Capa | Herramienta | Qué te dice |
|---|---|---|
| Aplicación | `LogTo`, `ILogger`, OpenTelemetry | Qué SQL se ejecuta, cuántas veces y cuánto tarda |
| EF Core | `ToQueryString`, `DebugView`, métricas `Microsoft.EntityFrameworkCore` | Traducción, *change tracker*, caché de consultas |
| Base de datos | Plan de ejecución, Query Store, `pg_stat_statements` | Por qué una consulta concreta es lenta |
| Laboratorio | BenchmarkDotNet | Cuánto mejora un cambio, con rigor estadístico |

---

## 2. Ver el SQL: registros y etiquetas

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

var q = db.Productos
    .TagWith("Listado de la portada")
    .Where(p => p.Precio > 2)
    .Select(p => p.Nombre);
Console.WriteLine(q.ToQueryString());
// → -- Listado de la portada
// → 
// → SELECT "p"."Nombre"
// → FROM "Productos" AS "p"
// → WHERE "p"."Precio" > 2

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

| Opción | Uso | ¿Producción? |
|---|---|---|
| `LogTo(Console.WriteLine, LogLevel.Information)` | Registro simple, sin DI | Desarrollo |
| `LogTo(…, new[] { RelationalEventId.CommandExecuted })` | Solo los eventos que te interesan | Desarrollo |
| `ILogger` con categoría `Microsoft.EntityFrameworkCore.Database.Command` en `Information` | SQL y duración en tu sistema de logs | ✅ con muestreo |
| `EnableSensitiveDataLogging()` | Muestra los **valores** de los parámetros | ❌ nunca: expone datos personales |
| `EnableDetailedErrors()` | Mensajes de error más precisos al materializar | Desarrollo |
| `ConfigureWarnings(w => w.Throw(RelationalEventId.MultipleCollectionIncludeWarning))` | Convertir advertencias en excepciones | ✅ en pruebas |
| `TagWith("…")` / `TagWithCallSite()` | Comentario en el SQL con texto o archivo y línea | ✅ |

```json
// appsettings.Development.json: ver el SQL sin tocar el código
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.EntityFrameworkCore.Database.Command": "Information"
    }
  }
}
```

> [!TIP]
> `TagWithCallSite()` (EF Core 7+) añade `-- file: Servicios/Pedidos.cs:42` al SQL automáticamente. Con eso, una consulta lenta que aparece en Query Store
> te lleva directamente a la línea de código que la produjo.

---

## 3. Agrupación de contextos

Crear un `DbContext` es barato, pero no gratis: reserva memoria, resuelve servicios internos y configura opciones. Con miles de peticiones por segundo,
el **pool** reutiliza instancias:

```csharp omitir
// En lugar de AddDbContext:
builder.Services.AddDbContextPool<JobsDbContext>(
    o => o.UseSqlServer(builder.Configuration.GetConnectionString("Jobs")),
    poolSize: 1024);

// Fuera de DI, también existe una factoría con pool:
var factoria = new PooledDbContextFactory<JobsDbContext>(opciones);
using var db = factoria.CreateDbContext();
```

| | `AddDbContext` | `AddDbContextPool` |
|---|---|---|
| Instancia por petición | Nueva | Reutilizada (se reinicia) |
| Mejora típica | — | Hasta un 30–50 % menos de asignaciones en *benchmarks* de alto rendimiento |
| Estado en campos del contexto | ✅ | ❌ se comparte entre peticiones: **peligro** |
| `OnConfiguring` con dependencias por petición | ✅ | ❌ |

> [!WARNING]
> Un contexto en *pool* **no puede tener estado propio por petición** (un `TenantId` inyectado en el constructor, por ejemplo): la instancia la usará
> después otra petición. Para multiinquilino con *pool*, usa una factoría que asigne el inquilino tras obtener la instancia
> ([capítulo 19](19-arquitectura-de-aplicaciones.md)).

---

## 4. Modelos compilados

La **primera** vez que se usa un tipo de contexto, EF construye el modelo: recorre las entidades, aplica convenciones y ejecuta `OnModelCreating`.
Con cientos de entidades, eso puede costar **segundos** de arranque en frío: un problema en funciones *serverless* y contenedores que escalan a cero.
Un **modelo compilado** genera en tiempo de diseño el código C# que construye el modelo final, saltándose todo ese trabajo:

```bash
# Generar (EF Core 6+)
dotnet ef dbcontext optimize --output-dir ModeloCompilado --namespace JobsDb.ModeloCompilado

# EF Core 9+: regenerarlo automáticamente al compilar con el paquete Tasks
dotnet add package Microsoft.EntityFrameworkCore.Tasks
```

| Entidades | Arranque sin modelo compilado | Con modelo compilado |
|---|---|---|
| 10 | Despreciable | Despreciable |
| 400 | ~1–2 s | ~0,1–0,2 s |
| 2 000+ | Varios segundos | Una fracción |

> [!NOTE]
> Las cifras son **órdenes de magnitud orientativos** tomados de las publicaciones del equipo de EF; tu resultado depende del hardware y del modelo.
> Mide el arranque real de tu aplicación antes y después.

| Limitación del modelo compilado | Detalle |
|---|---|
| Debe regenerarse en cada cambio del modelo | Automático con `Microsoft.EntityFrameworkCore.Tasks` (EF Core 9+) |
| Filtros globales que dependen de datos externos | Soportados, pero el modelo no puede variar por instancia |
| `OnModelCreating` condicional (modelo distinto por inquilino) | No soportado: un modelo compilado es fijo |

---

## 5. Consultas precompiladas y Native AOT

EF Core 9 dio el paso siguiente: generar en compilación **también las consultas** (SQL y materializador) mediante interceptores de C#
([capítulo 09](09-ef-core-9-cosmos-aot-y-siembra.md#3-native-aot-y-consultas-precompiladas)). Es lo que hace posible publicar con **Native AOT**.

```xml
<PropertyGroup>
  <PublishAot>true</PublishAot>
  <!-- EF Core 10: generar modelo y consultas al publicar -->
  <EFScaffoldModelStage>publish</EFScaffoldModelStage>
  <EFPrecompileQueriesStage>publish</EFPrecompileQueriesStage>
</PropertyGroup>
```

| | JIT normal | Modelo compilado | Native AOT + consultas precompiladas |
|---|---|---|---|
| Arranque en frío | Lento | Rápido | **Mínimo** |
| Memoria | Base | Base | Menor |
| Consultas dinámicas | ✅ | ✅ | ❌ |
| Estado | 🟢 | 🟢 | 🟡 Experimental en EF Core 9 y 10 |

---

## 6. Lista de comprobación de consultas

| # | Pregunta | Si la respuesta es "no" |
|---|---|---|
| 1 | ¿Cada petición ejecuta un número **constante** de consultas? | N+1: usa proyección o `Include` |
| 2 | ¿Traes solo las **columnas** que usas? | `Select` a un DTO |
| 3 | ¿Traes solo las **filas** que usas? | `Where` + paginación por *keyset* |
| 4 | ¿Las lecturas puras son **sin seguimiento**? | `AsNoTracking()` o proyección |
| 5 | ¿Hay **índice** para cada `Where`, `OrderBy` y `JOIN` frecuente? | `HasIndex`, revisar el plan |
| 6 | ¿Los `Include` de varias colecciones usan **split**? | `AsSplitQuery()` |
| 7 | ¿Las actualizaciones masivas evitan cargar entidades? | `ExecuteUpdate` / `ExecuteDelete` |
| 8 | ¿Todo es **asíncrono** en el servidor web? | `ToListAsync`, `SaveChangesAsync` |
| 9 | ¿El contexto vive **poco** (una petición)? | Un contexto longevo acumula entidades y ralentiza `DetectChanges` |
| 10 | ¿Las condiciones son ***sargables***? | Evita funciones sobre la columna: `Where(x => x.Fecha.Year == 2026)` → `Where(x => x.Fecha >= inicio && x.Fecha < fin)` |

---

## 7. Métricas y trazas

EF Core publica **métricas** con `System.Diagnostics.Metrics` (EF Core 9+, antes contadores de eventos) en el medidor `Microsoft.EntityFrameworkCore`:

| Métrica | Lo que indica un valor alto |
|---|---|
| `microsoft.entityframeworkcore.active_dbcontexts` | Contextos que no se liberan (fuga) |
| `…queries` | Volumen de consultas: compáralo con las peticiones (N+1) |
| `…compiled_query_cache_hits` / `…compiled_query_cache_misses` | Consultas con forma dinámica que no se reutilizan |
| `…savechanges` | Volumen de escrituras |
| `…optimistic_concurrency_failures` | Conflictos de concurrencia |
| `…execution_strategy_operation_failures` | Errores transitorios y reintentos |

```bash
# En vivo, sin modificar la aplicación
dotnet-counters monitor --process-id <pid> --counters Microsoft.EntityFrameworkCore
```

```csharp omitir
// OpenTelemetry: trazas de cada comando SQL junto a la petición HTTP
builder.Services.AddOpenTelemetry()
    .WithTracing(t => t
        .AddAspNetCoreInstrumentation()
        .AddEntityFrameworkCoreInstrumentation()     // paquete OpenTelemetry.Instrumentation.EntityFrameworkCore
        .AddOtlpExporter())
    .WithMetrics(m => m.AddMeter("Microsoft.EntityFrameworkCore").AddOtlpExporter());
```

> [!TIP]
> Con **.NET Aspire**, las integraciones de EF Core (`AddSqlServerDbContext<T>`, `AddNpgsqlDbContext<T>`) configuran trazas, métricas, comprobaciones de
> salud y reintentos con una sola línea, y el panel de Aspire muestra cada consulta SQL dentro de su petición.

---

## 8. Interceptores

Los **interceptores** se ejecutan en puntos concretos de la canalización de EF y pueden **observar, modificar o sustituir** la operación:

| Interfaz | Intercepta | Ejemplo de uso |
|---|---|---|
| `IDbCommandInterceptor` | Creación y ejecución de comandos | Añadir *hints*, medir duración, bloquear consultas sin `WHERE` |
| `IDbConnectionInterceptor` | Apertura y cierre de conexiones | Token de Entra ID, `SET` de sesión, *row-level security* |
| `IDbTransactionInterceptor` | Transacciones y *savepoints* | Auditoría |
| `ISaveChangesInterceptor` | `SaveChanges` | Auditoría, *outbox*, eventos de dominio ([capítulo 14](14-guardado-y-concurrencia.md#7-auditoría-y-lógica-transversal)) |
| `IMaterializationInterceptor` (7+) | Creación de instancias | Inyectar servicios en entidades |
| `IQueryExpressionInterceptor` (7+) | El árbol LINQ antes de traducir | Añadir un `OrderBy` por defecto |
| `IIdentityResolutionInterceptor` (7+) | Conflictos de identidad al adjuntar | Resolver duplicados |

```csharp run
using var db = new Tienda();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Productos.AddRange(new Producto { Nombre = "Té" }, new Producto { Nombre = "Café" });
db.SaveChanges();
Contador.Total = 0;

var nombres = db.Productos.Select(p => p.Nombre).ToList();
var cantidad = db.Productos.Count();
Console.WriteLine($"Consultas: {Contador.Total}");                  // → Consultas: 2

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
}

public static class Contador { public static int Total; }

public sealed class ContadorDeConsultas : DbCommandInterceptor
{
    public override InterceptionResult<System.Data.Common.DbDataReader> ReaderExecuting(
        System.Data.Common.DbCommand cmd, CommandEventData e, InterceptionResult<System.Data.Common.DbDataReader> r)
    {
        Interlocked.Increment(ref Contador.Total);
        return r;
    }

    public override InterceptionResult<object> ScalarExecuting(
        System.Data.Common.DbCommand cmd, CommandEventData e, InterceptionResult<object> r)
    {
        Interlocked.Increment(ref Contador.Total);
        return r;
    }
}

public class Tienda : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlite("Data Source=tienda.db").AddInterceptors(new ContadorDeConsultas());
}
```

> [!TIP]
> Este mismo interceptor, en una prueba de integración, es un **detector de N+1**: ejecuta el endpoint y comprueba que `Contador.Total` no crece con el
> número de elementos ([capítulo 18](18-pruebas.md)).

> [!WARNING]
> Los interceptores se ejecutan en **cada** operación: deben ser rápidos y sin estado mutable compartido (o seguro entre hilos, como el `Interlocked`
> del ejemplo). Implementa siempre la versión síncrona **y** la asíncrona (`ReaderExecutingAsync`…) si tu aplicación usa ambas.

---

## 9. *Benchmarks* con BenchmarkDotNet

```csharp omitir
[MemoryDiagnoser]
public class LecturaDeTrabajos
{
    private JobsDbContext _db = null!;

    [GlobalSetup] public void Setup() => _db = CrearContextoConDatos(filas: 1_000);

    [Benchmark(Baseline = true)]
    public List<Job> EntidadesSeguidas() => _db.jobs.Include(j => j.Category).ToList();

    [Benchmark]
    public List<Job> SinSeguimiento() => _db.jobs.AsNoTracking().Include(j => j.Category).ToList();

    [Benchmark]
    public List<TrabajoDto> Proyeccion() => _db.jobs.Select(j => new TrabajoDto(j.JobId, j.Title, j.Category.Name)).ToList();
}
```

| Método | Media relativa | Memoria relativa |
|---|---|---|
| `EntidadesSeguidas` | 1,00 | 1,00 |
| `SinSeguimiento` | ~0,6 | ~0,6 |
| `Proyeccion` | ~0,3 | ~0,2 |

> [!NOTE]
> La tabla muestra la **forma típica** del resultado, no una medición de este repositorio: el orden (proyección < sin seguimiento < seguidas) es estable,
> las proporciones dependen de tu modelo. Ejecuta siempre en `Release` y contra el motor real.

---

## 10. El mapa de costos

| Operación | Coste relativo | Comentario |
|---|---|---|
| Viaje de red a la base | 🔴🔴🔴🔴 | Domina todo: minimiza el **número** de consultas |
| Plan sin índice sobre tabla grande | 🔴🔴🔴🔴 | Domina todo: revisa el plan |
| Materializar 10 000 entidades seguidas | 🔴🔴🔴 | Instantáneas y resolución de identidad |
| `DetectChanges` con miles de entidades | 🔴🔴 | Se llama en cada `SaveChanges` y en algunas consultas |
| Construir el modelo (primera vez) | 🔴🔴 una vez | Modelo compilado |
| Traducir una consulta nueva | 🟠 una vez por forma | Caché de consultas |
| Calcular la clave de caché | 🟢 | `EF.CompileQuery` lo evita |
| Crear un `DbContext` | 🟢 | *Pooling* lo reduce |

---

## 11. Referencias

- [Performance overview](https://learn.microsoft.com/ef/core/performance/)
- [Efficient querying](https://learn.microsoft.com/ef/core/performance/efficient-querying)
- [Advanced performance topics](https://learn.microsoft.com/ef/core/performance/advanced-performance-topics) — *pooling*, modelos compilados
- [Logging, events and diagnostics](https://learn.microsoft.com/ef/core/logging-events-diagnostics/)
- [Interceptors](https://learn.microsoft.com/ef/core/logging-events-diagnostics/interceptors)
- [Metrics](https://learn.microsoft.com/ef/core/logging-events-diagnostics/metrics)

<div align="center">

[⬅ 16 · Proveedores](16-proveedores.md) · [🏠 Índice](../README.md) · [18 · Pruebas ➡](18-pruebas.md)

</div>
