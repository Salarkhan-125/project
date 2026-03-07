

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Single helper for timezone-aware UTC now."""
    return datetime.now(timezone.utc)


# ============================================================================
# Enumerations
# ============================================================================

class DifficultyLevel(str, Enum):
    EASY   = "easy"
    MEDIUM = "medium"
    HARD   = "hard"
    EXPERT = "expert"
    INSANE = "insane"


class UserRole(str, Enum):
    """Single source of truth for RBAC role strings."""
    INDIVIDUAL       = "individual"
    ENTERPRISE_STAFF = "enterprise_staff"
    ENTERPRISE_ADMIN = "enterprise_admin"


# ============================================================================
# User Models
# ============================================================================

class User(BaseModel):
    """
    Individual user model — safe for API responses.
    password is intentionally absent; it must never appear in responses.
    """
    user_id:      str      = Field(..., description="Unique user identifier")
    full_name:    Optional[str] = Field(default=None)
    username:     str      = Field(..., description="Username")
    email:        str      = Field(..., description="Email address")
    role:         UserRole = Field(default=UserRole.INDIVIDUAL)
    account_type: str      = Field(default="individual")
    created_at:   datetime = Field(default_factory=_utcnow)

    # Merged from users_detail (populated at API layer)
    total_points:        int = Field(default=0)
    machines_solved:     int = Field(default=0)
    campaigns_completed: int = Field(default=0)
    current_streak:      int = Field(default=0)
    longest_streak:      int = Field(default=0)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    updated_at:       Optional[datetime] = Field(default=None)
    last_activity_at: Optional[datetime] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id":          "user_123",
                "username":         "hacker123",
                "email":            "hacker@example.com",
                "role":             "individual",
                "total_points":     500,
                "machines_solved":  5,
                "last_activity_at": "2024-01-15T10:30:00+00:00",
            }
        }


class OrgAdmin(BaseModel):
    """Enterprise admin model — safe for API responses."""
    user_id:         str
    email:           str
    org_name:        str
    organization_id: str
    role:            str = "enterprise_admin"
    account_type:    str = "enterprise"
    created_at:      datetime = Field(default_factory=_utcnow)
    updated_at:      Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class OrgStaff(BaseModel):
    """Enterprise staff model — safe for API responses."""
    user_id:         str
    full_name:       Optional[str] = None
    email:           str
    org_name:        str
    organization_id: str
    role:            str = "enterprise_staff"
    account_type:    str = "enterprise"
    created_at:      datetime = Field(default_factory=_utcnow)
    updated_at:      Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class UserDetail(BaseModel):
    """Extended profile/activity data for individual users."""
    user_id:             str
    full_name:           Optional[str] = None
    email:               Optional[str] = None
    total_points:        int = 0
    machines_solved:     int = 0
    campaigns_completed: int = 0
    current_streak:      int = 0
    longest_streak:      int = 0
    preferences:         Dict[str, Any] = Field(default_factory=dict)
    updated_at:          Optional[datetime] = None
    last_activity_at:    Optional[datetime] = None


class Organization(BaseModel):
    organization_id: str
    name:            str
    created_at:      datetime = Field(default_factory=_utcnow)


class UserProgress(BaseModel):
    """User progress for a specific machine in a specific campaign."""
    user_id:     str
    machine_id:  str
    campaign_id: str

    started_at:   datetime          = Field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    solved:       bool              = Field(default=False)

    attempts:   int = Field(default=0)
    hints_used: int = Field(default=0)

    time_spent: int           = Field(default=0)
    solve_time: Optional[int] = None

    points_earned: int = Field(default=0)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id":       "user_123",
                "machine_id":    "abc123",
                "campaign_id":   "campaign_001",
                "solved":        True,
                "attempts":      3,
                "points_earned": 200,
            }
        }


# ============================================================================
# Campaign Models
# ============================================================================

class CampaignStatus(str, Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class CampaignMachine(BaseModel):
    """
    Machine metadata within a campaign — safe for API responses.

    [FIX-M3] 'flag' / 'flag_hash' fields are intentionally absent.
    The API must never send flag data to the client.
    """
    machine_id:   str
    blueprint_id: str
    variant:      str
    difficulty:   int
    port:         Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "machine_id":   "mach_abc123",
                "blueprint_id": "bp_log4shell",
                "variant":      "log4j-rce-v1",
                "difficulty":   3,
                "port":         8080,
            }
        }


class Campaign(BaseModel):
    """Campaign model — safe for API responses."""
    campaign_id:   str
    campaign_name: str = Field(default="")
    user_id:       str

    difficulty:    int = Field(ge=1, le=5)
    machine_count: int

    machines: List[CampaignMachine] = Field(default_factory=list)  # [FIX-M3]

    status:       CampaignStatus    = Field(default=CampaignStatus.ACTIVE)
    created_at:   datetime          = Field(default_factory=_utcnow)
    started_at:   Optional[datetime] = None
    completed_at: Optional[datetime] = None

    machines_solved: int = Field(default=0)
    total_points:    int = Field(default=0)

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id":    "campaign_001",
                "user_id":        "user_123",
                "difficulty":     2,
                "machine_count":  5,
                "status":         "active",
                "machines_solved": 2,
            }
        }


# ============================================================================
# Flag Submission Models
# ============================================================================

class FlagSubmission(BaseModel):
    submission_id: str
    user_id:       str
    machine_id:    str
    campaign_id:   str

    submitted_flag: str   # the raw text the user typed
    correct:        bool
    submitted_at:   datetime = Field(default_factory=_utcnow)

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    points_awarded: int = Field(default=0)


class FlagSubmitRequest(BaseModel):
    """Inbound request body for POST /campaigns/{id}/machines/{id}/submit."""
    flag: str = Field(..., min_length=1, max_length=256)


# ============================================================================
# Hint Models
# ============================================================================

class HintUsage(BaseModel):
    user_id:      str
    machine_id:   str
    campaign_id:  str
    hint_number:  int
    hint_content: str
    used_at:      datetime = Field(default_factory=_utcnow)
    points_cost:  int      = Field(default=0)


# ============================================================================
# Achievement Models
# ============================================================================

class AchievementType(str, Enum):
    FIRST_BLOOD     = "first_blood"
    SPEED_DEMON     = "speed_demon"
    PERFECTIONIST   = "perfectionist"
    STREAK_MASTER   = "streak_master"
    CATEGORY_MASTER = "category_master"


class Achievement(BaseModel):
    achievement_id:   str
    name:             str
    description:      str
    achievement_type: AchievementType
    criteria:         Dict[str, Any]
    points:           int           = Field(default=0)
    badge_url:        Optional[str] = None


class UserAchievement(BaseModel):
    user_id:             str
    achievement_id:      str
    earned_at:           datetime        = Field(default_factory=_utcnow)
    related_machine_id:  Optional[str]   = None
    related_campaign_id: Optional[str]   = None


# ============================================================================
# Leaderboard Models
# ============================================================================

class LeaderboardEntry(BaseModel):
    user_id:  str
    username: str

    total_points:        int
    machines_solved:     int
    campaigns_completed: int
    average_solve_time:  Optional[float] = None

    rank: int

    last_activity_at: datetime  # [FIX-M1] was last_activity


class LeaderboardType(str, Enum):
    ALL_TIME = "all_time"
    MONTHLY  = "monthly"
    WEEKLY   = "weekly"
    DAILY    = "daily"
    CATEGORY = "category"


# ============================================================================
# Analytics Models
# ============================================================================

class MachineStats(BaseModel):
    """
    Aggregate statistics for a single machine across all campaigns.

    variant / difficulty are Optional: a machine_id can appear in multiple
    campaigns with different variants/difficulties, so these are not
    meaningful at the aggregate level.
    """
    machine_id: str

    variant:    Optional[str] = None
    difficulty: Optional[int] = None

    total_attempts: int   = 0
    unique_solvers: int   = 0
    solve_rate:     float = 0.0

    average_solve_time:  Optional[float] = None
    fastest_solve_time:  Optional[int]   = None
    average_hints_used:  float           = 0.0


class PlatformStats(BaseModel):
    """Platform-wide statistics — all fields align with get_platform_stats()."""
    total_users:        int
    active_users_today: int   # users with last_activity_at in last 24 h
    active_users_week:  int   # users with last_activity_at in last 7 days

    total_campaigns:     int
    active_campaigns:    int
    completed_campaigns: int

    total_machines: int
    total_solves:   int

    average_session_time:  float
    total_flags_submitted: int
    total_hints_used:      int

    last_updated: datetime = Field(default_factory=_utcnow)


# ============================================================================
# Session Models
# ============================================================================

class UserSession(BaseModel):
    session_id: str
    user_id:    str

    started_at:    datetime          = Field(default_factory=_utcnow)
    last_activity: datetime          = Field(default_factory=_utcnow)
    ended_at:      Optional[datetime] = None

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    machines_visited: List[str] = Field(default_factory=list)
    flags_submitted:  int       = 0
    hints_requested:  int       = 0


# ============================================================================
# Generated Machine Models (VulnForge pipeline)
# ============================================================================

class GeneratedMachineStatus(str, Enum):
    BUILDING = "building"
    READY    = "ready"
    STOPPED  = "stopped"
    FAILED   = "failed"


class GeneratedMachine(BaseModel):
    """
    Represents one machine produced by the VulnForge / bridge.py pipeline.

    [FIX-M2] flag_content and flag_hash are intentionally absent — the API
    must never return flag data to clients. Use database.verify_flag() at
    the submission endpoint to check a user's answer.
    """
    machine_id:   str
    job_id:       str
    user_id:      Optional[str] = None

    cve_id:      str
    difficulty:  str = Field(default="medium")

    port:         Optional[int] = None
    access_url:   Optional[str] = None
    machine_dir:  str
    service_name: Optional[str] = None

    flag_location: Optional[str] = None
    # flag_content / flag_hash intentionally omitted [FIX-M2]

    status:     GeneratedMachineStatus = Field(default=GeneratedMachineStatus.READY)
    created_at: datetime               = Field(default_factory=_utcnow)
    ready_at:   Optional[datetime]     = None

    class Config:
        json_schema_extra = {
            "example": {
                "machine_id":    "machine_a1b2c3d4",
                "job_id":        "job_uuid_here",
                "user_id":       "user_123",
                "cve_id":        "CVE-2021-44228",
                "difficulty":    "hard",
                "port":          8080,
                "access_url":    "http://localhost:8080",
                "machine_dir":   "/machines/machine_a1b2c3d4",
                "service_name":  "log4j",
                "flag_location": "/root/flag.txt",
                "status":        "ready",
            }
        }