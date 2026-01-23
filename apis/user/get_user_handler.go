package apis

import (
	"fmt"
	"vehix/core/logger"
	"vehix/core/messages"
	user "vehix/core/service"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
)

func GetUserByIDHandler(userSvc user.UserService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {

		userID := ctx.Locals("userID").(string)

		statusCode, userResp, errResp := userSvc.GetUser(ctx.Context(), userID)
		if errResp != nil {
			return throwGetUserByIDHandlerError(ctx, statusCode, errResp)
		}

		logger.Info(
			fmt.Sprintf("[%s] %s", messages.INFO_USER_FETCH_SUCCESS.Code,
				messages.INFO_USER_FETCH_SUCCESS.Text))

		return ctx.Status(statusCode).JSON(userResp)
	}

}

func throwGetUserByIDHandlerError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, fmt.Sprintf("%s: %s", errResp.Message, errResp.Exception)))
	return ctx.Status(statusCode).JSON(errResp)
}
