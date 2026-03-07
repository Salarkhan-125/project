# forge/web/api/models/__init__.py
"""
Pydantic models for request/response validation
"""
from .user import UserCreate
from .campaign import CampaignCreateRequest
from .flag import FlagSubmitRequest
from .vulnerability_config import VulnerabilityConfig

__all__ = [
    'UserCreate',
    'CampaignCreateRequest', 
    'FlagSubmitRequest',
    'VulnerabilityConfig'
]