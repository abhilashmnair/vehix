package apis

import "github.com/gofiber/fiber/v2"

func GetUserByIDHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("GetUserByIDHandler called, ID: " + ctx.Params("id"))
}
