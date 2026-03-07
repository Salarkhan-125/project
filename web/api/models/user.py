# forge/web/api/models/user.py
"""
User-related Pydantic models
"""
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    password: str        # ← ADDED
    role: str = "individual"