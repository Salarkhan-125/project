# forge/web/api/cleanup.py
"""
Background Cleanup Task
Runs on a schedule inside FastAPI's lifespan to automatically delete
expired rows from:
  - password_reset_tokens
  - pending_registrations

How to wire it into your FastAPI app (in main.py or app.py):

    from contextlib import asynccontextmanager
    from web.api.cleanup import start_cleanup_task

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(start_cleanup_task())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(lifespan=lifespan)

If your app already has a lifespan context manager, just add the two
lines (create_task + cancel) inside your existing one.
"""
import asyncio
import logging
from web.api.dependencies import db

logger = logging.getLogger(__name__)

# How often the cleanup loop runs (seconds).
# 30 minutes is a good default — short enough to keep the table clean,
# long enough to never put any noticeable load on the DB.
CLEANUP_INTERVAL_SECONDS = 30 * 60   # 30 minutes


async def run_cleanup() -> None:
    """
    Perform one cleanup pass — delete expired tokens and registrations.
    Errors are caught and logged so a DB hiccup never crashes the loop.
    """
    try:
        deleted_tokens = db.cleanup_expired_tokens()
        if deleted_tokens:
            logger.info(f"[cleanup] Deleted {deleted_tokens} expired password reset token(s).")
    except Exception as exc:
        logger.error(f"[cleanup] Failed to clean password_reset_tokens: {exc}", exc_info=True)

    try:
        deleted_regs = db.cleanup_expired_registrations()
        if deleted_regs:
            logger.info(f"[cleanup] Deleted {deleted_regs} expired pending registration(s).")
    except Exception as exc:
        logger.error(f"[cleanup] Failed to clean pending_registrations: {exc}", exc_info=True)


async def start_cleanup_task() -> None:
    """
    Infinite async loop that calls run_cleanup() every CLEANUP_INTERVAL_SECONDS.

    - Runs an immediate cleanup pass on startup so stale rows from a previous
      server run are cleared right away (not after the first 30-minute wait).
    - asyncio.sleep() yields control back to the event loop between runs,
      so this never blocks any request handling.
    - The task is cancelled cleanly when FastAPI shuts down via lifespan.
    """
    logger.info("[cleanup] Background cleanup task started.")

    # Immediate first pass on startup
    await run_cleanup()

    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            await run_cleanup()
        except asyncio.CancelledError:
            logger.info("[cleanup] Background cleanup task stopped.")
            raise   # re-raise so asyncio knows the task ended cleanly
        except Exception as exc:
            # Unexpected error in the loop itself — log and keep running
            logger.error(f"[cleanup] Unexpected error in cleanup loop: {exc}", exc_info=True)
            await asyncio.sleep(60)   # back off for 1 minute before retrying