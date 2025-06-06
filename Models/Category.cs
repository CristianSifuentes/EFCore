
using System.ComponentModel.DataAnnotations;
namespace EFCore.Models;

public class Category
{
    [Key]
    public Guid CategoryId { get; set; }
    public string Name { get; set; }
    public string Description { get; set; }
    public virtual ICollection<Homework> Homeworks { get; set; }
}