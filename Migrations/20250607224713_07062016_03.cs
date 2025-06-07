using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace EFCore.Migrations
{
    /// <inheritdoc />
    public partial class _07062016_03 : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.InsertData(
                table: "Category",
                columns: new[] { "CategoryId", "Description", "Name", "Weight" },
                values: new object[,]
                {
                    { new Guid("9b2ee223-763a-486a-b04d-2d0203e1e714"), "Description 1", "Pending", 20 },
                    { new Guid("f15d905a-ffd8-4f44-b63c-22234605f353"), "Desctiption 2", "Personal", 20 }
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DeleteData(
                table: "Category",
                keyColumn: "CategoryId",
                keyValue: new Guid("9b2ee223-763a-486a-b04d-2d0203e1e714"));

            migrationBuilder.DeleteData(
                table: "Category",
                keyColumn: "CategoryId",
                keyValue: new Guid("f15d905a-ffd8-4f44-b63c-22234605f353"));
        }
    }
}
