from fastapi import APIRouter, status

from app.db import SessionDep
from app.errors import error_responses
from app.schemas.user import UserRead, UserSelfUpdate
from app.security import CurrentUser
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401),
)
def read_me(current: CurrentUser) -> UserRead:
    return UserRead.model_validate(current)


@router.patch(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 403, 409, 422),
)
def update_me(body: UserSelfUpdate, current: CurrentUser, session: SessionDep) -> UserRead:
    return UserRead.model_validate(users_service.update_self(session, current, body))
