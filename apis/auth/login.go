package apis

import (
	logger "vehix/core/logger"
	userSvc "vehix/core/service"
	"vehix/models"
	"fmt"

	"github.com/gofiber/fiber/v2"
)

func Login(userSvc userSvc.UserService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {
		return ctx.Next()
	}
}

func throwLoginUserError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, errResp.Message))
	return ctx.Status(statusCode).JSON(errResp)
}
