using Microsoft.EntityFrameworkCore;
using EFCore.Models;

namespace EFCore;

public class JobsDbContext : DbContext
{
    //Previus DbSet<Category> categories
    //Before  DbSet<Category> categories { get; set; }
    //Tables was creadted correctly 


    public DbSet<Category> categories { get; set; }
    public DbSet<Job> jobs { get; set; }

    public JobsDbContext(DbContextOptions options) : base(options){

    }

    protected override void OnModelCreating(ModelBuilder builder)
    {


         List<Category> _categories = new List<Category>();
         _categories.Add(new Category
         {
             Name = "Pending",
             CategoryId = Guid.Parse("9b2ee223-763a-486a-b04d-2d0203e1e714"),
             Weight = 20,
             Description = "Description 1"
         });
         _categories.Add(new Category
         {
             Name = "Personal",
             CategoryId = Guid.Parse("f15d905a-ffd8-4f44-b63c-22234605f353"),
             Weight = 20,
             Description = "Desctiption 2"
         });

        //Fluent API is priority
        //Bad practice combinate data anottations with fluent api
        builder.Entity<Category>(category =>
        {
            category.ToTable("Category");
            category.HasKey(c => c.CategoryId);
            category.Property(c => c.Name).HasMaxLength(150);
            category.Property(c => c.Description).HasMaxLength(150);
            category.Property<int>(c => c.Weight);
            // category.Property<int>(c => c.Secuencial);
            // category.Property<string>(c => c.OtherField);
            // category.Property<string>(c => c.OtherField2);

            category.HasData(_categories);

        });
         List<Job> _jobs = new List<Job>();
        _jobs.Add(new Job
        {
            JobId = Guid.Parse("aff00f04-bc5f-4078-b7e0-f84d2e409f11"),
            CategoryId = Guid.Parse("9b2ee223-763a-486a-b04d-2d0203e1e714"),
            Title = "Public Services Payment",
            Priority = Priority.High
        });
        //  _jobs.Add(new Job
        //  {
        //      Title = "Public Services Payment",
        //      JobId = Guid.Parse("aff00f04-bc5f-4078-b7e0-f84d2e409f11"),
        //      CategoryId = Guid.Parse("9b2ee223-763a-486a-b04d-2d0203e1e714"),
        //      Priority = Priority.High
        //     //  FieldHelper = "desc2"

        // });
        //  _jobs.Add(new Job
        //  {
        //      Title = "Public Services Payment",
        //     JobId = Guid.Parse("1bdf26b7-4d81-4e40-b6e9-a50963cdcce7"),
        //     CategoryId = Guid.Parse("f15d905a-ffd8-4f44-b63c-22234605f353"),
        //      Priority = Priority.Low
        //     //  FieldHelper = "desc1"
        //  });



        builder.Entity<Job>(job =>
        {
            job.ToTable("Job");
            job.HasKey(c => c.JobId);
            job.HasOne(c => c.Category).WithMany(p => p.Jobs).HasForeignKey(p => p.CategoryId);
            job.Property(c => c.Title).IsRequired(true).HasMaxLength(200);
            job.Property(c => c.Description).IsRequired(false).HasMaxLength(300);
            job.Property(c => c.Priority);
            job.Property(c => c.CreationDate);
            // job.Property(c => c.Field);
            job.Ignore(c => c.Resume);
            job.HasData(_jobs);


        });
    }


}



//  public AppDbContext(IConfiguration configuration)
//     {
//         _config = configuration;
//     }

//     protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
//     {
//         optionsBuilder.UseSqlServer(_config.GetConnectionString("Conn1"));
//     }

//     protected override void OnModelCreating(ModelBuilder modelBuilder)
//     {

//     }

//     public DbSet<Categoria> Categorias { get; set; }
//     public DbSet<Tarea> Tareas { get; set; }
// }
// }