package rentals

import "github.com/gofiber/fiber/v2"

func PostRentalHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("PostRentalHandler called; ID: " + ctx.Params("id"))
}
