# forge/web/api/routes/stats.py
from fastapi import APIRouter, Query
from typing import Optional
from web.api.dependencies import db
from web.api.config import logger
from sqlalchemy import desc
import importlib.util, sys as _sys, pathlib as _pl
_db_path = _pl.Path(__file__).resolve().parent.parent.parent / "database" / "database.py"
_spec = importlib.util.spec_from_file_location("_hf_db", _db_path)
_hf_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hf_db)
SessionLocal    = _hf_db.SessionLocal
SubmissionTable = _hf_db.SubmissionTable
UserTable       = _hf_db.UserTable

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_statistics(user_id: Optional[str] = Query(None)):
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
async def get_solve_feed(limit: int = 20):
    """
    Returns recent correct flag submissions with username,
    machine_id, points, and whether it was first blood.
    """
    session = SessionLocal()
    try:
        # Get recent correct submissions joined with username
        rows = (
            session.query(
                SubmissionTable.submission_id,
                SubmissionTable.user_id,
                SubmissionTable.machine_id,
                SubmissionTable.points_awarded,
                SubmissionTable.submitted_at,
                UserTable.username,
            )
            .outerjoin(UserTable, SubmissionTable.user_id == UserTable.user_id)
            .filter(SubmissionTable.correct == True)
            .filter(SubmissionTable.machine_id != "seed_machine")  # exclude dummy seed
            .order_by(desc(SubmissionTable.submitted_at))
            .limit(limit)
            .all()
        )

        # Find first blood per machine (earliest correct submission)
        from sqlalchemy import func
        first_bloods = (
            session.query(
                SubmissionTable.machine_id,
                func.min(SubmissionTable.submitted_at).label("first_at"),
            )
            .filter(SubmissionTable.correct == True)
            .group_by(SubmissionTable.machine_id)
            .all()
        )
        first_blood_map = {r.machine_id: r.first_at for r in first_bloods}

        feed = []
        for r in rows:
            is_first_blood = (
                first_blood_map.get(r.machine_id) == r.submitted_at
            )
            feed.append({
                "submission_id": r.submission_id,
                "user_id":       r.user_id,
                "username":      r.username or r.user_id,
                "machine_id":    r.machine_id,
                "points":        r.points_awarded or 0,
                "submitted_at":  r.submitted_at.isoformat() if r.submitted_at else None,
                "first_blood":   is_first_blood,
            })

        return {"feed": feed}
    except Exception as e:
        logger.error(f"Feed error: {e}", exc_info=True)
        return {"feed": []}
    finally:
        session.close()
