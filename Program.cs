using EFCore;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<JobsContext>(p => p.UseInMemoryDatabase("JobsDB"));
var app = builder.Build();

app.MapGet("/", () => "Hello World!");

app.MapGet("/dbconextion", async ([FromServices] JobsContext dbcontext) =>
{
    dbcontext.Database.EnsureCreated();
    return Results.Ok("In memory db " + dbcontext.Database.IsInMemory());
});

app.Run();
