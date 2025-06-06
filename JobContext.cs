using Microsoft.EntityFrameworkCore;
using EFCore.Models;

namespace EFCore;

public class JobsDbContext : DbContext
{
    DbSet<Category> categories;
    DbSet<Job> jobs;

    public JobsDbContext(DbContextOptions options) : base(options) {
        
    }

}