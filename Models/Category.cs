
using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;
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

    [JsonIgnore]
    public virtual ICollection<Job> Jobs { get; set; }

}