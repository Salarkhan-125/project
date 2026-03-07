# forge/web/api/models/flag.py
"""
Flag submission Pydantic models
"""
from pydantic import BaseModel, Field


class FlagSubmitRequest(BaseModel):
    """
    Request body for POST /api/flags/validate

    campaign_id is required — it ensures the correct progress row is
    targeted when the same machine_id appears in multiple campaigns, and
    prevents progress rows from being written with a junk foreign key.
    """
    machine_id:  str = Field(..., min_length=1, max_length=64)
    campaign_id: str = Field(..., min_length=1, max_length=64)
    flag:        str = Field(..., min_length=1, max_length=256)
    user_id:     str = Field(..., min_length=1, max_length=64)