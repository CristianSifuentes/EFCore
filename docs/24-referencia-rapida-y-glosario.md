<div align="center">

# 24 · Referencia rápida y glosario

**EF Core en una página: la API esencial, LINQ y su SQL, configuración, comandos, diagnósticos y un glosario de 60 términos**

[⬅ 23 · Migración entre versiones](23-migracion-entre-versiones.md) · [🏠 Índice](../README.md)

</div>

<!-- ef=10 -->

---

## Contenido

1. [EF Core en un programa](#1-ef-core-en-un-programa)
2. [La API esencial](#2-la-api-esencial)
3. [De LINQ a SQL](#3-de-linq-a-sql)
4. [Configuración del modelo](#4-configuración-del-modelo)
5. [Opciones del contexto](#5-opciones-del-contexto)
6. [Comandos `dotnet ef`](#6-comandos-dotnet-ef)
7. [Códigos de diagnóstico](#7-códigos-de-diagnóstico)
8. [Glosario](#8-glosario)

---

## 1. EF Core en un programa

Todo el ciclo (modelo, creación, inserción, consulta, actualización masiva y borrado) en un único archivo ejecutable:

```csharp run
using var db = new Biblioteca();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();

// Crear
var autora = new Autora { Nombre = "Ursula K. Le Guin" };
db.Libros.AddRange(
    new Libro { Titulo = "Un mago de Terramar", Anio = 1968, Autora = autora, Etiquetas = ["fantasía"] },
    new Libro { Titulo = "Los desposeídos", Anio = 1974, Autora = autora, Etiquetas = ["ciencia ficción", "utopía"] });
db.SaveChanges();

// Leer con proyección
foreach (var x in db.Libros.OrderBy(l => l.Anio).Select(l => new { l.Titulo, l.Anio, Autora = l.Autora.Nombre }))
    Console.WriteLine($"{x.Anio} · {x.Titulo} · {x.Autora}");
// → 1968 · Un mago de Terramar · Ursula K. Le Guin
// → 1974 · Los desposeídos · Ursula K. Le Guin

// Consultar dentro de una colección primitiva (JSON)
Console.WriteLine(db.Libros.Count(l => l.Etiquetas.Contains("utopía")));          // → 1

// Actualizar en masa, sin cargar
Console.WriteLine(db.Libros.Where(l => l.Anio < 1970).ExecuteUpdate(s => s.SetProperty(l => l.Clasico, true)));  // → 1

// Borrar en masa
Console.WriteLine(db.Libros.Where(l => !l.Clasico).ExecuteDelete());               // → 1
Console.WriteLine(db.Libros.AsNoTracking().Single().Titulo);                         // → Un mago de Terramar

public class Autora
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public List<Libro> Libros { get; set; } = [];
}

public class Libro
{
    public int Id { get; set; }
    public required string Titulo { get; set; }
    public int Anio { get; set; }
    public bool Clasico { get; set; }
    public List<string> Etiquetas { get; set; } = [];
    public int AutoraId { get; set; }
    public Autora Autora { get; set; } = null!;
}

public class Biblioteca : DbContext
{
    public DbSet<Libro> Libros => Set<Libro>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=biblioteca.db");
}
```

---

## 2. La API esencial

| Quiero… | API |
|---|---|
| Añadir | `db.Add(x)`, `db.AddRange(…)`, `db.Set<T>().Add(x)` |
| Buscar por clave (usa la caché del contexto) | `db.Find<T>(id)`, `FindAsync` |
| Marcar para borrar | `db.Remove(x)` |
| Adjuntar sin cambios / como modificado | `db.Attach(x)` / `db.Update(x)` |
| Guardar | `SaveChanges()`, `SaveChangesAsync(ct)` |
| Ver el estado | `db.Entry(x).State`, `db.ChangeTracker.DebugView.LongView` |
| Valores originales y de la base | `Entry(x).OriginalValues`, `GetDatabaseValues()` |
| Recargar | `Entry(x).Reload()` |
| Cargar una navegación tarde | `Entry(x).Collection(c => c.Hijos).Load()` / `.Reference(r => r.Padre).Load()` |
| Olvidar todo lo seguido | `ChangeTracker.Clear()` |
| Transacción | `Database.BeginTransaction()`, `Commit()`, `CreateSavepoint()` |
| SQL directo | `Database.ExecuteSql($"…")`, `Database.SqlQuery<T>($"…")`, `Set.FromSql($"…")` |
| Actualizar o borrar en masa | `Where(…).ExecuteUpdate(s => s.SetProperty(…))`, `ExecuteDelete()` |
| Ver el SQL | `query.ToQueryString()` |
| Etiquetar | `TagWith("…")`, `TagWithCallSite()` |
| Esquema | `Database.Migrate()`, `EnsureCreated()`, `EnsureDeleted()`, `HasPendingModelChanges()` |
| Conexión | `Database.GetDbConnection()`, `OpenConnection()`, `SetCommandTimeout()` |

---

## 3. De LINQ a SQL

| LINQ | SQL (SQL Server) |
|---|---|
| `Where(x => x.A == 1)` | `WHERE [x].[A] = 1` |
| `Where(x => ids.Contains(x.Id))` | `WHERE [x].[Id] IN (@ids1, @ids2, …)` (EF 10) |
| `Where(x => x.Nombre.Contains(t))` | `WHERE [x].[Nombre] LIKE N'%' + @t + N'%'` |
| `Where(x => x.Nombre.StartsWith(t))` | `WHERE [x].[Nombre] LIKE @t + N'%'` |
| `OrderBy(x => x.A).ThenByDescending(x => x.B)` | `ORDER BY [x].[A], [x].[B] DESC` |
| `Skip(20).Take(10)` | `OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY` |
| `Select(x => new { x.A, x.Padre.B })` | `SELECT [x].[A], [p].[B] … LEFT JOIN` |
| `Include(x => x.Hijos)` | `LEFT JOIN [Hijos] …` |
| `Any(x => …)` | `EXISTS (SELECT 1 …)` |
| `Count()`, `Sum()`, `Max()` | `COUNT(*)`, `SUM()`, `MAX()` |
| `GroupBy(x => x.K).Select(g => new { g.Key, N = g.Count() })` | `GROUP BY [x].[K]` |
| `x.Fecha.Year == 2026` | `DATEPART(year, [x].[Fecha]) = 2026` |
| `x.Nombre ?? "—"` | `COALESCE([x].[Nombre], N'—')` |
| `cond ? a : b` | `CASE WHEN … THEN … ELSE … END` |
| `Math.Max(a, b)` | `GREATEST(a, b)` (SQL Server 2022, EF 9+) |
| `LeftJoin(…)` | `LEFT JOIN` (EF 10) |
| `FullJoin(…)` | `FULL JOIN` (EF 11 🟡) |
| `EF.Functions.Like(x.N, "a%")` | `LIKE N'a%'` |
| `EF.Functions.VectorDistance("cosine", v, q)` | `VECTOR_DISTANCE('cosine', v, @q)` (EF 10) |

---

## 4. Configuración del modelo

| Necesito | Fluent API | Anotación |
|---|---|---|
| Tabla y esquema | `ToTable("T", "s")` | `[Table("T", Schema = "s")]` |
| Clave | `HasKey(x => x.Id)` / `HasKey(x => new { x.A, x.B })` | `[Key]` / `[PrimaryKey(nameof(A), nameof(B))]` |
| Sin clave | `HasNoKey()` | `[Keyless]` |
| Obligatorio | `IsRequired()` | `[Required]` |
| Longitud | `HasMaxLength(200)` | `[MaxLength(200)]` |
| Precisión | `HasPrecision(18, 2)` | `[Precision(18, 2)]` |
| Columna | `HasColumnName("c")`, `HasColumnType("varchar(20)")` | `[Column("c", TypeName = "…")]` |
| Ignorar | `Ignore(x => x.P)` | `[NotMapped]` |
| Índice | `HasIndex(x => x.Email).IsUnique()` | `[Index(nameof(Email), IsUnique = true)]` |
| Valor por defecto | `HasDefaultValue(0)`, `HasDefaultValueSql("…")` | — |
| Calculada | `HasComputedColumnSql("…", stored: true)` | `[DatabaseGenerated(Computed)]` |
| Concurrencia | `IsRowVersion()`, `IsConcurrencyToken()` | `[Timestamp]`, `[ConcurrencyCheck]` |
| Conversión | `HasConversion<string>()` | — |
| Relación 1:N | `HasOne(x => x.P).WithMany(p => p.H).HasForeignKey(x => x.PId)` | `[ForeignKey]`, `[InverseProperty]` |
| Borrado | `OnDelete(DeleteBehavior.Restrict)` | `[DeleteBehavior(…)]` (EF 7+) |
| Tipo complejo | `ComplexProperty(x => x.Dir)` / `.ToJson()` | `[ComplexType]` |
| Colección compleja | `ComplexCollection(x => x.Items, c => c.ToJson())` | — |
| Filtro global | `HasQueryFilter("Nombre", x => !x.Borrado)` | — |
| Herencia | `UseTphMappingStrategy()` / `UseTptMappingStrategy()` / `UseTpcMappingStrategy()` | — |
| Tabla temporal | `ToTable(t => t.IsTemporal())` | — |
| Semillas | `HasData(…)` | — |

---

## 5. Opciones del contexto

| Opción | Efecto |
|---|---|
| `UseSqlServer` / `UseAzureSql` / `UseNpgsql` / `UseSqlite` / `UseCosmos` | Proveedor |
| `UseQueryTrackingBehavior(NoTracking)` | Lecturas sin seguimiento por defecto |
| `UseQuerySplittingBehavior(SplitQuery)` | Consultas divididas por defecto |
| `EnableRetryOnFailure()` | Reintentos ante errores transitorios |
| `UseCompatibilityLevel(n)` | Nivel de SQL Server que EF puede asumir |
| `UseParameterizedCollectionMode(…)` | Traducción de `Contains` con listas (EF 10) |
| `CommandTimeout(s)`, `MaxBatchSize(n)` | Tiempo de espera y tamaño de lote |
| `MigrationsAssembly("…")`, `MigrationsHistoryTable("…")` | Dónde viven las migraciones |
| `LogTo(…)`, `EnableSensitiveDataLogging()`, `EnableDetailedErrors()` | Diagnóstico |
| `ConfigureWarnings(w => w.Throw(…) / Ignore(…))` | Política de advertencias |
| `AddInterceptors(…)` | Interceptores |
| `UseSeeding(…)`, `UseAsyncSeeding(…)` | Siembra con lógica (EF 9+) |
| `UseLazyLoadingProxies()` | Carga diferida (paquete Proxies) |
| `UseModel(Modelo.Instance)` | Modelo compilado explícito |

---

## 6. Comandos `dotnet ef`

```bash
dotnet ef migrations add <Nombre> [--context C] [--output-dir D] [--namespace N]
dotnet ef migrations list
dotnet ef migrations remove
dotnet ef migrations has-pending-model-changes
dotnet ef migrations script [De] [A] --idempotent -o despliegue.sql
dotnet ef migrations bundle --self-contained -r linux-x64 -o efbundle

dotnet ef database update [Migracion | 0] [--connection "…"]
dotnet ef database drop --force

dotnet ef dbcontext list | info | script
dotnet ef dbcontext optimize [--precompile-queries --nativeaot]
dotnet ef dbcontext scaffold "<cadena>" <Proveedor> -o Modelos --context-dir Datos --no-onconfiguring

# Opciones comunes: -p <proyecto>  -s <inicio>  -c <contexto>  --framework net10.0  --no-build  -v
```

---

## 7. Códigos de diagnóstico

| Código | Significado |
|---|---|
| `EF1001` | Uso de una API interna de EF Core (puede romperse en cualquier versión) |
| `EF1002` | Riesgo de inyección de SQL: interpolación o concatenación en un método `…Raw` |
| `EF9100`–`EF9199` | API experimentales (consultas precompiladas, paginación de Cosmos `EF9102`…) |
| `PendingModelChangesWarning` | El modelo difiere de la última migración (error desde EF 9) |
| `MultipleCollectionIncludeWarning` | `Include` de varias colecciones sin `AsSplitQuery` |
| `RowLimitingOperationWithoutOrderByWarning` | `Skip`/`Take`/`First` sin `OrderBy` |
| `DecimalTypeDefaultWarning` | `decimal` sin precisión configurada |
| `ManyServiceProvidersCreatedWarning` | Se crean demasiados proveedores internos: opciones distintas en cada contexto |

---

## 8. Glosario

| Término | Definición |
|---|---|
| **Agregado** | Grupo de entidades que se modifica como una unidad a través de su raíz (DDD) |
| **AOT (Native AOT)** | Compilación anticipada a código máquina, sin JIT; EF Core la admite de forma experimental desde 9 |
| **Bundle** | Ejecutable autónomo que aplica migraciones (`migrations bundle`) |
| **Campo de respaldo** | Campo privado que EF lee y escribe en lugar de la propiedad |
| **Carga ansiosa** | Traer datos relacionados en la misma consulta (`Include`) |
| **Carga diferida** | Traer datos relacionados al acceder a la navegación (proxies) |
| **Carga explícita** | Traer datos relacionados a petición (`Entry(...).Load()`) |
| ***Change tracker*** | Componente que registra las entidades cargadas y detecta sus cambios |
| **Clave alternativa** | Restricción `UNIQUE` que puede ser destino de una FK |
| **Clave de partición** | En Cosmos DB, la propiedad que reparte los documentos entre particiones |
| **Clave sombra** | Clave foránea que existe en el modelo pero no en la clase |
| **Colección primitiva** | Lista de escalares guardada como JSON (EF 8+) |
| **Compatibilidad (nivel de)** | Versión del motor de SQL Server cuya sintaxis EF puede usar |
| **Concurrencia optimista** | Detectar conflictos al guardar mediante un token, sin bloquear al leer |
| **Consulta compilada** | Consulta cuya traducción se cachea explícitamente con `EF.CompileQuery` |
| **Consulta dividida** | Una consulta por colección incluida (`AsSplitQuery`) |
| **Consulta precompilada** | Consulta traducida en tiempo de compilación (EF 9+) |
| **Contexto** | Instancia de `DbContext`: unidad de trabajo y punto de acceso a la base |
| **Conversión de valor** | Transformación entre el tipo .NET y el tipo guardado |
| **Convención** | Regla que EF aplica sin configuración explícita |
| **`DbSet<T>`** | Colección consultable de entidades de un tipo |
| **`DetectChanges`** | Comparación de las entidades con su instantánea para encontrar cambios |
| **Dependiente** | Lado de una relación que contiene la clave foránea |
| **Discriminador** | Columna que indica el tipo concreto en TPH |
| ***Embedding*** | Vector numérico que representa el significado de un texto o imagen |
| **Entidad** | Clase con identidad (clave) mapeada por EF |
| **Entidad sin clave** | Tipo mapeado de solo lectura, sin identidad (`HasNoKey`) |
| **Estrategia de ejecución** | Política de reintentos ante errores transitorios |
| **Evaluación en cliente** | Ejecutar parte de una consulta en memoria; desde 3.0 solo en la proyección final |
| **Explosión cartesiana** | Multiplicación de filas al incluir varias colecciones en un `JOIN` |
| **Filtro global** | Condición añadida automáticamente a todas las consultas de una entidad |
| **Fluent API** | Configuración del modelo con métodos encadenados en `OnModelCreating` |
| **HiLo** | Generación de claves por bloques reservados con una secuencia |
| **Idempotente (script)** | Script de migración que se puede ejecutar varias veces sin error |
| **Instantánea del modelo** | `ModelSnapshot`: el modelo de la última migración, base de la siguiente |
| **Interceptor** | Componente que observa o altera operaciones de EF (comandos, conexiones, guardado) |
| **LTS / STS** | Soporte largo (3 años, versiones pares) / estándar (24 meses, impares) |
| **Materialización** | Construcción de objetos .NET a partir de filas |
| **Migración** | Clase que describe un cambio de esquema (`Up`/`Down`) |
| **Modelo** | Metadatos que describen entidades, propiedades, relaciones y su mapeo |
| **Modelo compilado** | Código generado que construye el modelo sin ejecutar convenciones |
| **N+1** | Antipatrón: una consulta para la lista y otra por cada elemento |
| **Navegación** | Propiedad que apunta a otra entidad o colección de entidades |
| ***Outbox*** | Tabla donde se guardan los mensajes a publicar en la misma transacción que los datos |
| **Principal** | Lado de una relación referenciado por la clave foránea |
| **Propiedad sombra** | Propiedad que existe en el modelo y la tabla, pero no en la clase |
| **Proveedor** | Paquete que adapta EF Core a una base de datos concreta |
| **Proyección** | `Select` que da forma al resultado, trayendo solo lo necesario |
| **Proxy** | Subclase generada en ejecución para carga diferida o notificación de cambios |
| **Resolución de identidad** | Garantía de que una fila corresponde a un único objeto en el contexto |
| ***Sargable*** | Condición que puede usar un índice (sin funciones sobre la columna) |
| ***Scaffolding*** | Generación de código a partir de una base existente |
| **Semilla** | Datos iniciales (`HasData`, `UseSeeding`) |
| **Tabla temporal** | Tabla de SQL Server que guarda automáticamente el historial de cada fila |
| **Tipo complejo** | Tipo sin identidad, con semántica de valor, mapeado a columnas o JSON (EF 8+) |
| **Tipo propio** | Tipo dependiente de su dueño con clave oculta (`OwnsOne`), predecesor de los complejos |
| **TPH / TPT / TPC** | Herencia en una tabla / tabla por tipo / tabla por tipo concreto |
| **Unidad de trabajo** | Patrón que agrupa los cambios y los confirma juntos (`SaveChanges`) |
| ***Value object*** | Objeto definido por sus valores, sin identidad (ver tipo complejo) |

<div align="center">

[⬅ 23 · Migración entre versiones](23-migracion-entre-versiones.md) · [🏠 Índice](../README.md)

</div>
