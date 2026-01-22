package vehicles

import "github.com/gofiber/fiber/v2"

func PostVehiclesHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("PostVehiclesHandler called")
}
