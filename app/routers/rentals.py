import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.db import SessionDep
from app.errors import error_responses
from app.models import RentalStatus
from app.routers import API_PREFIX
from app.schemas.common import Page, PageParamsDep
from app.schemas.rental import RentalCreate, RentalFilters, RentalRead, RentalUpdate
from app.security import AdminUser, CurrentUser
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


@router.get(
    "",
    response_model=Page[RentalRead],
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 422),
)
def list_rentals(
    current: CurrentUser,
    session: SessionDep,
    params: PageParamsDep,
    filters: Annotated[RentalFilters, Query()],
) -> Page[RentalRead]:
    rentals, total = rentals_service.list_rentals(session, current, filters, params)
    return Page[RentalRead](
        items=[RentalRead.model_validate(r) for r in rentals],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/{rental_id}",
    response_model=RentalRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 404, 422),
)
def read_rental(rental_id: uuid.UUID, current: CurrentUser, session: SessionDep) -> RentalRead:
    return RentalRead.model_validate(rentals_service.get_rental(session, current, rental_id))


@router.patch(
    "/{rental_id}",
    response_model=RentalRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 404, 409, 422),
)
def update_rental(
    rental_id: uuid.UUID, body: RentalUpdate, current: CurrentUser, session: SessionDep
) -> RentalRead:
    return RentalRead.model_validate(
        rentals_service.update_rental(session, current, rental_id, body)
    )


@router.post(
    "/{rental_id}/cancel",
    response_model=RentalRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 404, 409, 422),
)
def cancel_rental(rental_id: uuid.UUID, current: CurrentUser, session: SessionDep) -> RentalRead:
    rental = rentals_service.transition_rental(session, current, rental_id, RentalStatus.CANCELLED)
    return RentalRead.model_validate(rental)


@router.post(
    "/{rental_id}/activate",
    response_model=RentalRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 403, 404, 409, 422),
)
def activate_rental(rental_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> RentalRead:
    rental = rentals_service.transition_rental(session, admin, rental_id, RentalStatus.ACTIVE)
    return RentalRead.model_validate(rental)


@router.post(
    "/{rental_id}/complete",
    response_model=RentalRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 403, 404, 409, 422),
)
def complete_rental(rental_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> RentalRead:
    rental = rentals_service.transition_rental(session, admin, rental_id, RentalStatus.COMPLETED)
    return RentalRead.model_validate(rental)


@router.delete(
    "/{rental_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404, 422),
)
def delete_rental(rental_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> Response:
    rentals_service.delete_rental(session, admin, rental_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
