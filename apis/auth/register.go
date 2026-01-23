package apis

import (
	"fmt"
	logger "vehix/core/logger"
	"vehix/core/messages"
	auth "vehix/core/service"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
)

func RegisterHandler(authSvc auth.AuthService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {

		var payload models.RegisterUserPayload
		if err := ctx.BodyParser(&payload); err != nil {

			return throwRegisterHandlerError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_BAD_REQUEST.Code,
				Message:   messages.ERR_BAD_REQUEST.Text,
				Exception: fmt.Sprintf("Error parsing request body: %s", err.Error()),
			})
		}

		if payload.Name == "" || payload.Email == "" || payload.Password == "" {

			return throwRegisterHandlerError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_BAD_REQUEST.Code,
				Message:   messages.ERR_BAD_REQUEST.Text,
				Exception: "Missing required fields in payload",
			})
		}

		statusCode, errResp := authSvc.Register(ctx.Context(), payload)
		if errResp != nil {
			return throwRegisterHandlerError(ctx, statusCode, errResp)
		}

		logger.Info(
			fmt.Sprintf("[%s] %s", messages.INFO_USER_REGISTER_SUCCESS.Code,
				messages.INFO_USER_REGISTER_SUCCESS.Text),
		)

		return ctx.Status(statusCode).JSON(&models.SuccessResponse{
			MessageID: messages.INFO_USER_REGISTER_SUCCESS.Code,
			Message:   messages.INFO_USER_REGISTER_SUCCESS.Text,
		})
	}
}

func throwRegisterHandlerError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, fmt.Sprintf("%s: %s", errResp.Message, errResp.Exception)))
	return ctx.Status(statusCode).JSON(errResp)
}
