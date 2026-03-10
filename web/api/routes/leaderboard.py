# forge/web/api/routes/leaderboard.py
"""
Leaderboard endpoints — with 60-second in-memory cache.
"""
import time
from fastapi import APIRouter, Depends
from web.api.dependencies import db
from web.api.routes.auth import require_roles

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

# ── Simple in-memory cache ────────────────────────────────────────────────────
# Structure: { cache_key: {"data": [...], "expires_at": float} }
_leaderboard_cache: dict = {}
CACHE_TTL_SECONDS = 60  # leaderboard refreshes every 60 seconds


def _cache_key(limit: int, timeframe: str) -> str:
    return f"{timeframe}:{limit}"


def _get_cached(key: str):
    entry = _leaderboard_cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry["data"]
    return None


def _set_cached(key: str, data):
    _leaderboard_cache[key] = {
        "data":       data,
        "expires_at": time.time() + CACHE_TTL_SECONDS,
    }


# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def get_leaderboard(
    limit: int = 100,
    timeframe: str = "all_time",
    current_user: dict = Depends(require_roles("individual", "enterprise_staff")),
):
    """Get leaderboard — served from cache if available, refreshed every 60s."""
    key = _cache_key(limit, timeframe)

    # Return cached data if still fresh
    cached = _get_cached(key)
    if cached is not None:
        return {"timeframe": timeframe, "entries": cached, "cached": True}

    # Cache miss — query the database and store result
    leaderboard = db.get_leaderboard(limit=limit, timeframe=timeframe)
    _set_cached(key, leaderboard)

    return {"timeframe": timeframe, "entries": leaderboard, "cached": False}


@router.delete("/cache")
async def clear_leaderboard_cache(
    current_user: dict = Depends(require_roles("enterprise_admin")),
):
    """Manually clear the leaderboard cache (admin only)."""
    _leaderboard_cache.clear()
    return {"message": "Leaderboard cache cleared."}