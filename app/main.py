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

    # Bot + scheduler lifecycle
    @app.on_event("startup")
    async def startup():
        bot = None
        dp = None

        try:
            from app.bot.main import create_bot

            bot, dp = await create_bot()
            app.state.bot = bot
            app.state.dp = dp

            if settings.webhook_url:
                base = settings.webhook_url.rstrip("/")
                if not base.startswith("https://"):
                    base = f"https://{base}"
                webhook_endpoint = f"{base}/webhook/telegram"
                await bot.set_webhook(webhook_endpoint)
                logger.info("Telegram webhook registered: %s", webhook_endpoint)
            else:
                # Fallback: delete any stale webhook so polling works in dev
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("No WEBHOOK_URL set — webhook cleared (use bot_runner.py for local polling)")

        except Exception as exc:
            logger.warning("Bot unavailable: %s", exc)
            app.state.bot = None
            app.state.dp = None

        try:
            from app.tasks.scheduler import setup_scheduler

            setup_scheduler(bot=bot)
        except Exception as exc:
            logger.error("Scheduler failed to start: %s", exc)

    @app.on_event("shutdown")
    async def shutdown():
        bot = getattr(app.state, "bot", None)
        if bot is not None:
            try:
                if settings.webhook_url:
                    await bot.delete_webhook()
                await bot.session.close()
            except Exception as exc:
                logger.warning("Error closing bot session: %s", exc)

        from app.tasks.scheduler import shutdown_scheduler

        shutdown_scheduler()

    # Telegram webhook endpoint
    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        bot = getattr(app.state, "bot", None)
        dp = getattr(app.state, "dp", None)
        if bot is None or dp is None:
            return JSONResponse(status_code=503, content={"ok": False, "error": "bot not initialised"})

        from aiogram.types import Update

        try:
            body = await request.json()
            update = Update.model_validate(body)
            await dp.feed_update(bot, update)
            return {"ok": True}
        except Exception as exc:
            logger.exception("Telegram webhook update processing failed: %s", exc)
            return {"ok": False, "error": "update processing failed"}

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
