package apis

import "github.com/gofiber/fiber/v2"

func GetAllUsersHandler(ctx *fiber.Ctx) error {
	return ctx.SendString("GetAllUsersHandler called")
}
