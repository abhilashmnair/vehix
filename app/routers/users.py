import uuid

from fastapi import APIRouter, Response, status

from app.db import SessionDep
from app.errors import error_responses
from app.routers import API_PREFIX
from app.schemas.common import Page, PageParamsDep
from app.schemas.user import UserCreate, UserRead, UserSelfUpdate
from app.security import AdminUser, CurrentUser
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


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403, 409, 422),
)
def create_user(
    body: UserCreate, _admin: AdminUser, session: SessionDep, response: Response
) -> UserRead:
    user = users_service.create_user(session, body)
    response.headers["Location"] = f"{API_PREFIX}/users/{user.id}"
    return UserRead.model_validate(user)


@router.get(
    "",
    response_model=Page[UserRead],
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 403, 422),
)
def list_users(_admin: AdminUser, session: SessionDep, params: PageParamsDep) -> Page[UserRead]:
    users, total = users_service.list_users(session, params)
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 403, 404, 422),
)
def read_user(user_id: uuid.UUID, _admin: AdminUser, session: SessionDep) -> UserRead:
    return UserRead.model_validate(users_service.get_user(session, user_id))
