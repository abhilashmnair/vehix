package apis

import "github.com/gofiber/fiber/v2"

func DeleteUserHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("DeleteUserHandler called, ID: " + ctx.Params("id"))
}
