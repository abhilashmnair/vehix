package apis

import (
	"fmt"
	logger "vehix/core/logger"
	"vehix/core/messages"
	auth "vehix/core/service"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
)

func RefreshTokenHandler(authSvc auth.AuthService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {

		var payload models.RefreshTokenRequest
		if err := ctx.BodyParser(&payload); err != nil {
			return throwRefreshTokenHandlerError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_INVALID_REFRESH_TOKEN.Code,
				Message:   messages.ERR_INVALID_REFRESH_TOKEN.Text,
				Exception: "invalid request body",
			})
		}

		claims, err := authSvc.VerifyJWT(payload.RefreshToken, "refresh")
		if err != nil {
			return throwRefreshTokenHandlerError(ctx, fiber.StatusBadRequest, &models.ErrorResponse{
				MessageID: messages.ERR_INVALID_REFRESH_TOKEN.Code,
				Message:   messages.ERR_INVALID_REFRESH_TOKEN.Text,
				Exception: err.Error(),
			})
		}

		accessToken, err := authSvc.GenerateAccessToken(claims.UserID, claims.Email)
		if err != nil {
			return throwRefreshTokenHandlerError(ctx, fiber.StatusInternalServerError, &models.ErrorResponse{
				MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
				Message:   messages.ERR_UNEXPECTED_ERROR.Text,
				Exception: err.Error(),
			})
		}

		logger.Info(
			fmt.Sprintf("[%s] %s", messages.INFO_ACCESS_TOKEN_SUCCESS.Code,
				messages.INFO_ACCESS_TOKEN_SUCCESS.Text),
		)

		return ctx.Status(fiber.StatusOK).JSON(&models.LoginSuccess{
			AccessToken:  accessToken,
			TokenType:    "Bearer",
			ExpiresIn:    3600,
			RefreshToken: payload.RefreshToken,
		})
	}
}

func throwRefreshTokenHandlerError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, fmt.Sprintf("%s: %s", errResp.Message, errResp.Exception)))
	return ctx.Status(statusCode).JSON(errResp)
}
