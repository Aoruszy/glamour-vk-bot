from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin
from app.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import AdminIdentity, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if payload.username != settings.admin_username or payload.password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль администратора.",
        )

    token = create_access_token(
        subject=settings.admin_username,
        secret=settings.auth_secret,
        expires_minutes=settings.auth_access_token_ttl_minutes,
    )
    return TokenResponse(access_token=token, username=settings.admin_username)


@router.get("/me", response_model=AdminIdentity)
def get_current_admin(_: dict[str, object] = Depends(require_admin)) -> AdminIdentity:
    settings = get_settings()
    return AdminIdentity(username=settings.admin_username)
