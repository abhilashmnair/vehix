package service

import (
	"context"
	"errors"
	"time"
	"vehix/core/messages"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

type UserService interface {
	GetUser(ctx context.Context, userID string) (int, *models.UserResponse, *models.ErrorResponse)
	ListUsers(ctx context.Context) (int, *[]models.UserResponse, *models.ErrorResponse)
	UpdateUser(ctx context.Context, userID string, req *models.UpdateUserPayload) (int, *models.UserResponse, *models.ErrorResponse)
	DeleteUser(ctx context.Context, userID string) (int, *models.ErrorResponse)
}

type UserServiceImpl struct {
	db *gorm.DB
}

func NewUserService(db *gorm.DB) UserService {
	return &UserServiceImpl{db: db}
}

func (s *UserServiceImpl) GetUser(ctx context.Context, userID string) (int, *models.UserResponse, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var user models.User
	err := db.Where("id = ?", userID).First(&user).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return fiber.StatusNotFound, nil, &models.ErrorResponse{
				MessageID: messages.ERR_USER_NOT_FOUND.Code,
				Message:   messages.ERR_USER_NOT_FOUND.Text,
				Exception: "user not found",
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
		Role:      user.Role,
		CreatedAt: user.CreatedAt.Format(time.RFC3339),
		UpdatedAt: user.UpdatedAt.Format(time.RFC3339),
	}, nil
}

func (s *UserServiceImpl) DeleteUser(ctx context.Context, userID string) (int, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	result := db.Where("id = ?", userID).Delete(&models.User{})

	if result.Error != nil {
		return fiber.StatusInternalServerError, &models.ErrorResponse{
			MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
			Message:   messages.ERR_UNEXPECTED_ERROR.Text,
			Exception: result.Error.Error(),
		}
	}

	if result.RowsAffected == 0 {
		return fiber.StatusNotFound, &models.ErrorResponse{
			MessageID: messages.ERR_USER_NOT_FOUND.Code,
			Message:   messages.ERR_USER_NOT_FOUND.Text,
			Exception: "user not found",
		}
	}

	return fiber.StatusNoContent, nil
}

func (s *UserServiceImpl) UpdateUser(ctx context.Context, userID string, req *models.UpdateUserPayload) (int, *models.UserResponse, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var user models.User
	err := db.Where("id = ?", userID).First(&user).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return fiber.StatusNotFound, nil, &models.ErrorResponse{
				MessageID: messages.ERR_USER_NOT_FOUND.Code,
				Message:   messages.ERR_USER_NOT_FOUND.Text,
				Exception: "user not found",
			}
		} else {
			return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
				MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
				Message:   messages.ERR_UNEXPECTED_ERROR.Text,
				Exception: err.Error(),
			}
		}
	}

	if req.Name != nil {
		user.Name = *req.Name
	}

	if req.Email != nil && *req.Email != user.Email {
		var count int64
		if err := db.Model(&models.User{}).
			Where("email = ? AND id <> ?", *req.Email, user.ID).
			Count(&count).Error; err != nil {
			return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
				MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
				Message:   messages.ERR_UNEXPECTED_ERROR.Text,
				Exception: err.Error(),
			}
		}

		if count > 0 {
			return fiber.StatusConflict, nil, &models.ErrorResponse{
				MessageID: messages.ERR_EMAIL_ALREADY_EXISTS.Code,
				Message:   messages.ERR_EMAIL_ALREADY_EXISTS.Text,
			}
		}

		user.Email = *req.Email
	}

	if req.Password != nil {
		hashedPassword, err := bcrypt.GenerateFromPassword([]byte(*req.Password), bcrypt.DefaultCost)
		if err != nil {
			return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
				MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
				Message:   messages.ERR_UNEXPECTED_ERROR.Text,
				Exception: err.Error(),
			}
		}

		user.Password = string(hashedPassword)
	}

	err = db.Updates(&user).Error
	if err != nil {
		return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
			MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
			Message:   messages.ERR_UNEXPECTED_ERROR.Text,
			Exception: err.Error(),
		}
	}

	return fiber.StatusOK, &models.UserResponse{
		ID:        user.ID,
		Name:      user.Name,
		Email:     user.Email,
		Role:      user.Role,
		CreatedAt: user.CreatedAt.Format(time.RFC3339),
		UpdatedAt: user.UpdatedAt.Format(time.RFC3339),
	}, nil
}

func (s *UserServiceImpl) ListUsers(ctx context.Context) (int, *[]models.UserResponse, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var users []models.User
	if err := db.Find(&users).Error; err != nil {
		return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
			MessageID: messages.ERR_UNEXPECTED_ERROR.Code,
			Message:   messages.ERR_UNEXPECTED_ERROR.Text,
			Exception: err.Error(),
		}
	}

	var response []models.UserResponse
	for _, u := range users {
		response = append(response, models.UserResponse{
			ID:        u.ID,
			Name:      u.Name,
			Email:     u.Email,
			Role:      u.Role,
			CreatedAt: u.CreatedAt.Format(time.RFC3339Nano),
			UpdatedAt: u.UpdatedAt.Format(time.RFC3339Nano),
		})
	}

	return fiber.StatusOK, &response, nil
}
