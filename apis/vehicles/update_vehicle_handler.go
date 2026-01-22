package vehicles

import "github.com/gofiber/fiber/v2"

func UpdateVehicleHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("UpdateVehicleHandler called, ID: " + ctx.Params("id"))
}
