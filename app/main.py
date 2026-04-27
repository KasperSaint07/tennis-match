"""FastAPI application factory and configuration."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core import AppException, get_settings
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

settings = get_settings()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="API-first platform for organizing tennis games in Astana",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler for AppException
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Handle application exceptions."""
        error_detail = ErrorDetail(
            code=exc.code.value,
            message=exc.message,
            details=exc.details,
        )
        error_response = ErrorResponse(error=error_detail)

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
        )

    # Exception handler for generic exceptions
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        from app.core.exceptions import ErrorCode

        error_detail = ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR.value,
            message="Internal server error",
            details={},
        )
        error_response = ErrorResponse(error=error_detail)

        if settings.debug:
            error_response.error.details = {"exception": str(exc)}

        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(),
        )

    # Health check
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok"}

    # Scheduler lifecycle
    @app.on_event("startup")
    async def startup_scheduler():
        from app.tasks.scheduler import setup_scheduler

        bot = None
        try:
            from app.bot.main import create_bot

            bot, _ = await create_bot()
        except Exception as exc:
            logger.warning("Bot unavailable for scheduler notifications: %s", exc)

        setup_scheduler(bot=bot)

    @app.on_event("shutdown")
    async def shutdown_scheduler():
        from app.tasks.scheduler import shutdown_scheduler

        shutdown_scheduler()

    # Include API routers
    from app.api.v1 import router as api_v1_router

    app.include_router(
        api_v1_router,
        prefix=settings.api_v1_prefix,
    )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
