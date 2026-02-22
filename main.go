package main

import (
	"log"
	authApis "vehix/apis/auth"
	rentalApi "vehix/apis/rentals"
	userApi "vehix/apis/user"
	vehicleApi "vehix/apis/vehicles"
	"vehix/core/database"
	"vehix/core/middleware"
	"vehix/core/service"
	"vehix/models"

	"github.com/gofiber/fiber/v2"
)

func main() {

	db := database.Connect()
	err := db.AutoMigrate(
		&models.UserModel{},
		&models.VehicleModel{},
		&models.RentalModel{},
	)
	if err != nil {
		log.Fatalf("Failed to auto-migrate database: %v", err)
	}

	authService := service.NewAuthService(db)
	userService := service.NewUserService(db)

	app := fiber.New()

	// API v1 group with middleware
	v1 := app.Group("/v1")

	// Auth Endpoints
	auth := v1.Group("/auth")
	auth.Post("/register", authApis.RegisterHandler(authService))                       // POST /v1/auth/register - Register/Sign Up
	auth.Post("/login", authApis.LoginHandler(authService))                             // POST /v1/auth/login - Login
	auth.Post("/refresh", authApis.RefreshAccessTokenHandler(authService, userService)) // POST /v1/auth/refresh - Refresh Token

	// Protected routes
	v1.Use(middleware.Middleware(authService))
	/*
		=================================================================
		USER HANDLERS
		=================================================================
	*/
	v1.Get("/me", userApi.GetUserHandler(userService))       // GET 		/v1/me - Get user details
	v1.Patch("/me", userApi.UpdateUserHandler(userService))  // PATCH 	/v1/me - Update user details
	v1.Delete("/me", userApi.DeleteUserHandler(userService)) // DELETE	/v1/me - Delete user details
	v1.Get("/me/rentals", rentalApi.GetAllRentalsHandler)    // GET 		/v1/me/rentals - Get rentals by user

	// Admin only routes
	v1.Get("/users", userApi.ListUsersHandler(userService)) // GET	/v1/users - Get all users

	/*
		=================================================================
		VEHICLE HANDLERS
		=================================================================
	*/
	v1.Get("/vehicles", vehicleApi.GetAllVehiclesHandler)       // GET 		/v1/vehicles/ - Get vehicles
	v1.Post("/vehicles", vehicleApi.PostVehiclesHandler)        // POST 		/v1/vehicles/ - Create a new vehicle entry
	v1.Get("/vehicles/:id", vehicleApi.GetVehicleByIDHandler)   // GET 		/v1/vehicles/:vehicleID - Get vehicle details
	v1.Patch("/vehicles/:id", vehicleApi.UpdateVehicleHandler)  // PATCH 	/v1/vehicles/:vehicleID- Update vehicle details
	v1.Delete("/vehicles/:id", vehicleApi.DeleteVehicleHandler) // DELETE	/v1/vehicles/:vehicleID - Delete vehicle details
	v1.Get("/users/:id", rentalApi.GetAllRentalsHandler)        // GET 		/v1/vehicles/:vehicleID/rentals - Get rentals by vehicle

	/*
		=================================================================
		RENTALS HANDLERS
		=================================================================
	*/
	v1.Get("/rentals", rentalApi.GetAllRentalsHandler)        // GET 	/api/v1/rentals/ - Get rentals
	v1.Post("/rentals", rentalApi.PostRentalHandler)          // POST 	/api/v1/rentals/ - Create a new rental
	v1.Get("/rentals/:id", rentalApi.GetRentalByIDHandler)    // GET 	/api/v1/rentals/:rentalID - Get rental details
	v1.Patch("/rentals/:id", vehicleApi.UpdateVehicleHandler) // PATCH 	/api/v1/rentals/:rentalID - Update rental details
	v1.Delete("/rentals/:id", rentalApi.DeleteRentalHandler)  // DELETE 	/api/v1/rentals/:rentalID - Delete vehicle details

	log.Fatal(app.Listen(":3000"))
}
