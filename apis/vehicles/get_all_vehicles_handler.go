package vehicles

import "github.com/gofiber/fiber/v2"

func GetAllVehiclesHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("GetAllVehiclesHandler called")
}
