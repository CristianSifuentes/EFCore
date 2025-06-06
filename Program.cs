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

app.Run();
