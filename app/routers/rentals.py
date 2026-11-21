from fastapi import APIRouter, Response, status

from app.db import SessionDep
from app.errors import error_responses
from app.routers import API_PREFIX
from app.schemas.rental import RentalCreate, RentalRead
from app.security import CurrentUser
from app.services import rentals as rentals_service

router = APIRouter(prefix="/rentals", tags=["rentals"])


@router.post(
    "",
    response_model=RentalRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403, 404, 409, 422),
)
def create_rental(
    body: RentalCreate, current: CurrentUser, session: SessionDep, response: Response
) -> RentalRead:
    rental = rentals_service.create_rental(session, current, body)
    response.headers["Location"] = f"{API_PREFIX}/rentals/{rental.id}"
    return RentalRead.model_validate(rental)
