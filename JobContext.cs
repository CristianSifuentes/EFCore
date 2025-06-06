using Microsoft.EntityFrameworkCore;
using EFCore.Models;

namespace EFCore;

public class JobsDbContext : DbContext
{
    //Previus DbSet<Category> categories
    //Before  DbSet<Category> categories { get; set; }
    //Tables was creadted correctly 
    DbSet<Category> categories { get; set; }
    DbSet<Job> jobs { get; set; }

    public JobsDbContext(DbContextOptions options) : base(options) {
        
    }

}