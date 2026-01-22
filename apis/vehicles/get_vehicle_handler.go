package vehicles

import "github.com/gofiber/fiber/v2"

func GetVehicleByIDHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("GetVehicleByIDHandler called, ID: " + ctx.Params("id"))
}
