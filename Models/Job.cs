using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
//DataAnnotations

namespace EFCore.Models;

public class Job
{
    // [Key]
    public Guid JobId { get; set; }

    // [ForeignKey(nameof(Category))]
    public Guid CategoryId { get; set; }

    // [Required]
    // [MaxLength(150)]
    public string Title { get; set; }
    public string Description { get; set; }
    // public required string Field { get; set; }
    public virtual Priority Priority { get; set; }
    public DateTime CreationDate { get; set; }
    public virtual Category Category { get; set; }
 
    // Title + description
    // [NotMapped]
    public string Resume { get; set; }

}

public enum Priority
{
    High,
    Medium,
    Low
}