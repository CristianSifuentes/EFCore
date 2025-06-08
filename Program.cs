using EFCore;
using EFCore.Models;
using Microsoft.AspNetCore.Http.HttpResults;
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
    return Results.Ok(dbcontext.jobs.Include(p => p.Category));
});

app.MapPost("/api/jobs", async ([FromServices] JobsDbContext dbcontext, [FromBody] Job job) =>
{
    job.JobId = Guid.NewGuid();
    job.CreationDate = DateTime.Now;
    await dbcontext.AddAsync(job);
    dbcontext.SaveChanges();
    return Results.Ok();
});

app.MapPut("/api/jobs{id}", async ([FromServices] JobsDbContext dbcontext, [FromBody] Job job, [FromRoute] Guid id) =>
{
    var _actualJob = await dbcontext.jobs.FindAsync(id);
    if (_actualJob != null)
    {
        _actualJob.CategoryId = job.CategoryId;
        _actualJob.Title = job.Title;
        _actualJob.Description = job.Description;
        await dbcontext.SaveChangesAsync();
        return Results.Ok();
    }
    return Results.NotFound();
});

app.MapDelete("/api/jobs{id}", async ([FromServices] JobsDbContext dbcontext, [FromRoute] Guid id) =>
{
    var _actualJob = await dbcontext.jobs.FindAsync(id);
    if (_actualJob != null)
    {
        dbcontext.Remove(_actualJob);
        await dbcontext.SaveChangesAsync();
        return  Results.Ok();

    }
    return Results.NotFound();
});

// using (var context = new JobsDbContext(app.Configuration))
// {
//     context.Database.Migrate();
// }
app.Run();
