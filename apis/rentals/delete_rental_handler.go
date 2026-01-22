package rentals

import "github.com/gofiber/fiber/v2"

func DeleteRentalHandler(c *fiber.Ctx) error {
	return c.SendString("DeleteRentalHandler called, ID: " + c.Params("id"))
}
