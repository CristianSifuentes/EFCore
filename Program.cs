using EFCore;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
// builder.Services.AddDbContext<JobsDbContext>(p => p.UseInMemoryDatabase("JobsDB"));
builder.Services.AddSqlServer<JobsDbContext>(builder.Configuration.GetConnectionString("sql"));
var app = builder.Build();

app.MapGet("/", () => "Hello World!");

app.MapGet("/dbconextion", async ([FromServices] JobsDbContext dbcontext) =>
{
    dbcontext.Database.EnsureCreated();
    return Results.Ok("In memory db " + dbcontext.Database.IsInMemory());
});

app.MapGet("/api/jobs", async ([FromServices] JobsDbContext dbcontext) =>
{
    return Results.Ok(dbcontext.jobs.Include(p => p.Category).Where(p => p.Priority == EFCore.Models.Priority.Medium));
});


// using (var context = new JobsDbContext(app.Configuration))
// {
//     context.Database.Migrate();
// }
app.Run();
