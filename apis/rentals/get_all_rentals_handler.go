package rentals

import "github.com/gofiber/fiber/v2"

func GetAllRentalsHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("GetAllRentalsHandler called")
}
