"""Authentication endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.core.config import get_settings
from app.services.auth import AuthService
from app.schemas.auth import TelegramAuthRequest, AuthResponse

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


@router.post("/telegram", response_model=AuthResponse)
async def authenticate_telegram(
    request: TelegramAuthRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Authenticate user with Telegram WebApp init data.

    Args:
        request: Telegram init data
        auth_service: Auth service

    Returns:
        JWT token and user ID
    """
    user, token = await auth_service.authenticate_telegram(
        request.init_data,
        settings.telegram_bot_token,
    )

    return AuthResponse(
        access_token=token,
        user_id=user.id,
    )
