from fastapi import APIRouter, Response, status

from app.db import SessionDep
from app.errors import error_responses
from app.routers import API_PREFIX
from app.schemas.vehicle import VehicleCreate, VehicleRead
from app.security import AdminUser
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
