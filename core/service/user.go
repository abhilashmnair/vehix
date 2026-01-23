package service

import (
	"context"
	"errors"
	"time"
	"vehix/core/messages"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
	"gorm.io/gorm"
)

type UserService interface {
	GetUser(ctx context.Context, userID string) (int, *models.UserResponse, *models.ErrorResponse)
}

type UserServiceImpl struct {
	db *gorm.DB
}

func NewUserService(db *gorm.DB) UserService {
	return &UserServiceImpl{db: db}
}

func (s *UserServiceImpl) GetUser(ctx context.Context, userID string) (int, *models.UserResponse, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var user models.UserModel
	err := db.Where("id = ?", userID).First(&user).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return fiber.StatusNotFound, nil, &models.ErrorResponse{
				MessageID: messages.ERR_USER_NOT_FOUND.Code,
				Message:   messages.ERR_USER_NOT_FOUND.Text,
				Exception: err.Error(),
			}
		} else {
			return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
				MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
				Message:   messages.ERR_UNEXPECTED_ERROR.Text,
				Exception: err.Error(),
			}
		}
	}

	return fiber.StatusOK, &models.UserResponse{
		ID:        user.ID,
		Name:      user.Name,
		Email:     user.Email,
		CreatedAt: user.CreatedAt.Format(time.RFC3339),
		UpdatedAt: user.UpdatedAt.Format(time.RFC3339),
	}, nil
}
