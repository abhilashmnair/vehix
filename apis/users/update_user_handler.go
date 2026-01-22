package apis

import "github.com/gofiber/fiber/v2"

func UpdateUserHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("UpdateUserHandler called, ID: " + ctx.Params("id"))
}
