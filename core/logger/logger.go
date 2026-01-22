package logger

import (
	"log"
	"os"
)

type LogLevel string

const (
	INFO  LogLevel = "INFO"
	WARN  LogLevel = "WARN"
	ERROR LogLevel = "ERROR"
	DEBUG LogLevel = "DEBUG"
)

/* ANSI color codes */
const (
	colorReset  = "\033[0m"
	colorRed    = "\033[31m"
	colorGreen  = "\033[32m"
	colorYellow = "\033[33m"
	colorBlue   = "\033[34m"
	colorCyan   = "\033[36m"
)

var debugEnabled = os.Getenv("LOG_LEVEL") == "DEBUG"

func colorForLevel(level LogLevel) string {
	switch level {
	case INFO:
		return colorGreen
	case WARN:
		return colorYellow
	case ERROR:
		return colorRed
	case DEBUG:
		return colorCyan
	default:
		return colorReset
	}
}

func logWithLevel(level LogLevel, msg string) {
	color := colorForLevel(level)

	log.Printf("%s[%s]%s %s",
		color,
		level,
		colorReset,
		msg,
	)
}

func Info(msg string) {
	logWithLevel(INFO, msg)
}

func Warn(msg string) {
	logWithLevel(WARN, msg)
}

func Error(msg string) {
	logWithLevel(ERROR, msg)
}

func Debug(msg string) {
	if debugEnabled {
		logWithLevel(DEBUG, msg)
	}
}
