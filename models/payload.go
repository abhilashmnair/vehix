package models

import (
	"github.com/google/uuid"
)

// Common Responses

type SuccessResponse struct {
	MessageID string `json:"messageID"`
	Message   string `json:"message"`
}

type ErrorResponse struct {
	MessageID string `json:"messageID"`
	Message   string `json:"message"`
	Exception string `json:"exception,omitempty"`
}

// User Payload

type CreateUserPayload struct {
	Name     string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
}

type UserResponse struct {
	ID    uuid.UUID `json:"id"`
	Name  string    `json:"username"`
	Email string    `json:"email"`
}
