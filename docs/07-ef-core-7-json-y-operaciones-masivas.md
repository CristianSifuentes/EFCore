<div align="center">

# 07 · EF Core 7: JSON y operaciones masivas

**`ExecuteUpdate` y `ExecuteDelete`, columnas JSON, TPC, procedimientos almacenados, nuevos interceptores y convenciones propias (2022)**

[⬅ 06 · EF Core 6](06-ef-core-6-rendimiento-y-temporalidad.md) · [🏠 Índice](../README.md) · [08 · EF Core 8 ➡](08-ef-core-8-tipos-complejos.md)

</div>

<!-- ef=10 -->

| Ficha | EF Core 7.0 |
|---|---|
| **Publicación** | 8-nov-2022, junto con .NET 7 y C# 11 |
| **Plataforma** | `net6.0` (funciona en .NET 6 y .NET 7) |
| **Soporte** | ⛔ 14-may-2024 (STS) |
| **Idea central** | Dejar de cargar entidades para modificarlas y modelar documentos dentro de bases relacionales |

---

## Contenido

1. [`ExecuteUpdate` y `ExecuteDelete`](#1-executeupdate-y-executedelete)
2. [Columnas JSON](#2-columnas-json)
3. [Herencia TPC](#3-herencia-tpc)
4. [`SaveChanges` más rápido](#4-savechanges-más-rápido)
5. [Procedimientos almacenados para insertar, actualizar y borrar](#5-procedimientos-almacenados-para-insertar-actualizar-y-borrar)
6. [Nuevos interceptores](#6-nuevos-interceptores)
7. [Convenciones propias](#7-convenciones-propias)
8. [Más novedades de EF Core 7](#8-más-novedades-de-ef-core-7)
9. [Cambios incompatibles](#9-cambios-incompatibles)
10. [Referencias](#10-referencias)

---

## 1. `ExecuteUpdate` y `ExecuteDelete`

Durante seis años, actualizar mil filas con EF significaba **cargarlas, modificarlas y guardarlas**: mil objetos en memoria y mil sentencias `UPDATE`
(en lotes, pero mil). EF Core 7 añadió dos operadores que **traducen LINQ directamente a `UPDATE` y `DELETE`**:

```csharp run
using System.Data.Common;

var registro = new UltimoComando();
using var db = new Tienda(registro);
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.AddRange(
    new Producto { Nombre = "Lápiz", Precio = 1.00m, Stock = 0 },
    new Producto { Nombre = "Goma", Precio = 0.50m, Stock = 10 },
    new Producto { Nombre = "Regla", Precio = 2.00m, Stock = 5 });
db.SaveChanges();

var subidos = db.Productos
    .Where(p => p.Stock > 0)
    .ExecuteUpdate(s => s.SetProperty(p => p.Precio, p => p.Precio * 1.10m));
Console.WriteLine($"Actualizados: {subidos}");          // → Actualizados: 2
Console.WriteLine(registro.Texto);
// → UPDATE "Productos" AS "p"
// → SET "Precio" = ef_multiply("p"."Precio", '1.1')
// → WHERE "p"."Stock" > 0

var borrados = db.Productos.Where(p => p.Stock == 0).ExecuteDelete();
Console.WriteLine($"Borrados: {borrados}");             // → Borrados: 1
Console.WriteLine(registro.Texto);
// → DELETE FROM "Productos" AS "p"
// → WHERE "p"."Stock" = 0

public class UltimoComando : DbCommandInterceptor
{
    public string Texto { get; private set; } = "";
    public override InterceptionResult<int> NonQueryExecuting(DbCommand c, CommandEventData e, InterceptionResult<int> r)
    {
        Texto = c.CommandText;
        return r;
    }
}

public class Producto
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public decimal Precio { get; set; }
    public int Stock { get; set; }
}

public class Tienda(UltimoComando registro) : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlite("Data Source=tienda.db").AddInterceptors(registro);
}
```

> [!NOTE]
> `ef_multiply` es una función que el proveedor de SQLite registra en cada conexión: SQLite no tiene tipo `decimal` y EF guarda los `decimal` como
> `TEXT` para no perder precisión. En SQL Server la misma consulta produce `SET [p].[Precio] = [p].[Precio] * 1.1`.

### Lo que hay que saber antes de usarlos

| Característica | `SaveChanges` | `ExecuteUpdate` / `ExecuteDelete` |
|---|---|---|
| Carga entidades | Sí | **No** |
| Sentencias | Una por entidad (en lotes) | **Una** para todas las filas |
| *Change tracker* | Se actualiza | **No se entera**: las entidades ya cargadas quedan desfasadas |
| Transacción | Implícita | **Ninguna implícita**: es una sola sentencia; para varias, abre una tú |
| Interceptores de `SaveChanges`, auditoría | Se ejecutan | **No se ejecutan** |
| Concurrencia optimista | Comprobada | No, salvo que la incluyas en el `Where` |
| Cascadas configuradas en EF | Aplicadas en cliente si hace falta | Solo las de la base de datos |
| Proveedores | Todos | Relacionales (no Cosmos ni InMemory) |

> [!WARNING]
> El caso que más sorprende: si cargaste una entidad y después ejecutas `ExecuteUpdate` sobre ella, **la instancia en memoria conserva el valor
> antiguo**. Usa `ExecuteUpdate` en operaciones independientes o llama a `ChangeTracker.Clear()` después.

EF Core 10 cambió el parámetro de `ExecuteUpdate` de árbol de expresión a **lambda normal**, de modo que los *setters* condicionales ya no exigen construir
expresiones a mano ([capítulo 10](10-ef-core-10-lts-vectores-y-json.md#8-executeupdate-con-una-lambda-normal)).

---

## 2. Columnas JSON

Las bases relacionales modernas tienen funciones JSON. EF Core 7 permite mapear un **agregado completo** (un objeto con objetos y colecciones dentro) a
**una sola columna JSON**, y consultar dentro de ella con LINQ:

```csharp run
using var db = new Blogs();
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Add(new Autor
{
    Nombre = "Arthur",
    Contacto = new Contacto
    {
        Correo = "arthur@ejemplo.com",
        Direccion = new Direccion { Ciudad = "Londres", Pais = "Reino Unido" }
    }
});
db.SaveChanges();

var guardado = db.Database.SqlQuery<string>($"SELECT Contacto AS Value FROM Autores").Single();
Console.WriteLine(guardado);
// → {"Correo":"arthur@ejemplo.com","Direccion":{"Ciudad":"Londres","Pais":"Reino Unido"}}

var londinenses = db.Autores.Where(a => a.Contacto.Direccion.Ciudad == "Londres");
Console.WriteLine(londinenses.ToQueryString());
// → SELECT "a"."Id", "a"."Nombre", "a"."Contacto"
// → FROM "Autores" AS "a"
// → WHERE "a"."Contacto" ->> '$.Direccion.Ciudad' = 'Londres'
Console.WriteLine(londinenses.Count());                            // → 1

public class Autor
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public required Contacto Contacto { get; set; }
}

public class Contacto
{
    public required string Correo { get; set; }
    public required Direccion Direccion { get; set; }
}

public class Direccion
{
    public required string Ciudad { get; set; }
    public required string Pais { get; set; }
}

public class Blogs : DbContext
{
    public DbSet<Autor> Autores => Set<Autor>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=blogs.db");
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Autor>().OwnsOne(a => a.Contacto, c =>
        {
            c.ToJson();
            c.OwnsOne(x => x.Direccion);
        });
}
```

| Cuándo usar una columna JSON | Cuándo no |
|---|---|
| Datos que siempre se leen con su dueño | Datos que se consultan por separado |
| Estructura variable o anidada (configuraciones, metadatos, direcciones) | Datos con integridad referencial hacia otras tablas |
| Evitar `JOIN` con tablas pequeñas de detalle | Columnas por las que filtras constantemente sin índice JSON |

> [!IMPORTANT]
> En EF Core 7 las columnas JSON se mapeaban con **tipos propios** (`OwnsOne(...).ToJson()`). Desde **EF Core 10** la forma recomendada son los
> **tipos complejos** (`ComplexProperty(...).ToJson()`), con semántica de valor y soporte de `ExecuteUpdate`, y en **EF Core 11** las colecciones
> propias JSON sin clave quedan obsoletas ([capítulo 10](10-ef-core-10-lts-vectores-y-json.md#4-tipos-complejos-mapeados-a-json)).

---

## 3. Herencia TPC

**Tabla por tipo concreto**: cada clase **concreta** tiene su tabla con **todas** sus columnas, incluidas las heredadas; la clase base abstracta no
tiene tabla.

```csharp run
using var db = new Pagos();
Console.WriteLine(db.Database.GenerateCreateScript().Trim());
// → CREATE TABLE "PagosConTarjeta" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_PagosConTarjeta" PRIMARY KEY,
// →     "Importe" TEXT NOT NULL,
// →     "UltimosDigitos" TEXT NOT NULL
// → );
// →
// →
// → CREATE TABLE "Transferencias" (
// →     "Id" INTEGER NOT NULL CONSTRAINT "PK_Transferencias" PRIMARY KEY,
// →     "Importe" TEXT NOT NULL,
// →     "Iban" TEXT NOT NULL
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
        b.Entity<Pago>().UseTpcMappingStrategy();
        b.Entity<PagoConTarjeta>().ToTable("PagosConTarjeta");
        b.Entity<Transferencia>().ToTable("Transferencias");
    }
}
```

> [!CAUTION]
> En TPC **los identificadores no pueden repetirse entre tablas**: un `PagoConTarjeta` con `Id = 1` y una `Transferencia` con `Id = 1` serían
> indistinguibles al consultar `Todos`. Por eso EF no usa `IDENTITY`/`AUTOINCREMENT` en TPC y en SQL Server crea una **secuencia compartida**; con
> SQLite, que no tiene secuencias, tendrás que asignar las claves tú (o usar `Guid`).

---

## 4. `SaveChanges` más rápido

EF Core 7 reescribió partes del *pipeline* de actualización:

| Optimización | Antes | EF Core 7 |
|---|---|---|
| Transacción para una sola sentencia | `BEGIN … COMMIT` siempre | Sin transacción explícita (la sentencia ya es atómica) |
| Recuperar claves en SQL Server | `INSERT` + `SELECT` de la fila | `INSERT … OUTPUT INSERTED.Id` |
| Varias filas en SQL Server | Varias sentencias | `MERGE` con `OUTPUT` en un viaje |
| SQLite | `INSERT` + `SELECT last_insert_rowid()` | `INSERT … RETURNING` |

El resultado: hasta **cuatro veces menos latencia** al insertar con la base en otra máquina. La contrapartida fue un cambio incompatible: las tablas con
**disparadores** en SQL Server no admiten `OUTPUT` sin `INTO`, y hay que declararlos con `HasTrigger` (§ 9).

---

## 5. Procedimientos almacenados para insertar, actualizar y borrar

Muchas bases corporativas prohíben `INSERT`/`UPDATE`/`DELETE` directos y exigen procedimientos. EF6 lo permitía; EF Core lo recuperó en la 7:

```csharp
public class Persona
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    public byte[] Version { get; set; } = [];
}

public class Rrhh : DbContext
{
    protected override void OnModelCreating(ModelBuilder b)
        => b.Entity<Persona>(e =>
        {
            e.Property(p => p.Version).IsRowVersion();
            e.InsertUsingStoredProcedure("Persona_Insertar", sp => sp
                .HasParameter(p => p.Nombre)
                .HasResultColumn(p => p.Id)
                .HasResultColumn(p => p.Version));
            e.UpdateUsingStoredProcedure("Persona_Actualizar", sp => sp
                .HasOriginalValueParameter(p => p.Id)
                .HasParameter(p => p.Nombre)
                .HasOriginalValueParameter(p => p.Version)
                .HasResultColumn(p => p.Version)
                .HasRowsAffectedResultColumn());
            e.DeleteUsingStoredProcedure("Persona_Borrar", sp => sp
                .HasOriginalValueParameter(p => p.Id)
                .HasOriginalValueParameter(p => p.Version)
                .HasRowsAffectedResultColumn());
        });
}
```

---

## 6. Nuevos interceptores

| Interceptor | Momento | Uso típico |
|---|---|---|
| `IMaterializationInterceptor` | Al crear e inicializar una entidad leída | Inyectar servicios, marcar la hora de carga |
| `IQueryExpressionInterceptor` | Antes de compilar el árbol LINQ | Añadir un `OrderBy` estable, reescribir consultas |
| `IIdentityResolutionInterceptor` | Al adjuntar una entidad con clave duplicada | Fusionar valores en lugar de lanzar excepción |
| Mejoras en `DbConnectionInterceptor` | Creación de conexiones | Conexiones con token de Entra ID |

```csharp run
using var db = new Tienda(new MarcaDeCarga());
db.Database.EnsureDeleted();
db.Database.EnsureCreated();
db.Add(new Producto { Nombre = "Lupa" });
db.SaveChanges();
db.ChangeTracker.Clear();

var p = db.Productos.Single();
Console.WriteLine(p.Origen);                    // → cargado desde la base de datos

public interface IConOrigen { string? Origen { get; set; } }

public class MarcaDeCarga : IMaterializationInterceptor
{
    public object InitializedInstance(MaterializationInterceptionData datos, object entidad)
    {
        if (entidad is IConOrigen e) e.Origen = "cargado desde la base de datos";
        return entidad;
    }
}

public class Producto : IConOrigen
{
    public int Id { get; set; }
    public required string Nombre { get; set; }
    [NotMapped] public string? Origen { get; set; }
}

public class Tienda(MarcaDeCarga interceptor) : DbContext
{
    public DbSet<Producto> Productos => Set<Producto>();
    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseSqlite("Data Source=tienda.db").AddInterceptors(interceptor);
}
```

---

## 7. Convenciones propias

EF Core 7 hizo públicas las **convenciones de modelado**: puedes quitar las existentes y añadir las tuyas. Una convención se ejecuta como reacción a
eventos del modelo (se añadió una propiedad, se finalizó el modelo…).

```csharp run
using Microsoft.EntityFrameworkCore.Metadata;
using Microsoft.EntityFrameworkCore.Metadata.Conventions;

using var db = new Tienda();
var tabla = db.Model.FindEntityType(typeof(LineaDePedido))!;
Console.WriteLine(tabla.GetTableName());                                      // → linea_de_pedido
Console.WriteLine(string.Join(", ", tabla.GetProperties().Select(p => p.GetColumnName())));
// → id, cantidad, precio_unitario

public class SnakeCase : IModelFinalizingConvention
{
    public void ProcessModelFinalizing(IConventionModelBuilder modelo, IConventionContext<IConventionModelBuilder> ctx)
    {
        foreach (var entidad in modelo.Metadata.GetEntityTypes())
        {
            entidad.Builder.ToTable(Convertir(entidad.ClrType.Name));
            foreach (var p in entidad.GetProperties())
                p.Builder.HasColumnName(Convertir(p.Name));
        }
    }

    private static string Convertir(string nombre)
        => string.Concat(nombre.Select((c, i) => i > 0 && char.IsUpper(c) ? "_" + char.ToLowerInvariant(c) : char.ToLowerInvariant(c).ToString()));
}

public class LineaDePedido
{
    public int Id { get; set; }
    public int Cantidad { get; set; }
    public decimal PrecioUnitario { get; set; }
}

public class Tienda : DbContext
{
    public DbSet<LineaDePedido> Lineas => Set<LineaDePedido>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.UseSqlite("Data Source=tienda.db");
    protected override void ConfigureConventions(ModelConfigurationBuilder c)
    {
        c.Conventions.Add(_ => new SnakeCase());
        c.Conventions.Remove(typeof(TableNameFromDbSetConvention));     // quitar una convención existente
    }
}
```

> [!TIP]
> Para PostgreSQL existe el paquete de la comunidad `EFCore.NamingConventions` (`UseSnakeCaseNamingConvention()`), que hace esto mismo de forma completa,
> incluidas claves, índices y restricciones.

---

## 8. Más novedades de EF Core 7

| Novedad | Descripción |
|---|---|
| **División de entidades** | `SplitToTable`: una entidad en varias tablas |
| `HasTrigger` | Declarar disparadores para que EF evite `OUTPUT` incompatible |
| `Database.SqlQuery<int>(...)` | SQL crudo que devuelve escalares (tipos no mapeados llegarían en la 8) |
| Plantillas T4 de *scaffolding* | `dotnet new ef-templates` para personalizar el código generado |
| `GroupBy` como operador final | `ToDictionary` de grupos directamente |
| Muchos a muchos unidireccional | Navegación solo en un lado |
| Claves con conversión y valor generado | Identificadores fuertemente tipados con `IDENTITY` |
| Mejoras en `ExecuteSql` | Interpolación segura en `ExecuteSql(FormattableString)` |
| `FromSql` de nuevo | Versión solo interpolada y segura |
| Mapeo de funciones de agregado de estadística | `EF.Functions.StandardDeviationSample` etc. en SQL Server |
| Cosmos | `DateTime`/`Math`/`string` traducidos, regex |

---

## 9. Cambios incompatibles

| Cambio | Impacto | Mitigación |
|---|---|---|
| **`Encrypt=True` por defecto** en SQL Server (Microsoft.Data.SqlClient 4.0) | 🔴 Alto | Certificado válido o `TrustServerCertificate=True` en desarrollo |
| Tablas con disparadores en SQL Server fallan por `OUTPUT` | 🔴 Alto | `ToTable(t => t.HasTrigger("nombre"))` |
| SQLite: tablas con disparadores y `RETURNING` | 🟠 Medio | `HasTrigger` también en SQLite |
| Dependientes huérfanos de relaciones opcionales no se borran | 🟠 Medio | Configurar la cascada explícitamente |
| `DeleteBehavior` en cascada por defecto con dependientes en TPC | 🟡 Bajo | — |
| Columnas de clave en tablas compartidas exigen orden | 🟡 Bajo | — |

> [!NOTE]
> El primer cambio es la razón de que la cadena de conexión de este repositorio lleve `TrustServerCertificate=True`: sin ella, SQL Server Express con su
> certificado autofirmado rechaza la conexión desde EF Core 7.

---

## 10. Referencias

- [What's new in EF Core 7.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-7.0/whatsnew)
- [ExecuteUpdate and ExecuteDelete](https://learn.microsoft.com/ef/core/saving/execute-insert-update-delete)
- [JSON columns](https://learn.microsoft.com/ef/core/what-is-new/ef-core-7.0/whatsnew#json-columns)
- [TPC inheritance](https://learn.microsoft.com/ef/core/modeling/inheritance#table-per-concrete-type-configuration)
- [Model building conventions](https://learn.microsoft.com/ef/core/modeling/bulk-configuration#conventions)
- [Breaking changes in EF Core 7.0](https://learn.microsoft.com/ef/core/what-is-new/ef-core-7.0/breaking-changes)

<div align="center">

[⬅ 06 · EF Core 6](06-ef-core-6-rendimiento-y-temporalidad.md) · [🏠 Índice](../README.md) · [08 · EF Core 8 ➡](08-ef-core-8-tipos-complejos.md)

</div>
