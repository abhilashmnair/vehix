package models

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

// Auth Payload

type LoginSuccess struct {
	AccessToken  string `json:"access_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
	RefreshToken string `json:"refresh_token"`
}

type RefreshTokenRequest struct {
	RefreshToken string `json:"refresh_token"`
}

// User Payload

type RegisterUserPayload struct {
	Name     string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
}

type LoginUserPayload struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}
