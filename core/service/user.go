package service

import (
	"vehix/core/messages"
	"vehix/models"
	"context"
	"errors"

	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

type UserService interface {
	RegisterUser(ctx context.Context, payload models.CreateUserPayload) (int, *models.ErrorResponse)
}

type UserServiceImpl struct {
	db *gorm.DB
}

func NewUserService(db *gorm.DB) UserService {
	return &UserServiceImpl{db: db}
}

func (s *UserServiceImpl) RegisterUser(ctx context.Context, payload models.CreateUserPayload) (int, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var existingUser models.User
	err := db.Where("email = ?", payload.Email).First(&existingUser).Error
	if err == nil {
		return fiber.StatusConflict, &models.ErrorResponse{
			MessageID: messages.ERR_USER_ALREADY_EXISTS.Code,
			Message:   messages.ERR_USER_ALREADY_EXISTS.Text,
		}
	}

	if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
		return fiber.StatusNotFound, &models.ErrorResponse{
			MessageID: messages.ERR_USER_NOT_FOUND.Code,
			Message:   messages.ERR_USER_NOT_FOUND.Text,
			Exception: err.Error(),
		}
	}

	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(payload.Password), bcrypt.DefaultCost)
	if err != nil {
		return fiber.StatusInternalServerError, &models.ErrorResponse{
			MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
			Message:   messages.ERR_UNEXPECTED_ERROR.Text,
			Exception: err.Error(),
		}
	}

	user := models.User{
		Name:     payload.Name,
		Email:    payload.Email,
		Password: string(hashedPassword),
	}

	if err = db.Create(&user).Error; err != nil {
		return fiber.StatusInternalServerError, &models.ErrorResponse{
			MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
			Message:   messages.ERR_UNEXPECTED_ERROR.Text,
			Exception: err.Error(),
		}
	}

	return fiber.StatusCreated, nil
}
