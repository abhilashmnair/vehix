package middleware

import (
	"fmt"
	"vehix/core/logger"
	"vehix/core/messages"
	auth "vehix/core/service"
	models "vehix/models"

	"github.com/gofiber/fiber/v2"
)

func Middleware(authSvc auth.AuthService) fiber.Handler {
	return func(ctx *fiber.Ctx) error {
		tokenString := ctx.Get("Authorization") // Bearer <token>
		if tokenString == "" {
			return throwMiddlewareError(ctx, fiber.StatusUnauthorized, &models.ErrorResponse{
				MessageID: messages.ERR_UNAUTHORIZED.Code,
				Message:   messages.ERR_UNAUTHORIZED.Text,
				Exception: "Missing Authorization header",
			})
		}

		const bearerPrefix = "Bearer "
		if len(tokenString) > len(bearerPrefix) && tokenString[:len(bearerPrefix)] == bearerPrefix {
			tokenString = tokenString[len(bearerPrefix):]
		} else {
			return throwMiddlewareError(ctx, fiber.StatusUnauthorized, &models.ErrorResponse{
				MessageID: messages.ERR_UNAUTHORIZED.Code,
				Message:   messages.ERR_UNAUTHORIZED.Text,
				Exception: "Authorization header must start with Bearer",
			})
		}

		claims, err := authSvc.VerifyJWT(tokenString, "access")
		if err != nil {
			return throwMiddlewareError(ctx, fiber.StatusUnauthorized, &models.ErrorResponse{
				MessageID: messages.ERR_UNAUTHORIZED.Code,
				Message:   messages.ERR_UNAUTHORIZED.Text,
				Exception: "Token verification failed: " + err.Error(),
			})
		}

		ctx.Locals("userID", claims.UserID)
		ctx.Locals("email", claims.Email)
		return ctx.Next()
	}
}

func throwMiddlewareError(ctx *fiber.Ctx, statusCode int, errResp *models.ErrorResponse) error {
	logger.Error(fmt.Sprintf("[%s] %s", errResp.MessageID, fmt.Sprintf("%s: %s", errResp.Message, errResp.Exception)))
	return ctx.Status(statusCode).JSON(errResp)
}
