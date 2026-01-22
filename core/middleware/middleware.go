package middleware

import "github.com/gofiber/fiber/v2"

func Middleware(ctx *fiber.Ctx) error {
	return ctx.Next()
}
