package main

import (
	"log"
	apis "vehix/apis/auth"
	rentals "vehix/apis/rentals"
	users "vehix/apis/user"
	vehicles "vehix/apis/vehicles"
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
	auth.Post("/register", apis.RegisterHandler(authService))    // POST /v1/auth/register - Register/Sign Up
	auth.Post("/login", apis.LoginHandler(authService))          // POST /v1/auth/login - Login
	auth.Post("/refresh", apis.RefreshTokenHandler(authService)) // POST /v1/auth/refresh - Refresh Token

	// Protected routes
	v1.Use(middleware.Middleware(authService))
	/*
		=================================================================
		USER HANDLERS
		=================================================================
	*/
	v1.Get("/me", users.GetUserHandler(userService))       // GET 		/v1/me - Get user details
	v1.Patch("/me", users.UpdateUserHandler(userService))  // PATCH 	/v1/me - Update user details
	v1.Delete("/me", users.DeleteUserHandler(userService)) // DELETE	/v1/me - Delete user details
	v1.Get("/me/rentals", rentals.GetAllRentalsHandler)    // GET 		/v1/me/rentals - Get rentals by user

	/*
		=================================================================
		VEHICLE HANDLERS
		=================================================================
	*/
	v1.Get("/vehicles", vehicles.GetAllVehiclesHandler)       // GET 	/v1/vehicles/ - Get vehicles
	v1.Post("/vehicles", vehicles.PostVehiclesHandler)        // POST 	/v1/vehicles/ - Create a new vehicle entry
	v1.Get("/vehicles/:id", vehicles.GetVehicleByIDHandler)   // GET 	/v1/vehicles/:vehicleID - Get vehicle details
	v1.Patch("/vehicles/:id", vehicles.UpdateVehicleHandler)  // PATCH 	/v1/vehicles/:vehicleID- Update vehicle details
	v1.Delete("/vehicles/:id", vehicles.DeleteVehicleHandler) // DELETE /v1/vehicles/:vehicleID - Delete vehicle details
	v1.Get("/users/:id", rentals.GetAllRentalsHandler)        // GET 	/v1/vehicles/:vehicleID/rentals - Get rentals by vehicle

	/*
		=================================================================
		RENTALS HANDLERS
		=================================================================
	*/
	v1.Get("/rentals", rentals.GetAllRentalsHandler)        // GET 		/api/v1/rentals/ - Get rentals
	v1.Post("/rentals", rentals.PostRentalHandler)          // POST 	/api/v1/rentals/ - Create a new rental
	v1.Get("/rentals/:id", rentals.GetRentalByIDHandler)    // GET 		/api/v1/rentals/:rentalID - Get rental details
	v1.Patch("/rentals/:id", vehicles.UpdateVehicleHandler) // PATCH 	/api/v1/rentals/:rentalID - Update rental details
	v1.Delete("/rentals/:id", rentals.DeleteRentalHandler)  // DELETE 	/api/v1/rentals/:rentalID - Delete vehicle details

	log.Fatal(app.Listen(":3000"))
}
