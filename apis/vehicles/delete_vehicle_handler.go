package vehicles

import "github.com/gofiber/fiber/v2"

func DeleteVehicleHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("DeleteVehicleHandler called, ID: " + ctx.Params("id"))
}
