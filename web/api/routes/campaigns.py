# forge/web/api/routes/campaigns.py
"""
Campaign management endpoints - DISABLED
VulnForge uses individual lab generation via /api/lab/chat instead.
To re-enable: restore old generator.py and template_engine.py files.
"""
from fastapi import APIRouter, HTTPException, Depends
from web.api.dependencies import db
from web.api.config import logger
from web.api.routes.auth import require_roles

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("")
async def list_campaigns_disabled(current_user: dict = Depends(require_roles("enterprise_staff"))):
    """Campaigns are disabled - use VulnForge Lab Chat instead"""
    raise HTTPException(
        status_code=501,
        detail="Campaign system disabled. Use /api/lab/chat for individual lab generation."
    )


@router.post("")
async def create_campaign_disabled(current_user: dict = Depends(require_roles("enterprise_staff"))):
    """Campaigns are disabled - use VulnForge Lab Chat instead"""
    raise HTTPException(
        status_code=501,
        detail="Campaign system disabled. Use /api/lab/chat for individual lab generation."
    )


@router.get("/{campaign_id}")
async def get_campaign_disabled(campaign_id: str, current_user: dict = Depends(require_roles("enterprise_staff"))):
    """Campaigns are disabled - use VulnForge Lab Chat instead"""
    raise HTTPException(
        status_code=501,
        detail="Campaign system disabled. Use /api/lab/chat for individual lab generation."
    )
