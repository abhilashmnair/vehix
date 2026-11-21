import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.db import SessionDep
from app.errors import error_responses
from app.routers import API_PREFIX
from app.schemas.common import Page, PageParamsDep
from app.schemas.vehicle import VehicleCreate, VehicleFilters, VehicleRead, VehicleUpdate
from app.security import AdminUser, CurrentUser
from app.services import vehicles as vehicles_service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post(
    "",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403, 409, 422),
)
def create_vehicle(
    body: VehicleCreate, _admin: AdminUser, session: SessionDep, response: Response
) -> VehicleRead:
    vehicle = vehicles_service.create_vehicle(session, body)
    response.headers["Location"] = f"{API_PREFIX}/vehicles/{vehicle.id}"
    return VehicleRead.model_validate(vehicle)


@router.get(
    "",
    response_model=Page[VehicleRead],
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 422),
)
def list_vehicles(
    _user: CurrentUser,
    session: SessionDep,
    params: PageParamsDep,
    filters: Annotated[VehicleFilters, Query()],
) -> Page[VehicleRead]:
    vehicles, total = vehicles_service.list_vehicles(session, filters, params)
    return Page[VehicleRead](
        items=[VehicleRead.model_validate(v) for v in vehicles],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/{vehicle_id}",
    response_model=VehicleRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 404, 422),
)
def read_vehicle(vehicle_id: uuid.UUID, _user: CurrentUser, session: SessionDep) -> VehicleRead:
    return VehicleRead.model_validate(vehicles_service.get_vehicle(session, vehicle_id))


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_vehicle(
    vehicle_id: uuid.UUID, body: VehicleUpdate, _admin: AdminUser, session: SessionDep
) -> VehicleRead:
    return VehicleRead.model_validate(vehicles_service.update_vehicle(session, vehicle_id, body))
