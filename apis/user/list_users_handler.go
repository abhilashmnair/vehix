package apis

import (
	"fmt"
	"vehix/core/logger"
	"vehix/core/messages"
	user "vehix/core/service"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
)

func ListUsersHandler(userSvc user.UserService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {

		userID, ok := ctx.Locals("userID").(string)
		if !ok || userID == "" {
			return throwListUsersHandlerError(ctx, fiber.StatusUnauthorized, &models.ErrorResponse{
				MessageID: messages.ERR_UNAUTHORIZED.Code,
				Message:   messages.ERR_UNAUTHORIZED.Text,
				Exception: "userID not found in context",
			})
		}

		statusCode, userResp, errResp := userSvc.GetUser(ctx.Context(), userID)
		if errResp != nil {
			return throwListUsersHandlerError(ctx, statusCode, errResp)
		}

		logger.Info(
			fmt.Sprintf("[%s] %s", messages.INFO_USER_FETCH_SUCCESS.Code,
				messages.INFO_USER_FETCH_SUCCESS.Text))

		return ctx.Status(statusCode).JSON(userResp)
	}

}

func throwListUsersHandlerError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, fmt.Sprintf("%s: %s", errResp.Message, errResp.Exception)))
	return ctx.Status(statusCode).JSON(errResp)
}
