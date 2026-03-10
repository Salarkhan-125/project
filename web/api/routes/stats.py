# forge/web/api/routes/stats.py
from fastapi import APIRouter, Query, Depends
from typing import Optional
from web.api.dependencies import db
from web.api.config import logger
from sqlalchemy import desc, func
from web.api.routes.auth import get_current_user
from web.database.database import SessionLocal, SubmissionTable, UserTable

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_statistics(user_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    platform_stats = db.get_platform_stats()

    if user_id:
        try:
            user_campaigns = db.get_user_campaigns(user_id)
            platform_stats['total_campaigns'] = len(user_campaigns)
        except Exception as e:
            logger.error(f"✗ Failed to get user campaign count for {user_id}: {e}")
            platform_stats['total_campaigns'] = 0
    else:
        pass

    try:
        machines = db.list_generated_machines(status='ready')
        platform_stats['total_machines'] = len(machines)
    except Exception as e:
        logger.error(f"✗ Failed to count machines: {e}")
        platform_stats['total_machines'] = 0

    return platform_stats


@router.get("/feed")
async def get_solve_feed(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """
    Returns recent correct flag submissions with username,
    machine_id, points, and whether it was first blood.
    Optimized: single query with subquery for first blood detection.
    """
    session = SessionLocal()
    try:
        # Build first-blood subquery — finds the earliest submission per machine
        # This runs as a subquery inside the main query, not as a separate round-trip
        first_blood_subq = (
            session.query(
                SubmissionTable.machine_id,
                func.min(SubmissionTable.submitted_at).label("first_at"),
            )
            .filter(SubmissionTable.correct == True)
            .group_by(SubmissionTable.machine_id)
            .subquery()
        )

        # Single main query — joins username and first-blood status together
        rows = (
            session.query(
                SubmissionTable.submission_id,
                SubmissionTable.user_id,
                SubmissionTable.machine_id,
                SubmissionTable.points_awarded,
                SubmissionTable.submitted_at,
                UserTable.username,
                (SubmissionTable.submitted_at == first_blood_subq.c.first_at).label("is_first_blood"),
            )
            .outerjoin(UserTable, SubmissionTable.user_id == UserTable.user_id)
            .outerjoin(
                first_blood_subq,
                SubmissionTable.machine_id == first_blood_subq.c.machine_id,
            )
            .filter(SubmissionTable.correct == True)
            .filter(SubmissionTable.machine_id != "seed_machine")
            .order_by(desc(SubmissionTable.submitted_at))
            .limit(limit)
            .all()
        )

        feed = []
        for r in rows:
            feed.append({
                "submission_id": r.submission_id,
                "user_id":       r.user_id,
                "username":      r.username or r.user_id,
                "machine_id":    r.machine_id,
                "points":        r.points_awarded or 0,
                "submitted_at":  r.submitted_at.isoformat() if r.submitted_at else None,
                "first_blood":   bool(r.is_first_blood),
            })

        return {"feed": feed}
    except Exception as e:
        logger.error(f"Feed error: {e}", exc_info=True)
        return {"feed": []}
    finally:
        session.close()
