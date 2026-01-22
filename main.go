package main

import (
	apis "vehix/apis/auth"
	rentals "vehix/apis/rentals"
	users "vehix/apis/users"
	vehicles "vehix/apis/vehicles"
	"vehix/core/database"
	"vehix/core/middleware"
	"vehix/core/service"
	"vehix/models"
	"log"

	"github.com/gofiber/fiber/v2"
)

func main() {

	db := database.Connect()
	db.AutoMigrate(
		&models.User{},
		&models.Vehicle{},
		&models.Rental{},
	)

	userService := service.NewUserService(db)

	app := fiber.New()

	// Public Endpoint
	app.Post("/register", apis.Register(userService)) // POST /api/v1/users - Register/Sign Up
	app.Post("/login", apis.Register(userService))    // POST /api/v1/users - Login

	// API v1 group with middleware
	v1 := app.Group("/v1", middleware.Middleware)

	/*
		=================================================================
		USER HANDLERS
		=================================================================
	*/

	v1.Get("/users", users.GetAllUsersHandler)                 // GET /api/v1/users - Get users
	v1.Get("/users/:id", users.GetUserByIDHandler)             // GET /api/v1/users/:userID - Get user details
	v1.Patch("/users/:id", users.UpdateUserHandler)            // PATCH /api/v1/users/:userID - Update user details
	v1.Delete("/users/:id", users.DeleteUserHandler)           // DELETE /api/v1/users/:userID - Delete user details
	v1.Get("/users/:id/rentals", rentals.GetAllRentalsHandler) // GET /api/v1/users/:userID/rentals - Get rentals by user

	/*
		=================================================================
		VEHICLE HANDLERS
		=================================================================
	*/

	v1.Get("/vehicles", vehicles.GetAllVehiclesHandler)       // GET /api/v1/vehicles/ - Get vehicles
	v1.Post("/vehicles", vehicles.PostVehiclesHandler)        // POST /api/v1/vehicles/ - Create a new vehicle entry
	v1.Get("/vehicles/:id", vehicles.GetVehicleByIDHandler)   // GET /api/v1/vehicles/:vehicleID - Get vehicle details
	v1.Patch("/vehicles/:id", vehicles.UpdateVehicleHandler)  // PATCH /api/v1/vehicles/:vehicleID- Update vehicle details
	v1.Delete("/vehicles/:id", vehicles.DeleteVehicleHandler) // DELETE /api/v1/vehicles/:vehicleID - Delete vehicle details
	v1.Get("/users/:id", rentals.GetAllRentalsHandler)        // GET /api/v1/vehicles/:vehicleID/rentals - Get rentals by vehicle

	/*
		=================================================================
		RENTALS HANDLERS
		=================================================================
	*/

	v1.Get("/rentals", rentals.GetAllRentalsHandler)        // GET /api/v1/rentals/ - Get rentals
	v1.Post("/rentals", rentals.PostRentalHandler)          // POST /api/v1/rentals/ - Create a new rental
	v1.Get("/rentals/:id", rentals.GetRentalByIDHandler)    // GET /api/v1/rentals/:rentalID - Get rental details
	v1.Patch("/rentals/:id", vehicles.UpdateVehicleHandler) // PATCH /api/v1/rentals/:rentalID - Update rental details
	v1.Delete("/rentals/:id", rentals.DeleteRentalHandler)  // DELETE /api/v1/rentals/:rentalID - Delete vehicle details

	log.Fatal(app.Listen(":3000"))
}
