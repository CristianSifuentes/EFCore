namespace EFCore.Models;

public class Homework
{
    public Guid HomeWorkId { get; set; }
    public Guid CategoryId { get; set; }
    public string Title { get; set; }
    public string Description { get; set; }
    public virtual Priority priority { get; set; }
    public DateTime CreationDate { get; set; }
    public virtual Category Category { get; set; }

}

public enum Priority
{
    High,
    Medium,
    Low
}