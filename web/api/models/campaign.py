# forge/web/api/models/campaign.py
"""
Campaign-related Pydantic models
"""
from pydantic import BaseModel
from typing import Optional, List

class CampaignCreateRequest(BaseModel):
    user_id: str
    campaign_name: str
    difficulty: int = 2
    count: Optional[int] = None
    selected_blueprints: Optional[List[str]] = None