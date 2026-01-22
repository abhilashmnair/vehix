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

// User Messages
var (
	INFO_USER_REGISTER_SUCCESS = Message{Code: "USR001I", Text: "User registered successfully"}
	INFO_USER_LOGIN_SUCCESS    = Message{Code: "USR002I", Text: "Auth token retrieved successfully"}
	ERR_USER_ALREADY_EXISTS    = Message{Code: "USR003E", Text: "Email already in use"}
	ERR_USER_NOT_FOUND         = Message{Code: "USR004E", Text: "User not found"}
	ERR_INVALID_CREDENTIALS    = Message{Code: "USR005E", Text: "Invalid email or password"}
)
