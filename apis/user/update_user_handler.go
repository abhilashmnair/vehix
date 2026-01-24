package apis

import (
	"fmt"
	"vehix/core/logger"
	"vehix/core/messages"
	user "vehix/core/service"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
)

func UpdateUserHandler(userSvc user.UserService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {
		userID, ok := ctx.Locals("userID").(string)
		if !ok || userID == "" {
			return throwUpdateUserHandlerError(ctx, fiber.StatusUnauthorized, &models.ErrorResponse{
				MessageID: messages.ERR_UNAUTHORIZED.Code,
				Message:   messages.ERR_UNAUTHORIZED.Text,
				Exception: "userID not found in context",
			})
		}

		var payload models.UpdateUserPayload
		if err := ctx.BodyParser(&payload); err != nil {
			return throwUpdateUserHandlerError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_BAD_REQUEST.Code,
				Message:   messages.ERR_BAD_REQUEST.Text,
				Exception: err.Error(),
			})
		}

		statusCode, userResp, errResp := userSvc.UpdateUser(ctx.Context(), userID, &payload)
		if errResp != nil {
			return throwUpdateUserHandlerError(ctx, statusCode, errResp)
		}

		logger.Info(
			fmt.Sprintf("[%s] %s", messages.INFO_USER_UPDATE_SUCCESS.Code,
				messages.INFO_USER_UPDATE_SUCCESS.Text))
		return ctx.Status(statusCode).JSON(userResp)
	}
}

func throwUpdateUserHandlerError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, fmt.Sprintf("%s: %s", errResp.Message, errResp.Exception)))
	return ctx.Status(statusCode).JSON(errResp)
}
