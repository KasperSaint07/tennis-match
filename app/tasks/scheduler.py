"""APScheduler setup and lifecycle management."""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

# Module-level bot instance used by notification tasks
_bot = None


def get_task_bot():
    """Return the bot instance configured for background tasks."""
    return _bot


def setup_scheduler(bot=None) -> None:
    """Register all jobs and start the scheduler.

    Args:
        bot: Optional aiogram Bot instance for sending notifications.
    """
    global _bot
    _bot = bot

    from app.tasks.game_status import (
        auto_cancel_unfilled,
        complete_games,
        detect_no_shows,
        start_games,
    )
    from app.tasks.notifications import send_game_reminders, send_last_call

    scheduler.add_job(
        start_games,
        trigger=IntervalTrigger(minutes=1),
        id="start_games",
        replace_existing=True,
    )
    scheduler.add_job(
        complete_games,
        trigger=IntervalTrigger(minutes=1),
        id="complete_games",
        replace_existing=True,
    )
    scheduler.add_job(
        detect_no_shows,
        trigger=IntervalTrigger(minutes=5),
        id="detect_no_shows",
        replace_existing=True,
    )
    scheduler.add_job(
        send_game_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="game_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_last_call,
        trigger=IntervalTrigger(minutes=5),
        id="last_call",
        replace_existing=True,
    )
    scheduler.add_job(
        auto_cancel_unfilled,
        trigger=IntervalTrigger(minutes=5),
        id="auto_cancel_unfilled",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
