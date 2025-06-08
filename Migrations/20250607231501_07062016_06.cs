using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace EFCore.Migrations
{
    /// <inheritdoc />
    public partial class _07062016_06 : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.InsertData(
                table: "Job",
                columns: new[] { "JobId", "CategoryId", "CreationDate", "Description", "Priority", "Title" },
                values: new object[] { new Guid("aff00f04-bc5f-4078-b7e0-f84d2e409f11"), new Guid("9b2ee223-763a-486a-b04d-2d0203e1e714"), new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified), null, 0, "Public Services Payment" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DeleteData(
                table: "Job",
                keyColumn: "JobId",
                keyValue: new Guid("aff00f04-bc5f-4078-b7e0-f84d2e409f11"));
        }
    }
}
