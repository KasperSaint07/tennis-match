"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, games, users, wallet

router = APIRouter()

# Include sub-routers
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(games.router)
router.include_router(wallet.router)

__all__ = ["router"]
