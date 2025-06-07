
using System.ComponentModel.DataAnnotations;
namespace EFCore.Models;

public class Category
{
    [Key]
    public Guid CategoryId { get; set; }

    // [Required]
    // [MaxLength(150)]
    public string Name { get; set; }
    public string Description { get; set; }
    public int Weight { get; set; }
    // public int Secuencial { get; set; }
    // public string OtherField { get; set; }
    // public string OtherField2 { get; set; }

    public virtual ICollection<Job> Jobs { get; set; }

}