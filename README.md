# Entity Framework Core: Modern ORM for Relational Databases

![Entity Framework Core Logo](https://codeopinion.com/wp-content/uploads/2017/10/Bitmap-MEDIUM_Entity-Framework-Core-Logo_2colors_Square_Boxed_RGB.png)

## Table of Contents

- [What is Entity Framework Core?](#what-is-entity-framework-core)
- [Key Features](#key-features)
- [How Entity Framework Core Works](#how-entity-framework-core-works)
- [Timeline: Versions and Milestones](#timeline-versions-and-milestones)
- [EF Core Features Every Expert Must Know](#ef-core-features-every-expert-must-know)
- [Most Important EF Core Commands](#most-important-ef-core-commands)
- [Bootstrapping](#bootstrapping)
- [Creating and Evolving a Schema - Migrations](#creating-and-evolving-a-schema---migrations)
- [Advanced Rename - Move](#advanced-rename---move)
- [Database Operations - Beyond migrations](#database-operations---beyond-migrations)
- [Reverse Engineering - Scaffold existing DB](#reverse-engineering---scaffold-existing-db)
- [Testing with - In Memory](#testing-with---in-memory)
- [Supported Platforms](#supported-platforms)
- [Impact and Challenges](#impact-and-challenges)
- [Takeaways](#takeaways)


---

## What is Entity Framework Core?

Entity Framework Core (EF Core) is an open-source, cross-platform object-relational mapper (ORM) for .NET. It simplifies database interactions by allowing developers to work with database objects using .NET classes and LINQ queries. EF Core supports multiple relational databases like SQL Server, PostgreSQL, MySQL, SQLite, and more.

---

## Key Features

1. **Cross-Platform**:
   - Runs on Windows, macOS, and Linux.
2. **Multiple Database Support**:
   - Works with SQL Server, PostgreSQL, MySQL, SQLite, Cosmos DB, and more.
3. **Migrations**:
   - Simplifies schema changes and versioning with code-based migrations.
4. **LINQ Integration**:
   - Enables querying databases using LINQ (Language Integrated Query).
5. **Lazy and Eager Loading**:
   - Controls how related data is loaded into memory.
6. **Change Tracking**:
   - Tracks changes to objects in memory and updates the database accordingly.
7. **Raw SQL Queries**:
   - Allows executing raw SQL queries alongside LINQ.
8. **Custom Conventions**:
   - Enables defining custom rules for mapping between classes and database tables.
9. **Optimized Performance**:
   - Enhanced features like compiled queries and batching for large-scale applications.

---

## How Entity Framework Core Works

1. **DbContext**:
   - Acts as a bridge between the application and the database. Manages connections and tracks changes.
2. **Entity Classes**:
   - Represents database tables as .NET classes.
3. **LINQ Queries**:
   - Converts LINQ expressions into SQL commands.
4. **Migrations**:
   - Manages database schema evolution by applying incremental changes.
5. **Providers**:
   - Abstracts the differences between various relational databases.

---

## Timeline: Versions and Milestones

| **Year** | **Version**      | **Key Milestones and Features**                                  |
|----------|------------------|------------------------------------------------------------------|
| **2016** | **EF Core 1.0**  | - Initial release with basic ORM features.                       |
| **2017** | **EF Core 2.0**  | - Improved LINQ translation and better tooling support.          |
| **2019** | **EF Core 3.0**  | - Breaking changes for LINQ evaluation.<br>- Added Cosmos DB provider. |
| **2020** | **EF Core 5.0**  | - Introduced filtered includes and table-per-type (TPT) inheritance. |
| **2021** | **EF Core 6.0**  | - Long-term support (LTS) version.<br>- Improved performance and compiled models. |
| **2022** | **EF Core 7.0**  | - Added bulk updates, JSON column support, and interceptors.     |
| **2023** | **EF Core 8.0**  | - Enhanced schema management and broader database provider compatibility. |
| **2024** | **EF Core 9.0**  | - ExecuteUpdate/Delete methods, improved scaffolding |
| **2025** | **EF Core 10.0** | - Cross-provider schema sync, tool updates (Preview) |


---

## EF Core Features Every Expert Must Know

- `ExecuteUpdate` / `ExecuteDelete` for bulk operations
- Shadow Properties
- Temporal Tables support
- Owned Types (Value Objects)
- Global Query Filters
- Query Tagging for diagnostics
- Raw SQL binding to DbSet<T>
- Model-level value conversion
- JSON column mapping


---

## Most Important EF Core Commands

```bash
# Create a new migration
dotnet ef migrations add InitialCreate

# Apply all migrations
dotnet ef database update

# Remove last migration
dotnet ef migrations remove

# Drop the database
dotnet ef database drop

# Generate SQL script from migrations
dotnet ef migrations script

# Scaffold from existing database
dotnet ef dbcontext scaffold "connection-string" Microsoft.EntityFrameworkCore.SqlServer -o Models
```

---

## Bootstrapping

```bash
# 1️⃣ Install global CLI once
dotnet tool install --global dotnet-ef

# 2️⃣ Add latest EF Core packages (preview for EF 10)
dotnet add package Microsoft.EntityFrameworkCore               \
               --version 10.0.0-preview.*
dotnet add package Microsoft.EntityFrameworkCore.Design         --version 10.0.0-preview.*

dotnet add package Microsoft.EntityFrameworkCore.SqlServer      # SQL Server
dotnet add package Npgsql.EntityFrameworkCore.PostgreSQL        # PostgreSQL
dotnet add package Microsoft.EntityFrameworkCore.InMemory       # Testing
```

---

## Creating and Evolving a Schema - Migrations

| Purpose                       | CLI (`dotnet ef`)                                      | PMC (VS)                             |
| ----------------------------- | ------------------------------------------------------ | ------------------------------------ |
| Add first migration        | dotnet ef migrations add InitialCreate                 | Add‑Migration InitialCreate          |
| Custom folder              | --output-dir Infrastructure/Migrations                 | -OutputDir Infrastructure\Migrations |
| Target context             | --context BillingContext                               | -Context BillingContext              |
| Apply to DB                | dotnet ef database update                              | Update‑Database                      |
|  Rollback                    | dotnet ef database update 20240424121500\_AddInvoices  | Update‑Database Previous             |
| Remove last (not applied) | dotnet ef migrations remove                            | Remove‑Migration                     |
| Script diff                | dotnet ef migrations script --idempotent -o deploy.sql | Script‑Migration -Idempotent         |
| Bundle (CI/CD)             | dotnet ef migrations bundle --self-contained           | —    


---

## Advanced Rename - Move

```bash
# Rename table Customers → Clients
dotnet ef migrations add RenameCustomerToClient \
    -- --operations "RenameTable:OldName=Customers,NewName=Clients"

# Save migration in custom namespace/folder
dotnet ef migrations add SplitModules \
    --output-dir Modules/Billing --namespace Billing.Migrations
```

---

## Database Operations - Beyond migrations

- **Drop DB**  `dotnet ef database drop --force --no-build`
- **Script model → empty DB**  `dotnet ef dbcontext script`
- **Pending list**  `dotnet ef migrations list`
- Provider override:
  - SQL Server → `--connection "Server=.;TrustServerCertificate=True"`
  - PostgreSQL → `--connection "Host=localhost;Username=app;Password=pwd"`

---

## Reverse Engineering - Scaffold existing DB


```bash
dotnet ef dbcontext scaffold \
  "Host=localhost;Database=crm;Username=app;Pwd=pwd" \
  Npgsql.EntityFrameworkCore.PostgreSQL \
  --schema public,billing --table customers,invoices \
  --context-dir Infrastructure \
  --output-dir Infrastructure/Models \
  --use-database-names --nullable --no-onconfiguring
```

*Add **``** if you prefer attributes over fluent API.*

---
## Testing with - In Memory
 

```csharp
var options = new DbContextOptionsBuilder<AppDbContext>()
                 .UseInMemoryDatabase("UnitTest")
                 .EnableDetailedErrors()
                 .Options;

using var ctx = new AppDbContext(options);
ctx.Database.EnsureCreated();
```

*Seed with ****modelBuilder.Entity\<T>().HasData(...)**** or directly add in tests.*

---

## Supported Platforms

- **Languages**: C#, F#.
- **Frameworks**: .NET Core, .NET 5+, ASP.NET Core.
- **Databases**: SQL Server, PostgreSQL, MySQL, SQLite, Cosmos DB, Oracle, and more.

---

## Impact and Challenges

### **Impact**

1. **Developer Productivity**:
   - Simplifies data access code and reduces boilerplate.
2. **Cross-Platform Compatibility**:
   - Enables building modern cloud-native applications on multiple platforms.
3. **Flexible Architecture**:
   - Adapts to various application needs, from small projects to enterprise systems.

### **Challenges**

1. **Learning Curve**:
   - Requires understanding of LINQ and ORM concepts.
2. **Performance Overhead**:
   - May not be as performant as raw SQL for complex queries.
3. **Breaking Changes**:
   - New versions often introduce breaking changes requiring code refactoring.

---

## Takeaways

- Entity Framework Core is a powerful ORM that simplifies database interactions in .NET applications.
- Regular updates and community support make EF Core a robust tool for modern development.
- Its performance optimizations and cross-platform support ensure scalability and reliability.

---

For more information, visit the official [Entity Framework Core documentation](https://learn.microsoft.com/en-us/ef/core/).
