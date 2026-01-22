package apis

import (
	logger "vehix/core/logger"
	"vehix/core/messages"
	userSvc "vehix/core/service"
	"vehix/models"
	"fmt"

	"github.com/gofiber/fiber/v2"
)

func Register(userSvc userSvc.UserService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {

		var payload models.CreateUserPayload
		if err := ctx.BodyParser(&payload); err != nil {

			return throwRegisterUserError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_BAD_REQUEST.Code,
				Message:   messages.ERR_BAD_REQUEST.Text,
				Exception: fmt.Sprintf("Error parsing request body: %s", err.Error()),
			})
		}

		if payload.Name == "" || payload.Email == "" || payload.Password == "" {

			return throwRegisterUserError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_BAD_REQUEST.Code,
				Message:   messages.ERR_BAD_REQUEST.Text,
				Exception: "Missing required fields in payload",
			})
		}

		logger.Info("PostUserHandler called")

		statusCode, errResp := userSvc.RegisterUser(ctx.Context(), payload)
		if errResp != nil {
			return throwRegisterUserError(ctx, statusCode, errResp)
		}

		logger.Info(fmt.Sprintf("[%s] %s", messages.INFO_USER_REGISTER_SUCCESS.Code, messages.INFO_USER_REGISTER_SUCCESS.Text))
		return ctx.Status(statusCode).JSON(&models.SuccessResponse{
			MessageID: messages.INFO_USER_REGISTER_SUCCESS.Code,
			Message:   messages.INFO_USER_REGISTER_SUCCESS.Text,
		})
	}
}

func throwRegisterUserError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, errResp.Message))
	return ctx.Status(statusCode).JSON(errResp)
}
