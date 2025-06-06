using Microsoft.EntityFrameworkCore;
using EFCore.Models;

namespace EFCore;

public class JobsContext : DbContext
{
    DbSet<Category> categories;
    DbSet<Job> jobs;

    public JobsContext(DbContextOptions options) : base(options) {
        
    }

}