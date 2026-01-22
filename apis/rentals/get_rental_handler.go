package rentals

import "github.com/gofiber/fiber/v2"

func GetRentalByIDHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("GetRentalByIDHandler called; ID: " + ctx.Params("id"))
}
