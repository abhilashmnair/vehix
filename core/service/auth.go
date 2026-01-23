package service

import (
	"context"
	"errors"
	"fmt"
	"os"
	"time"
	"vehix/core/messages"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

var (
	jwtSecret       = os.Getenv("JWT_SECRET")
	accessTokenTTL  = time.Hour * 1
	refreshTokenTTL = time.Hour * 24 * 7
)

type Claims struct {
	UserID string `json:"sub"`
	Email  string `json:"email"`
	Type   string `json:"typ"`
	jwt.RegisteredClaims
}

type AuthService interface {
	Register(ctx context.Context, payload models.RegisterUserPayload) (int, *models.ErrorResponse)
	Login(ctx context.Context, payload models.LoginUserPayload) (int, *models.LoginSuccess, *models.ErrorResponse)
	GenerateToken(userID, email string) (*models.LoginSuccess, error)
	GenerateAccessToken(userID, email string) (string, error)
	VerifyJWT(tokenString, expectedType string) (*Claims, error)
}

type AuthServiceImpl struct {
	db *gorm.DB
}

func NewAuthService(db *gorm.DB) AuthService {
	return &AuthServiceImpl{db: db}
}

func (s *AuthServiceImpl) Register(ctx context.Context, payload models.RegisterUserPayload) (int, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var existingUser models.UserModel
	err := db.Where("email = ?", payload.Email).First(&existingUser).Error
	if err == nil {
		return fiber.StatusConflict, &models.ErrorResponse{
			MessageID: messages.ERR_USER_ALREADY_EXISTS.Code,
			Message:   messages.ERR_USER_ALREADY_EXISTS.Text,
		}
	} else {
		if !errors.Is(err, gorm.ErrRecordNotFound) {
			return fiber.StatusNotFound, &models.ErrorResponse{
				MessageID: messages.ERR_USER_NOT_FOUND.Code,
				Message:   messages.ERR_USER_NOT_FOUND.Text,
				Exception: err.Error(),
			}
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

	user := models.UserModel{
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

func (s *AuthServiceImpl) Login(ctx context.Context, payload models.LoginUserPayload) (int, *models.LoginSuccess, *models.ErrorResponse) {
	db := s.db.WithContext(ctx)

	var user models.UserModel
	if err := db.Where("email = ?", payload.Email).Find(&user).Error; err != nil {
		return fiber.StatusNotFound, nil, &models.ErrorResponse{
			MessageID: messages.ERR_USER_NOT_FOUND.Code,
			Message:   messages.ERR_USER_NOT_FOUND.Text,
			Exception: err.Error(),
		}
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(payload.Password)); err != nil {
		return fiber.StatusBadRequest, nil, &models.ErrorResponse{
			MessageID: messages.ERR_INVALID_CREDENTIALS.Code,
			Message:   messages.ERR_INVALID_CREDENTIALS.Text,
			Exception: err.Error(),
		}
	}

	loginResp, err := s.GenerateToken(user.ID.String(), user.Email)
	if err != nil {
		return fiber.StatusInternalServerError, nil, &models.ErrorResponse{
			MessageID: messages.ERR_USER_LOGIN_FAILED.Code,
			Message:   messages.ERR_USER_LOGIN_FAILED.Text,
			Exception: err.Error(),
		}
	}

	return fiber.StatusOK, loginResp, nil
}

func (s *AuthServiceImpl) GenerateToken(userID, email string) (*models.LoginSuccess, error) {
	accessToken, err := s.GenerateAccessToken(userID, email)
	if err != nil {
		return nil, err
	}
	refreshToken, err := s.GenerateRefreshToken(userID)
	if err != nil {
		return nil, err
	}

	return &models.LoginSuccess{
		AccessToken:  accessToken,
		TokenType:    "Bearer",
		RefreshToken: refreshToken,
		ExpiresIn:    3600,
	}, nil
}

func (s *AuthServiceImpl) GenerateAccessToken(userID, email string) (string, error) {

	claims := Claims{
		UserID: userID,
		Email:  email,
		Type:   "access",
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(accessTokenTTL)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString([]byte(jwtSecret))

	return signed, err
}

func (s *AuthServiceImpl) GenerateRefreshToken(userID string) (string, error) {

	claims := Claims{
		UserID: userID,
		Type:   "refresh",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(refreshTokenTTL)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		}}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString([]byte(jwtSecret))

	return signed, err
}

func (s *AuthServiceImpl) VerifyJWT(tokenString, expectedType string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(
		tokenString,
		&Claims{},
		func(token *jwt.Token) (any, error) {
			if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
			}
			return []byte(jwtSecret), nil
		},
	)

	if err != nil {
		return nil, err
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid token")
	}

	if claims.Type != expectedType {
		return nil, fmt.Errorf("invalid token type: %s", claims.Type)
	}

	return claims, nil
}
