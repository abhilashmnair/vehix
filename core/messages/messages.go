package messages

type Message struct {
	Code string
	Text string
}

var (
	INFO_STARTING_SERVER = Message{Code: "SYS001I", Text: "Starting server"}
	INFO_SERVER_UP       = Message{Code: "SYS002I", Text: "Server is up and running"}
	ERR_SERVER_STARTUP   = Message{Code: "SYS003E", Text: "Failed to start server"}
	ERR_UNEXPECTED_ERROR = Message{Code: "SYS004E", Text: "Unexpected Error"}
	ERR_BAD_REQUEST      = Message{Code: "SYS005E", Text: "Bad Request"}
)

// Auth Messages
var (
	INFO_REFRESH_TOKEN_SUCCESS = Message{Code: "AUTH001I", Text: "Generated refresh token successfully"}
	ERR_INVALID_REFRESH_TOKEN  = Message{Code: "AUTH002E", Text: "Refresh token invalid or expired"}

	INFO_ACCESS_TOKEN_SUCCESS = Message{Code: "AUTH003I", Text: "Generated access token successfully"}
	ERR_INVALID_ACCESS_TOKEN  = Message{Code: "AUTH004E", Text: "Access token invalid or expired"}

	ERR_UNAUTHORIZED = Message{Code: "AUTH006E", Text: "Missing or invalid token"}
)

// User Messages
var (
	INFO_USER_REGISTER_SUCCESS = Message{Code: "USR001I", Text: "User registered successfully"}
	ERR_INVALID_CREDENTIALS    = Message{Code: "USR002E", Text: "Invalid email or password"}

	INFO_USER_LOGIN_SUCCESS = Message{Code: "USR003I", Text: "Login successful"}
	ERR_USER_LOGIN_FAILED   = Message{Code: "USR004E", Text: "Login failed"}

	ERR_USER_ALREADY_EXISTS = Message{Code: "USR005E", Text: "Email already in use"}
	ERR_USER_NOT_FOUND      = Message{Code: "USR006E", Text: "User not found"}

	INFO_USER_FETCH_SUCCESS = Message{Code: "USR007I", Text: "User fetched successfully"}

	INFO_USER_UPDATE_SUCCESS = Message{Code: "USR008I", Text: "User updated successfully"}

	ERR_EMAIL_ALREADY_EXISTS = Message{Code: "USR009E", Text: "Email already in use"}
)
