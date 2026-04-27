"""Game endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_game_service
from app.enums.game import GameFormat, GameLevel
from app.models.user import User
from app.services.game import GameService
from app.schemas.game import (
    CancelGameRequest,
    CancelGameResponse,
    CheckinRequest,
    CheckinResponse,
    CreateGameRequest,
    GameListResponse,
    GameResponse,
    JoinGameRequest,
    JoinGameResponse,
    LeaveGameRequest,
    LeaveGameResponse,
)

router = APIRouter(prefix="/games", tags=["games"])


@router.post("", response_model=GameResponse, status_code=201)
async def create_game(
    request: CreateGameRequest,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service),
) -> GameResponse:
    """Create a new game.

    Args:
        request: Game creation data
        current_user: Authenticated user (host)
        game_service: Game service

    Returns:
        Created game
    """
    game = await game_service.create_game(
        user=current_user,
        location=request.location,
        scheduled_at=request.scheduled_at,
        format=request.format,
        level=request.level,
        price_per_player=request.price_per_player,
    )

    return GameResponse(
        id=game.id,
        host_id=game.host_id,
        location=game.location,
        scheduled_at=game.scheduled_at,
        format=game.format,
        level=game.level,
        max_players=game.max_players,
        price_per_player=game.price_per_player,
        status=game.status,
        telegram_chat_link=game.telegram_chat_link,
        created_at=game.created_at,
        updated_at=game.updated_at,
    )


@router.get("", response_model=GameListResponse)
async def list_games(
    level: Optional[GameLevel] = Query(None),
    format: Optional[GameFormat] = Query(None),
    date: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    game_service: GameService = Depends(get_game_service),
) -> GameListResponse:
    """List available games with filters.

    Args:
        level: Filter by skill level
        format: Filter by format (SINGLES/DOUBLES)
        date: Filter by date
        limit: Pagination limit
        offset: Pagination offset
        game_service: Game service

    Returns:
        Paginated list of games
    """
    games, total = await game_service.get_games(
        level=level,
        format=format,
        date_filter=date,
        limit=limit,
        offset=offset,
    )

    items = [
        GameResponse(
            id=game.id,
            host_id=game.host_id,
            location=game.location,
            scheduled_at=game.scheduled_at,
            format=game.format,
            level=game.level,
            max_players=game.max_players,
            price_per_player=game.price_per_player,
            status=game.status,
            telegram_chat_link=game.telegram_chat_link,
            created_at=game.created_at,
            updated_at=game.updated_at,
        )
        for game in games
    ]

    return GameListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: UUID,
    game_service: GameService = Depends(get_game_service),
) -> GameResponse:
    """Get game details.

    Args:
        game_id: Game UUID
        game_service: Game service

    Returns:
        Game details

    Raises:
        GameNotFoundException: If game not found
    """
    game = await game_service.get_game(game_id)
    if not game:
        from app.core.exceptions import GameNotFoundException

        raise GameNotFoundException(str(game_id))

    return GameResponse(
        id=game.id,
        host_id=game.host_id,
        location=game.location,
        scheduled_at=game.scheduled_at,
        format=game.format,
        level=game.level,
        max_players=game.max_players,
        price_per_player=game.price_per_player,
        status=game.status,
        telegram_chat_link=game.telegram_chat_link,
        created_at=game.created_at,
        updated_at=game.updated_at,
    )


@router.post("/{game_id}/join", response_model=JoinGameResponse, status_code=201)
async def join_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service),
) -> JoinGameResponse:
    """Join a game.

    Args:
        game_id: Game UUID
        current_user: Authenticated user
        game_service: Game service

    Returns:
        Join result

    Raises:
        GameNotAvailableException: Game not available
        GameAlreadyJoinedException: User already joined
        GameFullException: No free slots
        InsufficientBalanceException: Insufficient balance
    """
    result = await game_service.join_game(current_user, game_id)
    return JoinGameResponse(**result)


@router.post("/{game_id}/leave", response_model=LeaveGameResponse)
async def leave_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service),
) -> LeaveGameResponse:
    """Leave a game.

    Args:
        game_id: Game UUID
        current_user: Authenticated user
        game_service: Game service

    Returns:
        Leave result

    Raises:
        GameCannotLeaveException: User is host or not a participant
    """
    result = await game_service.leave_game(current_user, game_id)
    return LeaveGameResponse(**result)


@router.post("/{game_id}/cancel", response_model=CancelGameResponse)
async def cancel_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service),
) -> CancelGameResponse:
    """Cancel a game (host only).

    Args:
        game_id: Game UUID
        current_user: Authenticated user (must be host)
        game_service: Game service

    Returns:
        Cancellation result

    Raises:
        GameCannotCancelException: User is not host or wrong status
    """
    result = await game_service.cancel_game(current_user, game_id)
    return CancelGameResponse(**result)


@router.post("/{game_id}/checkin", response_model=CheckinResponse)
async def checkin_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service),
) -> CheckinResponse:
    """Check in to a game.

    Args:
        game_id: Game UUID
        current_user: Authenticated user
        game_service: Game service

    Returns:
        Check-in result

    Raises:
        GamePastCutoffException: Outside check-in window
    """
    checked_in_at = await game_service.checkin(current_user, game_id)
    return CheckinResponse(
        game_id=game_id,
        checked_in_at=checked_in_at,
    )
