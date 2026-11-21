from fastapi import APIRouter, status

from app.db import SessionDep
from app.errors import error_responses
from app.schemas.auth import LoginRequest, TokenRead
from app.security import create_access_token
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenRead,
    status_code=status.HTTP_200_OK,
    responses=error_responses(401, 422),
)
def login(body: LoginRequest, session: SessionDep) -> TokenRead:
    user = auth_service.authenticate(session, body.email, body.password)
    token, expires_in = create_access_token(user.id, user.role)
    return TokenRead(access_token=token, expires_in=expires_in)
