# forge/web/api/routes/users.py
"""
User management endpoints
"""
from fastapi import APIRouter, HTTPException
import uuid
from web.api.models.user import UserCreate
from web.api.dependencies import db
from web.api.config import logger
from web.api.routes.auth import hash_password   # reuse the same helper from auth.py

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("")
async def create_user(user: UserCreate):
    """Create a new user"""
    user_id = f"user_{uuid.uuid4().hex[:12]}"

    user_data = {
        'user_id':             user_id,
        'username':            user.username,
        'email':               user.email,
        'password':            hash_password(user.password),  # CHANGED: hash before saving
        'role':                user.role,
        'total_points':        0,
        'machines_solved':     0,
        'campaigns_completed': 0,
    }

    try:
        created_user = db.create_user(user_data)
        created_user.pop('password', None)   # never return password in response
        return created_user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}")
async def get_user(user_id: str):
    """Get user details"""
    user = db.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rank = db.get_user_rank(user_id)
    user['rank'] = rank

    # Never send password back to frontend
    user.pop('password', None)

    return user


@router.get("/{user_id}/progress")
async def get_user_progress(user_id: str):
    """Get user's overall progress"""
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.pop('password', None)   # never expose password

    campaigns   = db.get_user_campaigns(user_id)
    submissions = db.get_user_submissions(user_id, limit=10)

    return {
        'user':               user,
        'campaigns':          campaigns,
        'recent_submissions': submissions
    }


@router.get("/{user_id}/campaigns")
async def get_user_campaigns_list(user_id: str):
    """Get list of user's campaigns — optimized with bulk progress fetch."""
    try:
        logger.info(f"Fetching campaigns for user: {user_id}")
        campaigns = db.get_user_campaigns(user_id)
        logger.info(f"Found {len(campaigns)} campaigns")

        if not campaigns:
            return campaigns

        # ✅ Fetch ALL progress records for this user in ONE query
        # instead of one query per campaign
        all_progress = db.get_all_user_progress(user_id)

        # Group progress by campaign_id in Python — zero extra DB calls
        progress_by_campaign = {}
        for p in all_progress:
            cid = p.get("campaign_id")
            if cid not in progress_by_campaign:
                progress_by_campaign[cid] = []
            progress_by_campaign[cid].append(p)

        for campaign in campaigns:
            try:
                campaign.pop("_id", None)
                cid = campaign["campaign_id"]
                progress_list = progress_by_campaign.get(cid, [])
                solved = sum(1 for p in progress_list if p.get("solved", False))
                campaign["machines_solved"] = solved
                campaign["progress_percentage"] = (
                    (solved / campaign["machine_count"] * 100)
                    if campaign.get("machine_count", 0) > 0 else 0
                )
            except Exception as e:
                logger.error(f"Error processing campaign {campaign.get('campaign_id')}: {e}")
                campaign["machines_solved"]     = 0
                campaign["progress_percentage"] = 0

        return campaigns
    except Exception as e:
        logger.error(f"Error in get_user_campaigns_list: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch campaigns: {str(e)}")