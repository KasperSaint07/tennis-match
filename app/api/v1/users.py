"""User endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_repo
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import MeResponse, UpdateUserRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """Get current user profile.

    Args:
        current_user: Authenticated user

    Returns:
        User profile
    """
    return MeResponse(
        id=current_user.id,
        telegram_id=current_user.telegram_id,
        name=current_user.name,
        level=current_user.level,
        reliability_score=current_user.reliability_score,
        games_played=current_user.games_played,
        games_cancelled=current_user.games_cancelled,
        no_shows=current_user.no_shows,
    )


@router.patch("/me", response_model=MeResponse)
async def update_user_profile(
    request: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
) -> MeResponse:
    """Update current user profile.

    Args:
        request: Update data
        current_user: Authenticated user
        user_repo: User repository

    Returns:
        Updated user profile
    """
    updated = await user_repo.update(
        current_user,
        name=request.name,
        level=request.level,
    )

    return MeResponse(
        id=updated.id,
        telegram_id=updated.telegram_id,
        name=updated.name,
        level=updated.level,
        reliability_score=updated.reliability_score,
        games_played=updated.games_played,
        games_cancelled=updated.games_cancelled,
        no_shows=updated.no_shows,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserResponse:
    """Get user profile by ID.

    Args:
        user_id: User UUID
        user_repo: User repository

    Returns:
        User profile

    Raises:
        UserNotFoundException: If user not found
    """
    user = await user_repo.get_or_raise(user_id)

    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        name=user.name,
        level=user.level,
        reliability_score=user.reliability_score,
        games_played=user.games_played,
        games_cancelled=user.games_cancelled,
        no_shows=user.no_shows,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
