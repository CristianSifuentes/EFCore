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

    public JobsDbContext(DbContextOptions options) : base(options)
    {

    }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        //Fluent API is priority
        //Bad practice combinate data anottations with fluent api
        builder.Entity<Category>(category =>
        {
            category.ToTable("Category");
            category.HasKey(c => c.CategoryId);
            category.Property(c => c.Name).IsRequired().HasMaxLength(150);
            category.Property(c => c.Description).IsRequired().HasMaxLength(150);

        });

        builder.Entity<Job>(job =>
        {
            job.ToTable("Job");
            job.HasKey(c => c.JobId);
            job.HasOne(c => c.Category).WithMany(p => p.Jobs).HasForeignKey(p => p.CategoryId);
            job.Property(c => c.Title).IsRequired().HasMaxLength(200);
            job.Property(c => c.Description);
            job.Property(c => c.Priority);
            job.Property(c => c.CreationDate);
                      

        }); 
    }


}