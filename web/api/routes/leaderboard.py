# forge/web/api/routes/leaderboard.py
"""
Leaderboard endpoints
"""
from fastapi import APIRouter
from web.api.dependencies import db
from web.api.routes.auth import require_roles

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def get_leaderboard(
    limit: int = 100,
    timeframe: str = 'all_time',
    current_user: dict = require_roles("individual", "enterprise_staff"),
):
    """Get leaderboard"""
    leaderboard = db.get_leaderboard(limit=limit, timeframe=timeframe)
    return {
        'timeframe': timeframe,
        'entries': leaderboard
    }