
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

import hashlib
import hmac
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, JSON,
    create_engine, func, text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ============================================================
# Configuration — fail fast, never fall back to root/localhost
# ============================================================

def _require_env(name: str) -> str:
    """Raise immediately if a required environment variable is absent."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            "Check your .env file."
        )
    return value


DATABASE_URL   = _require_env('DATABASE_URL')          # [FIX-C3]
FLAG_HMAC_KEY  = _require_env('FLAG_HMAC_KEY').encode()  # [FIX-C4]


# ============================================================
# Flag hashing utilities  [FIX-C4]
# ============================================================

def hash_flag(flag: str) -> str:
    """
    Return the HMAC-SHA256 hex digest of a flag.
    This is the value that must be stored in the DB.
    Never store raw flag text.
    """
    return hmac.new(FLAG_HMAC_KEY, flag.strip().encode(), hashlib.sha256).hexdigest()


def verify_flag(submitted: str, stored_hash: str) -> bool:
    """
    Constant-time comparison of a submitted flag against the stored hash.
    Use this in the flag-submission route instead of plain string equality.
    """
    return hmac.compare_digest(hash_flag(submitted), stored_hash)


# ============================================================
# Engine & Session Setup
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=False,
    connect_args={"connect_timeout": 10}
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# ============================================================
# Helpers
# ============================================================

def _now() -> datetime:
    """Single source of truth for timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}


def _machine_row_to_dict(row) -> Dict[str, Any]:
    return {
        'machine_id':   row.machine_id,
        'blueprint_id': row.blueprint_id,
        'variant':      row.variant,
        'difficulty':   row.difficulty,
        # flag_hash intentionally excluded — never send the hash to clients
        'port':         row.port,
    }


# ============================================================
# Allowed columns for proxy classes  [FIX-S1]
# ============================================================

_USER_READABLE_COLS = frozenset({
    'user_id', 'username', 'email', 'full_name', 'role',
    'account_type', 'created_at',
    # 'password' deliberately absent — proxies must never filter/expose it
})

_USER_WRITABLE_COLS = frozenset({
    'username', 'email', 'full_name',
    # 'password' must be updated via a dedicated change-password method only
})

_CAMPAIGN_READABLE_COLS = frozenset({
    'campaign_id', 'campaign_name', 'user_id', 'difficulty',
    'machine_count', 'status', 'machines_solved', 'total_points',
    'created_at', 'started_at', 'completed_at',
})

_CAMPAIGN_WRITABLE_COLS = frozenset({
    'campaign_name', 'status', 'machines_solved', 'total_points',
    'started_at', 'completed_at',
})

_PROGRESS_READABLE_COLS = frozenset({
    'user_id', 'machine_id', 'campaign_id', 'solved',
    'attempts', 'hints_used', 'time_spent', 'solve_time',
    'points_earned', 'started_at', 'completed_at',
})

_SUBMISSION_READABLE_COLS = frozenset({
    'submission_id', 'user_id', 'machine_id', 'campaign_id',
    'correct', 'points_awarded', 'submitted_at',
    # 'submitted_flag' omitted — proxies should not filter by raw flag text
})


# ============================================================
# Table Definitions
# ============================================================

class OrganizationTable(Base):
    __tablename__ = 'organizations'

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    organization_id = Column(String(64),  unique=True, nullable=False, index=True)
    name            = Column(String(256), nullable=False)
    created_at      = Column(DateTime,    default=_now)


class OrgAdminTable(Base):
    """Enterprise admin accounts — one per organization."""
    __tablename__ = 'org_admins'

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    user_id         = Column(String(64),  unique=True, nullable=False, index=True)
    email           = Column(String(256), unique=True, nullable=False, index=True)
    password        = Column(String(256), nullable=False)
    org_name        = Column(String(256), nullable=False)
    organization_id = Column(
        String(64),
        ForeignKey('organizations.organization_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    role            = Column(String(32),  nullable=False, default='enterprise_admin')
    account_type    = Column(String(32),  nullable=False, default='enterprise')
    created_at      = Column(DateTime,    default=_now)
    updated_at      = Column(DateTime,    default=_now, onupdate=_now)
    last_activity_at = Column(DateTime,   default=_now, index=True)


class OrgStaffTable(Base):
    """Enterprise staff accounts — teachers / staff created by enterprise admins."""
    __tablename__ = 'org_staff'

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    user_id         = Column(String(64),  unique=True, nullable=False, index=True)
    full_name       = Column(String(256), nullable=True)
    email           = Column(String(256), unique=True, nullable=False, index=True)
    password        = Column(String(256), nullable=False)
    org_name        = Column(String(256), nullable=False)
    organization_id = Column(
        String(64),
        ForeignKey('organizations.organization_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    role            = Column(String(32),  nullable=False, default='enterprise_staff')
    account_type    = Column(String(32),  nullable=False, default='enterprise')
    created_at      = Column(DateTime,    default=_now)
    updated_at      = Column(DateTime,    default=_now, onupdate=_now)
    last_activity_at = Column(DateTime,   default=_now, index=True)


class UserTable(Base):
    """Individual user accounts only — no enterprise accounts."""
    __tablename__ = 'users'

    id               = Column(Integer,    primary_key=True, autoincrement=True)
    user_id          = Column(String(64), unique=True, nullable=False, index=True)
    full_name        = Column(String(256),nullable=True)
    username         = Column(String(128),unique=True, nullable=False)
    email            = Column(String(256),unique=True, nullable=False, index=True)
    password         = Column(String(256),nullable=False)
    role             = Column(String(32), nullable=False, default='individual')
    account_type     = Column(String(32), nullable=False, default='individual')
    created_at       = Column(DateTime, default=_now)


class UsersDetailTable(Base):
    """Extended profile / activity data for individual users."""
    __tablename__ = 'users_detail'

    id               = Column(Integer,    primary_key=True, autoincrement=True)
    user_id          = Column(
        String(64),
        ForeignKey('users.user_id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name        = Column(String(256), nullable=True)
    email            = Column(String(256), nullable=True)
    total_points     = Column(Integer, default=0)
    machines_solved  = Column(Integer, default=0)
    campaigns_completed = Column(Integer, default=0)
    current_streak   = Column(Integer, default=0)
    longest_streak   = Column(Integer, default=0)
    preferences      = Column(JSON, default=dict)
    updated_at       = Column(DateTime, default=_now, onupdate=_now)
    last_activity_at = Column(DateTime, default=_now, index=True)


class CampaignTable(Base):
    __tablename__ = 'campaigns'

    id            = Column(Integer,     primary_key=True, autoincrement=True)
    campaign_id   = Column(String(64),  unique=True, nullable=False, index=True)
    campaign_name = Column(String(256), nullable=False)
    user_id       = Column(String(64),  nullable=False, index=True)
    difficulty    = Column(Integer,     nullable=False)
    machine_count = Column(Integer,     nullable=False)
    status        = Column(String(32),  nullable=False, default='active')

    machines_solved = Column(Integer, default=0)
    total_points    = Column(Integer, default=0)

    created_at   = Column(DateTime, default=_now, index=True)
    started_at   = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    deleted_at   = Column(DateTime, nullable=True, index=True)  # [FIX-R1] soft delete

    __table_args__ = (
        Index('idx_campaign_user_created', 'user_id', 'created_at'),
    )


class CampaignMachineTable(Base):
    """One row per machine in a campaign."""
    __tablename__ = 'campaign_machines'

    id           = Column(Integer,     primary_key=True, autoincrement=True)
    campaign_id  = Column(
        String(64),
        ForeignKey('campaigns.campaign_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    machine_id   = Column(String(64),  nullable=False)
    blueprint_id = Column(String(128), nullable=False)
    variant      = Column(String(256), nullable=False)
    difficulty   = Column(Integer,     nullable=False)
    flag_hash    = Column(String(64),  nullable=False)  # [FIX-C4] HMAC-SHA256 hex digest
    port         = Column(Integer,     nullable=True)
    position     = Column(Integer,     nullable=False, default=0)
    created_at   = Column(DateTime,    default=_now)

    __table_args__ = (
        Index('idx_cm_campaign_position', 'campaign_id', 'position'),
        Index('idx_cm_machine_id',        'machine_id'),
        Index('idx_cm_campaign_machine',  'campaign_id', 'machine_id', unique=True),
    )


class ProgressTable(Base):
    __tablename__ = 'progress'

    id          = Column(Integer,  primary_key=True, autoincrement=True)
    user_id     = Column(String(64), nullable=False)
    machine_id  = Column(String(64), nullable=False)
    campaign_id = Column(String(64), nullable=False)

    solved      = Column(Boolean, default=False)
    attempts    = Column(Integer, default=0)
    hints_used  = Column(Integer, default=0)

    time_spent  = Column(Integer, default=0)
    solve_time  = Column(Integer, nullable=True)

    points_earned = Column(Integer, default=0)

    started_at   = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            'idx_progress_user_machine_campaign',
            'user_id', 'machine_id', 'campaign_id',
            unique=True,
        ),
        Index('idx_progress_campaign',   'user_id', 'campaign_id'),
        Index('idx_progress_machine_id', 'machine_id'),  # [FIX-P3]
    )


class SubmissionTable(Base):
    __tablename__ = 'flag_submissions'

    id            = Column(Integer,    primary_key=True, autoincrement=True)
    submission_id = Column(String(64), unique=True, nullable=False)
    user_id       = Column(String(64), nullable=False, index=True)
    machine_id    = Column(String(64), nullable=False)
    campaign_id   = Column(String(64), nullable=False)

    submitted_flag = Column(Text,    nullable=False)
    correct        = Column(Boolean, nullable=False)
    points_awarded = Column(Integer, default=0)

    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text,       nullable=True)

    submitted_at = Column(DateTime, default=_now, index=True)


class HintUsageTable(Base):
    __tablename__ = 'hint_usage'

    id           = Column(Integer,    primary_key=True, autoincrement=True)
    user_id      = Column(String(64), nullable=False, index=True)
    machine_id   = Column(String(64), nullable=False)
    campaign_id  = Column(String(64), nullable=False)
    hint_number  = Column(Integer,    nullable=False)
    hint_content = Column(Text,       nullable=False)
    points_cost  = Column(Integer,    default=0)
    used_at      = Column(DateTime,   default=_now)

    __table_args__ = (
        Index(
            'idx_hint_usage_unique',
            'user_id', 'machine_id', 'campaign_id', 'hint_number',
            unique=True,
        ),
    )


class AchievementTable(Base):
    __tablename__ = 'achievements'

    id               = Column(Integer,    primary_key=True, autoincrement=True)
    achievement_id   = Column(String(64), unique=True, nullable=False)
    name             = Column(String(128),nullable=False)
    description      = Column(Text,       nullable=True)
    achievement_type = Column(String(64), nullable=False)
    criteria         = Column(JSON,       default=dict)
    points           = Column(Integer,    default=0)
    badge_url        = Column(String(512),nullable=True)


class UserAchievementTable(Base):
    __tablename__ = 'user_achievements'

    id                  = Column(Integer,    primary_key=True, autoincrement=True)
    user_id             = Column(String(64), nullable=False, index=True)
    achievement_id      = Column(String(64), nullable=False)
    earned_at           = Column(DateTime,   default=_now)
    related_machine_id  = Column(String(64), nullable=True)
    related_campaign_id = Column(String(64), nullable=True)


class SessionTable(Base):
    """One row per user session."""
    __tablename__ = 'sessions'

    id           = Column(Integer,    primary_key=True, autoincrement=True)
    session_id   = Column(String(64), unique=True, nullable=False, index=True)
    user_id      = Column(String(64), nullable=False, index=True)
    ip_address   = Column(String(64), nullable=True)
    user_agent   = Column(Text,       nullable=True)

    flags_submitted  = Column(Integer, default=0)
    hints_requested  = Column(Integer, default=0)
    started_at       = Column(DateTime, default=_now, index=True)
    last_activity    = Column(DateTime, default=_now)
    ended_at         = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_session_user_started', 'user_id', 'started_at'),
    )


class SessionMachineVisitTable(Base):
    """One row per machine visited per session."""
    __tablename__ = 'session_machine_visits'

    id         = Column(Integer,    primary_key=True, autoincrement=True)
    session_id = Column(
        String(64),
        ForeignKey('sessions.session_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    machine_id = Column(String(64), nullable=False)
    visited_at = Column(DateTime,   default=_now, nullable=False)

    __table_args__ = (
        Index('idx_smv_session',         'session_id'),
        Index('idx_smv_machine',         'machine_id'),
        Index('idx_smv_session_machine', 'session_id', 'machine_id', unique=True),
    )


class PasswordResetTokenTable(Base):
    __tablename__ = 'password_reset_tokens'

    id         = Column(Integer,     primary_key=True, autoincrement=True)
    token      = Column(String(128), unique=True, nullable=False, index=True)
    email      = Column(String(256), nullable=False, index=True)
    expires_at = Column(DateTime,    nullable=False, index=True)
    created_at = Column(DateTime,    default=_now)


class PendingRegistrationTable(Base):
    """
    Stores pre-verified registration data.
    IMPORTANT: 'password' here must already be bcrypt-hashed by the
    calling route before it is written here. Never store plaintext passwords.
    """
    __tablename__ = 'pending_registrations'

    id         = Column(Integer,     primary_key=True, autoincrement=True)
    username   = Column(String(128), nullable=False)
    full_name  = Column(String(256), nullable=True)
    email      = Column(String(256), nullable=False, index=True)
    password   = Column(String(256), nullable=False)  # must be pre-hashed
    role       = Column(String(32),  nullable=False, default='individual')
    otp        = Column(String(4),   nullable=False)
    attempts   = Column(Integer,     default=0)
    expires_at = Column(DateTime,    nullable=False, index=True)
    created_at = Column(DateTime,    default=_now)


class GeneratedMachineTable(Base):
    """
    Permanent MySQL record for every machine produced by the
    VulnForge / bridge.py pipeline.

    flag_content has been replaced with flag_hash. [FIX-C4]
    bridge.py must call hash_flag() before writing here.
    """
    __tablename__ = 'generated_machines'

    id           = Column(Integer,     primary_key=True, autoincrement=True)
    machine_id   = Column(String(64),  unique=True, nullable=False, index=True)
    job_id       = Column(String(64),  nullable=False, index=True)
    user_id      = Column(String(64),  nullable=True,  index=True)

    cve_id       = Column(String(64),  nullable=False)
    difficulty   = Column(String(32),  nullable=False, default='medium')

    port         = Column(Integer,     nullable=True)
    access_url   = Column(String(512), nullable=True)
    machine_dir  = Column(String(512), nullable=False)
    service_name = Column(String(128), nullable=True)

    flag_location = Column(String(256), nullable=True)
    flag_hash     = Column(String(64),  nullable=True)   # [FIX-C4] HMAC-SHA256

    status     = Column(String(32), nullable=False, default='ready', index=True)
    created_at = Column(DateTime,   default=_now, index=True)
    ready_at   = Column(DateTime,   nullable=True)
    deleted_at = Column(DateTime,   nullable=True, index=True)  # [FIX-R1] soft delete

    __table_args__ = (
        Index('idx_gm_user_status',  'user_id', 'status'),
        Index('idx_gm_user_created', 'user_id', 'created_at'),
    )


class StuDetailTable(Base):
    """
    Stores student records grouped by class_name.
    Each row = one student in a class, created by an enterprise_staff user.
    Data is scoped by staff_user_id + enterprise_id so universities are isolated.
    """
    __tablename__ = 'stu_detail'

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    class_name     = Column(String(256), nullable=False)
    roll_no        = Column(String(128), nullable=False)
    student_name   = Column(String(256), nullable=False)
    father_name    = Column(String(256), nullable=True)
    section        = Column(String(128), nullable=True)

    staff_user_id  = Column(
        String(64),
        ForeignKey('org_staff.user_id', ondelete='CASCADE'),
        nullable=False,
    )
    enterprise_id  = Column(
        String(64),
        ForeignKey('organizations.organization_id', ondelete='CASCADE'),
        nullable=False,
    )

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index('idx_stu_staff',       'staff_user_id'),
        Index('idx_stu_enterprise',  'enterprise_id'),
        Index('idx_stu_roll',        'roll_no'),
        Index('idx_stu_class_staff', 'class_name', 'staff_user_id'),
    )


# ============================================================
# DatabaseManager
# ============================================================

class DatabaseManager:

    def __init__(self):
        Base.metadata.create_all(bind=engine)

    def _get_session(self) -> Session:
        return SessionLocal()

    # ----------------------------------------------------------
    # Transaction context manager  [FIX-R2]
    # ----------------------------------------------------------

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """
        Yield a single SQLAlchemy session for multi-step operations
        that must succeed or fail atomically.

        Usage:
            with db.transaction() as session:
                db._some_op(session, ...)
                db._other_op(session, ...)
            # auto-committed or rolled back on exception
        """
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ----------------------------------------------------------
    # PRIVATE — Machine helpers (campaigns)
    # ----------------------------------------------------------

    def _insert_machines(
        self,
        session: Session,
        campaign_id: str,
        machines: List[Dict[str, Any]],
    ) -> None:
        for position, m in enumerate(machines):
            # Caller must supply 'flag' as plaintext; we hash it here.
            raw_flag = m.get('flag', '')
            row = CampaignMachineTable(
                campaign_id  = campaign_id,
                machine_id   = m['machine_id'],
                blueprint_id = m['blueprint_id'],
                variant      = m['variant'],
                difficulty   = m['difficulty'],
                flag_hash    = hash_flag(raw_flag),  # [FIX-C4]
                port         = m.get('port'),
                position     = position,
                created_at   = _now(),
            )
            session.add(row)

    def _fetch_machines(
        self, session: Session, campaign_id: str
    ) -> List[Dict[str, Any]]:
        rows = (
            session.query(CampaignMachineTable)
            .filter_by(campaign_id=campaign_id)
            .order_by(CampaignMachineTable.position)
            .all()
        )
        return [_machine_row_to_dict(r) for r in rows]

    def _fetch_machines_batch(
        self, session: Session, campaign_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """[FIX-P2] Load machines for many campaigns in one query."""
        if not campaign_ids:
            return {}
        rows = (
            session.query(CampaignMachineTable)
            .filter(CampaignMachineTable.campaign_id.in_(campaign_ids))
            .order_by(
                CampaignMachineTable.campaign_id,
                CampaignMachineTable.position,
            )
            .all()
        )
        result: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            result.setdefault(r.campaign_id, []).append(_machine_row_to_dict(r))
        return result

    def _attach_machines(
        self,
        session: Session,
        campaign_dict: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if campaign_dict is None:
            return None
        campaign_dict['machines'] = self._fetch_machines(
            session, campaign_dict['campaign_id']
        )
        return campaign_dict

    # ----------------------------------------------------------
    # USER OPERATIONS (individual accounts)
    # ----------------------------------------------------------

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an individual user + its users_detail row."""
        now = _now()
        with self._get_session() as session:
            row = UserTable(
                user_id      = user_data['user_id'],
                full_name    = user_data.get('full_name', ''),
                username     = user_data['username'],
                email        = user_data['email'],
                password     = user_data.get('password', ''),
                role         = 'individual',
                account_type = 'individual',
                created_at   = now,
            )
            session.add(row)
            session.flush()

            detail = UsersDetailTable(
                user_id         = user_data['user_id'],
                full_name       = user_data.get('full_name', ''),
                email           = user_data['email'],
                total_points    = user_data.get('total_points', 0),
                machines_solved = user_data.get('machines_solved', 0),
                campaigns_completed = user_data.get('campaigns_completed', 0),
                current_streak  = 0,
                longest_streak  = 0,
                preferences     = user_data.get('preferences', {}),
                updated_at      = now,
                last_activity_at = now,
            )
            session.add(detail)
            session.commit()
            session.refresh(row)
            session.refresh(detail)

            result = _row_to_dict(row)
            detail_dict = _row_to_dict(detail)
            result.update({
                'total_points':        detail_dict.get('total_points', 0),
                'machines_solved':     detail_dict.get('machines_solved', 0),
                'campaigns_completed': detail_dict.get('campaigns_completed', 0),
                'current_streak':      detail_dict.get('current_streak', 0),
                'longest_streak':      detail_dict.get('longest_streak', 0),
                'preferences':         detail_dict.get('preferences', {}),
                'updated_at':          detail_dict.get('updated_at'),
                'last_activity_at':    detail_dict.get('last_activity_at'),
            })
            return result

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get individual user with detail data merged."""
        with self._get_session() as session:
            row = session.query(UserTable).filter_by(user_id=user_id).first()
            if not row:
                return None
            result = _row_to_dict(row)
            detail = session.query(UsersDetailTable).filter_by(user_id=user_id).first()
            if detail:
                d = _row_to_dict(detail)
                result.update({
                    'total_points':        d.get('total_points', 0),
                    'machines_solved':     d.get('machines_solved', 0),
                    'campaigns_completed': d.get('campaigns_completed', 0),
                    'current_streak':      d.get('current_streak', 0),
                    'longest_streak':      d.get('longest_streak', 0),
                    'preferences':         d.get('preferences', {}),
                    'updated_at':          d.get('updated_at'),
                    'last_activity_at':    d.get('last_activity_at'),
                })
            return result

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find individual user by email."""
        with self._get_session() as session:
            row = session.query(UserTable).filter_by(email=email).first()
            if not row:
                return None
            result = _row_to_dict(row)
            detail = session.query(UsersDetailTable).filter_by(user_id=row.user_id).first()
            if detail:
                d = _row_to_dict(detail)
                result.update({
                    'total_points':        d.get('total_points', 0),
                    'machines_solved':     d.get('machines_solved', 0),
                    'campaigns_completed': d.get('campaigns_completed', 0),
                    'current_streak':      d.get('current_streak', 0),
                    'longest_streak':      d.get('longest_streak', 0),
                    'preferences':         d.get('preferences', {}),
                    'updated_at':          d.get('updated_at'),
                    'last_activity_at':    d.get('last_activity_at'),
                })
            return result

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(UserTable).filter_by(username=username).first()
            return _row_to_dict(row)

    def get_any_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Check all three user tables for an email.
        Returns the matching user dict with additional '_source_table' key.
        """
        with self._get_session() as session:
            # Check individual users first
            row = session.query(UserTable).filter_by(email=email).first()
            if row:
                result = _row_to_dict(row)
                result['_source_table'] = 'users'
                result['organization_id'] = None
                # merge detail
                detail = session.query(UsersDetailTable).filter_by(user_id=row.user_id).first()
                if detail:
                    d = _row_to_dict(detail)
                    result.update({
                        'total_points': d.get('total_points', 0),
                        'machines_solved': d.get('machines_solved', 0),
                        'updated_at': d.get('updated_at'),
                        'last_activity_at': d.get('last_activity_at'),
                    })
                return result

            # Check org_admins
            row = session.query(OrgAdminTable).filter_by(email=email).first()
            if row:
                result = _row_to_dict(row)
                result['_source_table'] = 'org_admins'
                result['username'] = email.split('@')[0]   # synthetic username
                return result

            # Check org_staff
            row = session.query(OrgStaffTable).filter_by(email=email).first()
            if row:
                result = _row_to_dict(row)
                result['_source_table'] = 'org_staff'
                result['username'] = email.split('@')[0]   # synthetic username
                return result

            return None

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update individual user fields (users + users_detail)."""
        with self._get_session() as session:
            row = session.query(UserTable).filter_by(user_id=user_id).first()
            if not row:
                return False
            detail = session.query(UsersDetailTable).filter_by(user_id=user_id).first()

            user_fields = {'username', 'email', 'full_name', 'password'}
            detail_fields = {
                'total_points', 'machines_solved', 'campaigns_completed',
                'current_streak', 'longest_streak', 'preferences',
                'updated_at', 'last_activity_at',
            }

            for field, value in update_data.items():
                if field in user_fields:
                    setattr(row, field, value)
                if field in detail_fields and detail:
                    setattr(detail, field, value)
                # sync full_name/email to both tables
                if field == 'full_name' and detail:
                    detail.full_name = value
                if field == 'email' and detail:
                    detail.email = value

            if detail:
                detail.updated_at = _now()
            session.commit()
            return True

    def update_last_activity(self, user_id: str) -> bool:
        """Update last_activity_at in users_detail for individual users."""
        with self._get_session() as session:
            detail = session.query(UsersDetailTable).filter_by(user_id=user_id).first()
            if not detail:
                return False
            now = _now()
            detail.last_activity_at = now
            detail.updated_at       = now
            session.commit()
            return True

    def add_points(self, user_id: str, points: int) -> bool:
        with self._get_session() as session:
            detail = session.query(UsersDetailTable).filter_by(user_id=user_id).first()
            if not detail:
                return False
            detail.total_points     += points
            detail.updated_at        = _now()
            detail.last_activity_at  = _now()
            session.commit()
            return True

    def increment_solved(self, user_id: str) -> bool:
        with self._get_session() as session:
            detail = session.query(UsersDetailTable).filter_by(user_id=user_id).first()
            if not detail:
                return False
            detail.machines_solved  += 1
            detail.updated_at        = _now()
            detail.last_activity_at  = _now()
            session.commit()
            return True

    # ----------------------------------------------------------
    # ORG ADMIN OPERATIONS
    # ----------------------------------------------------------

    def create_org_admin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = _now()
        with self._get_session() as session:
            row = OrgAdminTable(
                user_id         = data['user_id'],
                email           = data['email'],
                password        = data.get('password', ''),
                org_name        = data['org_name'],
                organization_id = data['organization_id'],
                role            = 'enterprise_admin',
                account_type    = 'enterprise',
                created_at      = data.get('created_at', now),
                updated_at      = now,
                last_activity_at = now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)

    def get_org_admin(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(OrgAdminTable).filter_by(user_id=user_id).first()
            return _row_to_dict(row)

    def get_org_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(OrgAdminTable).filter_by(email=email).first()
            return _row_to_dict(row)

    # ----------------------------------------------------------
    # ORG STAFF OPERATIONS
    # ----------------------------------------------------------

    def create_org_staff(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = _now()
        with self._get_session() as session:
            row = OrgStaffTable(
                user_id         = data['user_id'],
                full_name       = data.get('full_name', ''),
                email           = data['email'],
                password        = data.get('password', ''),
                org_name        = data['org_name'],
                organization_id = data['organization_id'],
                role            = 'enterprise_staff',
                account_type    = 'enterprise',
                created_at      = now,
                updated_at      = now,
                last_activity_at = now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)

    def get_org_staff(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(OrgStaffTable).filter_by(user_id=user_id).first()
            return _row_to_dict(row)

    def get_org_staff_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(OrgStaffTable).filter_by(email=email).first()
            return _row_to_dict(row)

    def update_org_staff(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an org_staff account's fields."""
        with self._get_session() as session:
            row = session.query(OrgStaffTable).filter_by(user_id=user_id).first()
            if not row:
                return False
            allowed = {'full_name', 'email', 'password'}
            for field, value in update_data.items():
                if field in allowed:
                    setattr(row, field, value)
            row.updated_at = _now()
            session.commit()
            return True

    # ----------------------------------------------------------
    # PASSWORD RESET TOKEN OPERATIONS
    # ----------------------------------------------------------

    def save_reset_token(self, token: str, email: str, expires_at: datetime) -> None:
        with self._get_session() as session:
            session.query(PasswordResetTokenTable).filter_by(email=email).delete()
            row = PasswordResetTokenTable(
                token=token, email=email,
                expires_at=expires_at, created_at=_now(),
            )
            session.add(row)
            session.commit()

    def get_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(PasswordResetTokenTable).filter_by(token=token).first()
            return _row_to_dict(row)

    def delete_reset_token(self, token: str) -> None:
        with self._get_session() as session:
            session.query(PasswordResetTokenTable).filter_by(token=token).delete()
            session.commit()

    # ----------------------------------------------------------
    # PENDING REGISTRATION / OTP OPERATIONS
    # ----------------------------------------------------------

    def create_pending_registration(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._get_session() as session:
            session.query(PendingRegistrationTable).filter_by(email=data['email']).delete()
            row = PendingRegistrationTable(
                username   = data['username'],
                full_name  = data.get('full_name', ''),
                email      = data['email'],
                password   = data['password'],   # must be pre-hashed by caller
                role       = data.get('role', 'individual'),
                otp        = data['otp'],
                attempts   = 0,
                expires_at = data['expires_at'],
                created_at = _now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)

    def get_pending_registration(self, email: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(PendingRegistrationTable).filter_by(email=email).first()
            return _row_to_dict(row)

    def increment_otp_attempts(self, email: str) -> int:
        with self._get_session() as session:
            row = session.query(PendingRegistrationTable).filter_by(email=email).first()
            if not row:
                return 0
            row.attempts += 1
            session.commit()
            return row.attempts

    def delete_pending_registration(self, email: str) -> None:
        with self._get_session() as session:
            session.query(PendingRegistrationTable).filter_by(email=email).delete()
            session.commit()

    # ----------------------------------------------------------
    # CLEANUP OPERATIONS
    # ----------------------------------------------------------

    def cleanup_expired_tokens(self) -> int:
        with self._get_session() as session:
            count = (
                session.query(PasswordResetTokenTable)
                .filter(PasswordResetTokenTable.expires_at < _now())
                .delete(synchronize_session=False)
            )
            session.commit()
            return count

    def cleanup_expired_registrations(self) -> int:
        with self._get_session() as session:
            count = (
                session.query(PendingRegistrationTable)
                .filter(PendingRegistrationTable.expires_at < _now())
                .delete(synchronize_session=False)
            )
            session.commit()
            return count

    # ----------------------------------------------------------
    # SESSION OPERATIONS
    # ----------------------------------------------------------

    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._get_session() as session:
            now = _now()
            row = SessionTable(
                session_id      = session_data['session_id'],
                user_id         = session_data['user_id'],
                ip_address      = session_data.get('ip_address'),
                user_agent      = session_data.get('user_agent'),
                flags_submitted = 0,
                hints_requested = 0,
                started_at      = now,
                last_activity   = now,
                ended_at        = None,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            result = _row_to_dict(row)
            result['machines_visited'] = []
            return result

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(SessionTable).filter_by(session_id=session_id).first()
            if not row:
                return None
            result = _row_to_dict(row)
            result['machines_visited'] = self._fetch_machines_visited(session, session_id)
            return result

    def get_user_sessions(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            rows = (
                session.query(SessionTable)
                .filter_by(user_id=user_id)
                .order_by(SessionTable.started_at.desc())
                .limit(limit)
                .all()
            )
            results = []
            for row in rows:
                d = _row_to_dict(row)
                d['machines_visited'] = self._fetch_machines_visited(session, row.session_id)
                results.append(d)
            return results

    def update_session_activity(self, session_id: str) -> bool:
        with self._get_session() as session:
            row = session.query(SessionTable).filter_by(session_id=session_id).first()
            if not row:
                return False
            row.last_activity = _now()
            session.commit()
            return True

    def end_session(self, session_id: str) -> bool:
        with self._get_session() as session:
            row = session.query(SessionTable).filter_by(session_id=session_id).first()
            if not row:
                return False
            now = _now()
            row.ended_at      = now
            row.last_activity = now
            session.commit()
            return True

    def record_session_flag_submission(self, session_id: str) -> bool:
        with self._get_session() as session:
            row = session.query(SessionTable).filter_by(session_id=session_id).first()
            if not row:
                return False
            row.flags_submitted += 1
            row.last_activity    = _now()
            session.commit()
            return True

    def record_session_hint(self, session_id: str) -> bool:
        with self._get_session() as session:
            row = session.query(SessionTable).filter_by(session_id=session_id).first()
            if not row:
                return False
            row.hints_requested += 1
            row.last_activity    = _now()
            session.commit()
            return True

    # ----------------------------------------------------------
    # PRIVATE — Session machine visit helpers
    # ----------------------------------------------------------

    def _fetch_machines_visited(
        self, session: Session, session_id: str
    ) -> List[str]:
        rows = (
            session.query(SessionMachineVisitTable)
            .filter_by(session_id=session_id)
            .order_by(SessionMachineVisitTable.visited_at)
            .all()
        )
        return [r.machine_id for r in rows]

    def add_machine_visit(self, session_id: str, machine_id: str) -> bool:
        with self._get_session() as session:
            try:
                visit_row = SessionMachineVisitTable(
                    session_id = session_id,
                    machine_id = machine_id,
                    visited_at = _now(),
                )
                session.add(visit_row)
                session.commit()
            except IntegrityError:
                session.rollback()

            session_row = session.query(SessionTable).filter_by(session_id=session_id).first()
            if session_row:
                session_row.last_activity = _now()
                session.commit()

            return True

    def get_machines_visited(self, session_id: str) -> List[str]:
        with self._get_session() as session:
            return self._fetch_machines_visited(session, session_id)

    def get_sessions_for_machine(self, machine_id: str) -> List[str]:
        with self._get_session() as session:
            rows = (
                session.query(SessionMachineVisitTable)
                .filter_by(machine_id=machine_id)
                .order_by(SessionMachineVisitTable.visited_at.desc())
                .all()
            )
            return [r.session_id for r in rows]

    # ----------------------------------------------------------
    # CAMPAIGN OPERATIONS
    # ----------------------------------------------------------

    def create_campaign(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        campaign_data.setdefault(
            'campaign_name',
            f"Campaign {campaign_data.get('campaign_id', 'Unknown')}",
        )
        campaign_data.setdefault('status', 'active')
        campaign_data['created_at'] = _now()

        machines = campaign_data.get('machines', [])

        with self._get_session() as session:
            row = CampaignTable(
                campaign_id     = campaign_data['campaign_id'],
                campaign_name   = campaign_data['campaign_name'],
                user_id         = campaign_data['user_id'],
                difficulty      = campaign_data['difficulty'],
                machine_count   = campaign_data['machine_count'],
                status          = campaign_data['status'],
                machines_solved = campaign_data.get('machines_solved', 0),
                total_points    = campaign_data.get('total_points', 0),
                created_at      = campaign_data['created_at'],
            )
            session.add(row)
            session.flush()
            self._insert_machines(session, campaign_data['campaign_id'], machines)
            session.commit()
            session.refresh(row)

            result = _row_to_dict(row)
            result['machines'] = [
                {k: v for k, v in m.items() if k != 'flag'}  # never return plaintext flag
                for m in machines
            ]
            return result

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = (
                session.query(CampaignTable)
                .filter_by(campaign_id=campaign_id)
                .filter(CampaignTable.deleted_at.is_(None))  # [FIX-R1]
                .first()
            )
            campaign = _row_to_dict(row)
            return self._attach_machines(session, campaign)

    def get_user_campaigns(self, user_id: str) -> List[Dict[str, Any]]:
        """[FIX-P2] Single batched query for all campaign machines."""
        with self._get_session() as session:
            rows = (
                session.query(CampaignTable)
                .filter_by(user_id=user_id)
                .filter(CampaignTable.deleted_at.is_(None))  # [FIX-R1]
                .order_by(CampaignTable.created_at.desc())
                .all()
            )
            if not rows:
                return []

            campaign_ids = [r.campaign_id for r in rows]
            machines_map = self._fetch_machines_batch(session, campaign_ids)

            campaigns = []
            for row in rows:
                d = _row_to_dict(row)
                d['machines'] = machines_map.get(row.campaign_id, [])
                campaigns.append(d)
            return campaigns

    def update_campaign_name(self, campaign_id: str, new_name: str) -> bool:
        with self._get_session() as session:
            row = (
                session.query(CampaignTable)
                .filter_by(campaign_id=campaign_id)
                .filter(CampaignTable.deleted_at.is_(None))
                .first()
            )
            if not row:
                return False
            row.campaign_name = new_name
            session.commit()
            return True

    def update_campaign_progress(
        self, campaign_id: str, solved_count: int, points: int
    ) -> bool:
        with self._get_session() as session:
            row = (
                session.query(CampaignTable)
                .filter_by(campaign_id=campaign_id)
                .filter(CampaignTable.deleted_at.is_(None))
                .first()
            )
            if not row:
                return False
            row.machines_solved = solved_count
            row.total_points    = points
            session.commit()
            return True

    def update_machine_port(
        self, campaign_id: str, machine_id: str, port: int
    ) -> bool:
        with self._get_session() as session:
            row = (
                session.query(CampaignMachineTable)
                .filter_by(campaign_id=campaign_id, machine_id=machine_id)
                .first()
            )
            if not row:
                return False
            row.port = port
            session.commit()
            return True

    def complete_campaign(self, campaign_id: str) -> bool:
        """
        Campaign status update and user counter increment.
        Updates UsersDetailTable for campaigns_completed.
        """
        with self._get_session() as session:
            campaign_row = (
                session.query(CampaignTable)
                .filter_by(campaign_id=campaign_id)
                .filter(CampaignTable.deleted_at.is_(None))
                .first()
            )
            if not campaign_row:
                return False

            campaign_row.status       = 'completed'
            campaign_row.completed_at = _now()

            detail_row = (
                session.query(UsersDetailTable)
                .filter_by(user_id=campaign_row.user_id)
                .first()
            )
            if detail_row:
                detail_row.campaigns_completed += 1
                detail_row.last_activity_at     = _now()
                detail_row.updated_at           = _now()

            session.commit()
            return True

    def delete_campaign(self, campaign_id: str) -> bool:
        """[FIX-R1] Soft delete — sets deleted_at, keeps the audit trail."""
        with self._get_session() as session:
            row = (
                session.query(CampaignTable)
                .filter_by(campaign_id=campaign_id)
                .filter(CampaignTable.deleted_at.is_(None))
                .first()
            )
            if not row:
                return False
            row.deleted_at = _now()
            session.commit()
            return True

    def hard_delete_campaign(self, campaign_id: str) -> bool:
        """
        Permanently remove a campaign and all its machines (via CASCADE).
        Reserved for admin/cleanup use only — prefer delete_campaign() for
        normal operations.
        """
        with self._get_session() as session:
            row = session.query(CampaignTable).filter_by(campaign_id=campaign_id).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def search_campaigns(
        self, user_id: str, search_term: str
    ) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            rows = (
                session.query(CampaignTable)
                .filter(
                    CampaignTable.user_id      == user_id,
                    CampaignTable.deleted_at.is_(None),  # [FIX-R1]
                    CampaignTable.campaign_name.ilike(f'%{search_term}%'),
                )
                .order_by(CampaignTable.created_at.desc())
                .all()
            )
            if not rows:
                return []
            campaign_ids = [r.campaign_id for r in rows]
            machines_map = self._fetch_machines_batch(session, campaign_ids)
            campaigns = []
            for row in rows:
                d = _row_to_dict(row)
                d['machines'] = machines_map.get(row.campaign_id, [])
                campaigns.append(d)
            return campaigns

    def get_campaign_statistics(
        self, campaign_id: str
    ) -> Optional[Dict[str, Any]]:
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return None

        progress_list  = self.get_campaign_progress(campaign['user_id'], campaign_id)
        total_attempts = sum(p.get('attempts', 0) for p in progress_list)
        solved_count   = sum(1 for p in progress_list if p.get('solved', False))
        total_points   = sum(p.get('points_earned', 0) for p in progress_list)
        machine_count  = campaign.get('machine_count', 1)

        return {
            'campaign_id':           campaign_id,
            'campaign_name':         campaign.get('campaign_name', 'Unknown'),
            'total_machines':        machine_count,
            'solved_machines':       solved_count,
            'total_attempts':        total_attempts,
            'total_points':          total_points,
            'completion_percentage': (
                (solved_count / machine_count * 100) if machine_count > 0 else 0
            ),
            'status':     campaign.get('status', 'active'),
            'created_at': campaign.get('created_at'),
        }

    # ----------------------------------------------------------
    # PROGRESS OPERATIONS
    # ----------------------------------------------------------

    def create_progress(self, progress_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._get_session() as session:
            row = ProgressTable(
                user_id     = progress_data['user_id'],
                machine_id  = progress_data['machine_id'],
                campaign_id = progress_data['campaign_id'],
                started_at  = _now(),
                solved      = False,
                attempts    = 0,
            )
            try:
                session.add(row)
                session.commit()
                session.refresh(row)
            except IntegrityError:
                session.rollback()
                row = session.query(ProgressTable).filter_by(
                    user_id     = progress_data['user_id'],
                    machine_id  = progress_data['machine_id'],
                    campaign_id = progress_data['campaign_id'],
                ).first()
            return _row_to_dict(row)

    def get_progress(
        self,
        user_id: str,
        machine_id: str,
        campaign_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            q = session.query(ProgressTable).filter_by(
                user_id=user_id, machine_id=machine_id,
            )
            if campaign_id:
                q = q.filter_by(campaign_id=campaign_id)
            return _row_to_dict(q.first())

    def increment_attempts(
        self,
        user_id: str,
        machine_id: str,
        campaign_id: Optional[str] = None,
    ) -> bool:
        with self._get_session() as session:
            q = session.query(ProgressTable).filter_by(
                user_id=user_id, machine_id=machine_id,
            )
            if campaign_id:
                q = q.filter_by(campaign_id=campaign_id)
            row = q.first()
            if not row:
                return False
            row.attempts += 1
            session.commit()
            return True

    def mark_solved(
        self,
        user_id: str,
        machine_id: str,
        points: int,
        solve_time: int,
        campaign_id: Optional[str] = None,
    ) -> bool:
        with self._get_session() as session:
            q = session.query(ProgressTable).filter_by(
                user_id=user_id, machine_id=machine_id,
            )
            if campaign_id:
                q = q.filter_by(campaign_id=campaign_id)
            row = q.first()
            if not row:
                return False
            row.solved        = True
            row.points_earned = points
            row.solve_time    = solve_time
            row.completed_at  = _now()
            session.commit()
            return True

    def get_flag_hash_for_machine(
        self, campaign_id: str, machine_id: str
    ) -> Optional[str]:
        """
        Return the stored HMAC-SHA256 flag_hash for a specific machine in a
        specific campaign.  Used exclusively by the flag-submission route so
        it can call verify_flag() without the hash ever leaving the server.
        Returns None if the (campaign_id, machine_id) pair does not exist.
        """
        with self._get_session() as session:
            row = (
                session.query(CampaignMachineTable.flag_hash)
                .filter_by(campaign_id=campaign_id, machine_id=machine_id)
                .first()
            )
            return row.flag_hash if row else None

    def get_generated_machine_flag_hash(self, machine_id: str) -> Optional[str]:
        """
        Return the flag_hash for a standalone generated machine (VulnForge
        pipeline).  Used by the flag-submission route as a fallback when
        the machine is not inside a campaign.
        Returns None if the machine does not exist or has no flag.
        """
        with self._get_session() as session:
            row = (
                session.query(GeneratedMachineTable.flag_hash)
                .filter_by(machine_id=machine_id)
                .filter(GeneratedMachineTable.deleted_at.is_(None))
                .first()
            )
            return row.flag_hash if row else None

    def get_campaign_progress(
        self, user_id: str, campaign_id: str
    ) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            rows = session.query(ProgressTable).filter_by(
                user_id=user_id, campaign_id=campaign_id,
            ).all()
            return [_row_to_dict(r) for r in rows]

    # ----------------------------------------------------------
    # SUBMISSIONS
    # ----------------------------------------------------------

    def record_submission(
        self, submission_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        with self._get_session() as session:
            row = SubmissionTable(
                submission_id  = submission_data['submission_id'],
                user_id        = submission_data['user_id'],
                machine_id     = submission_data['machine_id'],
                campaign_id    = submission_data['campaign_id'],
                submitted_flag = submission_data['submitted_flag'],
                correct        = submission_data['correct'],
                points_awarded = submission_data.get('points_awarded', 0),
                ip_address     = submission_data.get('ip_address'),
                user_agent     = submission_data.get('user_agent'),
                submitted_at   = _now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)

    def get_user_submissions(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            rows = (
                session.query(SubmissionTable)
                .filter_by(user_id=user_id)
                .order_by(SubmissionTable.submitted_at.desc())
                .limit(limit)
                .all()
            )
            return [_row_to_dict(r) for r in rows]

    # ----------------------------------------------------------
    # LEADERBOARD
    # ----------------------------------------------------------

    def get_leaderboard(self, limit: int = 100, timeframe: str = 'all_time') -> List[Dict[str, Any]]:
        """Leaderboard — joins UserTable + UsersDetailTable, individual users only."""
        with self._get_session() as session:
            # Only users who have at least one submission
            subquery = (
                session.query(SubmissionTable.user_id)
                .distinct()
                .subquery()
            )

            query = (
                session.query(UserTable, UsersDetailTable)
                .join(UsersDetailTable, UserTable.user_id == UsersDetailTable.user_id)
                .join(subquery, UserTable.user_id == subquery.c.user_id)
            )

            if timeframe == 'weekly':
                cutoff = _now() - timedelta(days=7)
                query  = query.filter(UsersDetailTable.last_activity_at >= cutoff)
            elif timeframe == 'monthly':
                cutoff = _now() - timedelta(days=30)
                query  = query.filter(UsersDetailTable.last_activity_at >= cutoff)

            rows = (
                query
                .order_by(UsersDetailTable.total_points.desc())
                .limit(limit)
                .all()
            )

            result = []
            for idx, (user_row, detail_row) in enumerate(rows, 1):
                d = _row_to_dict(user_row)
                dd = _row_to_dict(detail_row)
                d.update({
                    'total_points':        dd.get('total_points', 0),
                    'machines_solved':     dd.get('machines_solved', 0),
                    'campaigns_completed': dd.get('campaigns_completed', 0),
                    'current_streak':      dd.get('current_streak', 0),
                    'longest_streak':      dd.get('longest_streak', 0),
                    'last_activity_at':    dd.get('last_activity_at'),
                })
                d['rank'] = idx
                d.pop('password', None)
                result.append(d)
            return result

    def get_user_rank(self, user_id: str) -> Optional[int]:
        user = self.get_user(user_id)
        if not user:
            return None
        with self._get_session() as session:
            count = session.query(UsersDetailTable).filter(
                UsersDetailTable.total_points > user.get('total_points', 0)
            ).count()
            return count + 1

    # ----------------------------------------------------------
    # PLATFORM STATS
    # ----------------------------------------------------------

    def get_platform_stats(self) -> Dict[str, Any]:
        """
        [FIX-P1] Average session duration computed via SQL TIMESTAMPDIFF —
        no longer fetches every ended session row into Python.
        """
        with self._get_session() as session:
            now      = _now()
            day_ago  = now - timedelta(hours=24)
            week_ago = now - timedelta(days=7)

            total_users = (
                session.query(UserTable).count() +
                session.query(OrgAdminTable).count() +
                session.query(OrgStaffTable).count()
            )
            active_users_today = session.query(UsersDetailTable).filter(
                UsersDetailTable.last_activity_at >= day_ago
            ).count()
            active_users_week  = session.query(UsersDetailTable).filter(
                UsersDetailTable.last_activity_at >= week_ago
            ).count()

            total_campaigns     = session.query(CampaignTable).filter(
                CampaignTable.deleted_at.is_(None)
            ).count()
            active_campaigns    = session.query(CampaignTable).filter_by(
                status='active'
            ).filter(CampaignTable.deleted_at.is_(None)).count()
            completed_campaigns = session.query(CampaignTable).filter_by(
                status='completed'
            ).filter(CampaignTable.deleted_at.is_(None)).count()

            total_machines   = session.query(GeneratedMachineTable).filter(
                GeneratedMachineTable.deleted_at.is_(None)
            ).count()
            total_solves     = session.query(ProgressTable).filter_by(solved=True).count()
            total_flags      = session.query(SubmissionTable).count()
            total_hints_used = session.query(HintUsageTable).count()

            # [FIX-P1] Single SQL aggregate — no Python loop over all rows
            avg_session_time = session.query(
                func.avg(
                    func.timestampdiff(
                        text('SECOND'),
                        SessionTable.started_at,
                        SessionTable.ended_at,
                    )
                )
            ).filter(SessionTable.ended_at.isnot(None)).scalar() or 0.0

            return {
                'total_users':           total_users,
                'active_users_today':    active_users_today,
                'active_users_week':     active_users_week,
                'total_campaigns':       total_campaigns,
                'active_campaigns':      active_campaigns,
                'completed_campaigns':   completed_campaigns,
                'total_machines':        total_machines,
                'total_solves':          total_solves,
                'average_session_time':  float(avg_session_time),
                'total_flags_submitted': total_flags,
                'total_hints_used':      total_hints_used,
                'last_updated':          now,
            }

    # ----------------------------------------------------------
    # MACHINE STATS
    # ----------------------------------------------------------

    def get_machine_stats(self, machine_id: str) -> Dict[str, Any]:
        """
        [FIX-C1] total_attempts now sums ProgressTable.attempts (the actual
        flag-submission counter) instead of counting rows.
        [FIX-C1] All aggregates pushed to a single SQL query — no full-table
        Python loops.
        """
        with self._get_session() as session:
            stats = session.query(
                func.sum(ProgressTable.attempts).label('total_attempts'),
                func.sum(
                    func.cast(ProgressTable.solved, Integer)
                ).label('unique_solvers'),
                func.min(ProgressTable.solve_time).label('fastest_solve_time'),
                func.avg(ProgressTable.solve_time).label('average_solve_time'),
                func.avg(ProgressTable.hints_used).label('average_hints_used'),
            ).filter(ProgressTable.machine_id == machine_id).one()

            total_attempts = int(stats.total_attempts or 0)
            unique_solvers = int(stats.unique_solvers or 0)
            solve_rate     = (
                unique_solvers / total_attempts if total_attempts > 0 else 0.0
            )

            return {
                'machine_id':          machine_id,
                'total_attempts':      total_attempts,
                'unique_solvers':      unique_solvers,
                'solve_rate':          solve_rate,
                'average_solve_time':  (
                    float(stats.average_solve_time)
                    if stats.average_solve_time is not None else None
                ),
                'fastest_solve_time':  (
                    int(stats.fastest_solve_time)
                    if stats.fastest_solve_time is not None else None
                ),
                'average_hints_used':  float(stats.average_hints_used or 0.0),
            }

    # ----------------------------------------------------------
    # GENERATED MACHINE OPERATIONS (VulnForge pipeline)
    # ----------------------------------------------------------

    def register_generated_machine(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called by bridge.py the moment a machine is ready.
        'flag_content' in data must be the raw flag text — we hash it here
        and never store the plaintext. [FIX-C4]
        """
        with self._get_session() as session:
            now       = _now()
            raw_flag  = data.get('flag_content') or ''
            row = GeneratedMachineTable(
                machine_id    = data['machine_id'],
                job_id        = data['job_id'],
                user_id       = data.get('user_id'),
                cve_id        = data['cve_id'],
                difficulty    = data.get('difficulty', 'medium'),
                port          = data.get('port'),
                access_url    = data.get('access_url'),
                machine_dir   = data['machine_dir'],
                service_name  = data.get('service_name'),
                flag_location = data.get('flag_location'),
                flag_hash     = hash_flag(raw_flag) if raw_flag else None,  # [FIX-C4]
                status        = 'ready',
                created_at    = now,
                ready_at      = now,
            )
            try:
                session.add(row)
                session.commit()
                session.refresh(row)
            except IntegrityError:
                session.rollback()
                row = session.query(GeneratedMachineTable).filter_by(
                    machine_id=data['machine_id']
                ).first()
            return _row_to_dict(row)

    def get_generated_machine(self, machine_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(GeneratedMachineTable).filter_by(
                machine_id=machine_id
            ).filter(GeneratedMachineTable.deleted_at.is_(None)).first()
            return _row_to_dict(row)

    def get_generated_machine_by_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(GeneratedMachineTable).filter_by(
                job_id=job_id
            ).filter(GeneratedMachineTable.deleted_at.is_(None)).first()
            return _row_to_dict(row)

    def list_generated_machines(
        self,
        user_id: Optional[str] = None,
        status: Optional[str]  = None,
        limit: int             = 100,
    ) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            q = session.query(GeneratedMachineTable).filter(
                GeneratedMachineTable.deleted_at.is_(None)  # [FIX-R1]
            )
            if user_id:
                q = q.filter_by(user_id=user_id)
            if status:
                q = q.filter_by(status=status)
            rows = q.order_by(GeneratedMachineTable.created_at.desc()).limit(limit).all()
            results = [_row_to_dict(r) for r in rows]
            # Strip flag_hash from API-facing responses [FIX-C4]
            for r in results:
                r.pop('flag_hash', None)
            return results

    def update_generated_machine_status(self, machine_id: str, status: str) -> bool:
        with self._get_session() as session:
            row = session.query(GeneratedMachineTable).filter_by(
                machine_id=machine_id
            ).first()
            if not row:
                return False
            row.status = status
            session.commit()
            return True

    def delete_generated_machine(self, machine_id: str) -> bool:
        """[FIX-R1] Soft delete."""
        with self._get_session() as session:
            row = session.query(GeneratedMachineTable).filter_by(
                machine_id=machine_id
            ).filter(GeneratedMachineTable.deleted_at.is_(None)).first()
            if not row:
                return False
            row.deleted_at = _now()
            session.commit()
            return True

    def hard_delete_generated_machine(self, machine_id: str) -> bool:
        """Permanent removal — admin/cleanup use only."""
        with self._get_session() as session:
            row = session.query(GeneratedMachineTable).filter_by(
                machine_id=machine_id
            ).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    # ----------------------------------------------------------
    # ORGANIZATION OPERATIONS (Enterprise)
    # ----------------------------------------------------------

    def create_organization(self, org_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._get_session() as session:
            row = OrganizationTable(
                organization_id = org_data['organization_id'],
                name            = org_data['name'],
                created_at      = _now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)

    def get_organization(
        self, organization_id: str
    ) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            row = session.query(OrganizationTable).filter_by(
                organization_id=organization_id
            ).first()
            return _row_to_dict(row)

    def create_enterprise_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy wrapper — routes should call create_org_staff() or create_org_admin() directly.
        Kept for backward compatibility during transition.
        """
        role = user_data.get('role', 'enterprise_staff')
        org_id = user_data.get('organization_id')

        # Resolve org_name from organizations table
        org = self.get_organization(org_id) if org_id else None
        org_name = org['name'] if org else ''

        if role == 'enterprise_admin':
            return self.create_org_admin({
                'user_id':         user_data['user_id'],
                'email':           user_data['email'],
                'password':        user_data.get('password', ''),
                'org_name':        org_name,
                'organization_id': org_id,
            })
        else:
            return self.create_org_staff({
                'user_id':         user_data['user_id'],
                'full_name':       user_data.get('full_name', ''),
                'email':           user_data['email'],
                'password':        user_data.get('password', ''),
                'org_name':        org_name,
                'organization_id': org_id,
            })

    def get_staff_by_organization(
        self, organization_id: str
    ) -> List[Dict[str, Any]]:
        """Returns all staff accounts for an organization from org_staff table."""
        with self._get_session() as session:
            rows = (
                session.query(OrgStaffTable)
                .filter_by(organization_id=organization_id)
                .order_by(OrgStaffTable.created_at.desc())
                .all()
            )
            results = []
            for row in rows:
                d = _row_to_dict(row)
                d.pop('password', None)
                results.append(d)
            return results

    # ----------------------------------------------------------
    # STUDENT / CLASS OPERATIONS (Enterprise Staff)
    # ----------------------------------------------------------

    def create_class(
        self,
        staff_user_id: str,
        enterprise_id: str,
        class_name: str,
        students: List[Dict[str, Any]],
    ) -> None:
        """
        Bulk-insert student rows for a new class.
        Each dict in `students` must have at least 'roll_no' and 'student_name'.
        """
        now = _now()
        with self._get_session() as session:
            for s in students:
                row = StuDetailTable(
                    class_name    = class_name,
                    roll_no       = s['roll_no'],
                    student_name  = s['student_name'],
                    father_name   = s.get('father_name') or None,
                    section       = s.get('section') or None,
                    staff_user_id = staff_user_id,
                    enterprise_id = enterprise_id,
                    created_at    = now,
                    updated_at    = now,
                )
                session.add(row)
            session.commit()

    def get_classes_for_staff(
        self, staff_user_id: str, enterprise_id: str
    ) -> List[Dict[str, Any]]:
        """
        Return distinct class names with student count for a given staff user.
        """
        with self._get_session() as session:
            rows = (
                session.query(
                    StuDetailTable.class_name,
                    func.count(StuDetailTable.id).label('student_count'),
                    func.min(StuDetailTable.created_at).label('created_at'),
                )
                .filter_by(staff_user_id=staff_user_id, enterprise_id=enterprise_id)
                .group_by(StuDetailTable.class_name)
                .order_by(func.min(StuDetailTable.created_at).desc())
                .all()
            )
            return [
                {
                    'class_name':    r.class_name,
                    'student_count': r.student_count,
                    'created_at':    r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def get_class_students(
        self, staff_user_id: str, enterprise_id: str, class_name: str
    ) -> List[Dict[str, Any]]:
        """
        Return all student rows for a specific class owned by the staff user.
        """
        with self._get_session() as session:
            rows = (
                session.query(StuDetailTable)
                .filter_by(
                    staff_user_id=staff_user_id,
                    enterprise_id=enterprise_id,
                    class_name=class_name,
                )
                .order_by(StuDetailTable.id)
                .all()
            )
            return [_row_to_dict(r) for r in rows]

    def update_class(
        self,
        staff_user_id: str,
        enterprise_id: str,
        old_class_name: str,
        new_class_name: str,
        students: List[Dict[str, Any]],
    ) -> None:
        """
        Replace all students in a class.  Delete existing rows, then bulk-insert new ones.
        """
        now = _now()
        with self._get_session() as session:
            # Delete old rows
            session.query(StuDetailTable).filter_by(
                staff_user_id=staff_user_id,
                enterprise_id=enterprise_id,
                class_name=old_class_name,
            ).delete(synchronize_session=False)

            # Insert updated rows
            for s in students:
                row = StuDetailTable(
                    class_name    = new_class_name,
                    roll_no       = s['roll_no'],
                    student_name  = s['student_name'],
                    father_name   = s.get('father_name') or None,
                    section       = s.get('section') or None,
                    staff_user_id = staff_user_id,
                    enterprise_id = enterprise_id,
                    created_at    = now,
                    updated_at    = now,
                )
                session.add(row)
            session.commit()

    def delete_class(
        self, staff_user_id: str, enterprise_id: str, class_name: str
    ) -> int:
        """
        Delete all student rows for a class.  Returns number of rows deleted.
        """
        with self._get_session() as session:
            count = (
                session.query(StuDetailTable)
                .filter_by(
                    staff_user_id=staff_user_id,
                    enterprise_id=enterprise_id,
                    class_name=class_name,
                )
                .delete(synchronize_session=False)
            )
            session.commit()
            return count

    # ----------------------------------------------------------
    # RAW COLLECTION-STYLE ACCESS (proxy bridge)
    # ----------------------------------------------------------

    @property
    def campaigns(self):
        return _CampaignProxy(self)

    @property
    def progress(self):
        return _ProgressProxy(self)

    @property
    def submissions(self):
        return _SubmissionProxy(self)

    @property
    def users(self):
        return _UserProxy(self)


# ============================================================
# Proxy Classes  [FIX-S1] [FIX-S2]
# ============================================================

class _UserProxy:
    def __init__(self, manager: DatabaseManager):
        self._m = manager

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = SessionLocal()
        try:
            q = session.query(UserTable)
            for key, value in query.items():
                if key not in _USER_READABLE_COLS:          # [FIX-S1]
                    continue
                q = q.filter(getattr(UserTable, key) == value)
            row = q.first()
            result = _row_to_dict(row)
            if result:
                result.pop('password', None)               # never expose hash
            return result
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def update_one(self, query: Dict, update: Dict) -> Any:
        session = SessionLocal()
        try:
            q = session.query(UserTable)
            for key, value in query.items():
                if key not in _USER_READABLE_COLS:         # [FIX-S1]
                    continue
                q = q.filter(getattr(UserTable, key) == value)
            row = q.first()
            if not row:
                return _FakeResult(0)
            if '$inc' in update:
                for field, val in update['$inc'].items():
                    if field in _USER_WRITABLE_COLS:       # [FIX-S1]
                        setattr(row, field, getattr(row, field) + val)
            if '$set' in update:
                for field, val in update['$set'].items():
                    if field in _USER_WRITABLE_COLS:       # [FIX-S1]
                        setattr(row, field, val)
            session.commit()
            return _FakeResult(1)
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()


class _CampaignProxy:
    def __init__(self, manager: DatabaseManager):
        self._m = manager

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = SessionLocal()
        try:
            q = session.query(CampaignTable).filter(
                CampaignTable.deleted_at.is_(None)
            )
            for key, value in query.items():
                if key not in _CAMPAIGN_READABLE_COLS:     # [FIX-S1]
                    continue
                q = q.filter(getattr(CampaignTable, key) == value)
            row = q.first()
            campaign = _row_to_dict(row)
            if campaign:
                campaign['machines'] = self._m._fetch_machines(
                    session, campaign['campaign_id']
                )
            return campaign
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def find(self, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        session = SessionLocal()
        try:
            q = session.query(CampaignTable).filter(
                CampaignTable.deleted_at.is_(None)
            )
            if query:
                for key, value in query.items():
                    if key not in _CAMPAIGN_READABLE_COLS: # [FIX-S1]
                        continue
                    q = q.filter(getattr(CampaignTable, key) == value)
            rows = q.all()
            campaign_ids = [r.campaign_id for r in rows]
            machines_map = self._m._fetch_machines_batch(session, campaign_ids)
            campaigns = []
            for r in rows:
                d = _row_to_dict(r)
                if d:
                    d['machines'] = machines_map.get(r.campaign_id, [])
                    campaigns.append(d)
            return campaigns
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def delete_one(self, query: Dict[str, Any]) -> Any:
        session = SessionLocal()
        try:
            q = session.query(CampaignTable).filter(
                CampaignTable.deleted_at.is_(None)
            )
            for key, value in query.items():
                if key not in _CAMPAIGN_READABLE_COLS:     # [FIX-S1]
                    continue
                q = q.filter(getattr(CampaignTable, key) == value)
            row = q.first()
            if row:
                row.deleted_at = _now()                   # soft delete [FIX-R1]
                session.commit()
                return _FakeResult(1)
            return _FakeResult(0)
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def update_one(self, query: Dict, update: Dict) -> Any:
        session = SessionLocal()
        try:
            q = session.query(CampaignTable).filter(
                CampaignTable.deleted_at.is_(None)
            )
            for key, value in query.items():
                if key not in _CAMPAIGN_READABLE_COLS:     # [FIX-S1]
                    continue
                q = q.filter(getattr(CampaignTable, key) == value)
            row = q.first()
            if not row:
                return _FakeResult(0)
            if '$set' in update:
                for field, val in update['$set'].items():
                    if field in _CAMPAIGN_WRITABLE_COLS:   # [FIX-S1]
                        setattr(row, field, val)
            if '$inc' in update:
                for field, val in update['$inc'].items():
                    if field in _CAMPAIGN_WRITABLE_COLS:   # [FIX-S1]
                        setattr(row, field, getattr(row, field) + val)
            session.commit()
            return _FakeResult(1)
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()


class _ProgressProxy:
    def __init__(self, manager: DatabaseManager):
        self._m = manager

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = SessionLocal()
        try:
            q = session.query(ProgressTable)
            for key, value in query.items():
                if key not in _PROGRESS_READABLE_COLS:     # [FIX-S1]
                    continue
                q = q.filter(getattr(ProgressTable, key) == value)
            return _row_to_dict(q.first())
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def delete_many(self, query: Dict[str, Any]) -> Any:
        session = SessionLocal()
        try:
            q = session.query(ProgressTable)
            for key, value in query.items():
                if key not in _PROGRESS_READABLE_COLS:     # [FIX-S1]
                    continue
                q = q.filter(getattr(ProgressTable, key) == value)
            count = q.delete(synchronize_session=False)
            session.commit()
            return _FakeResult(count)
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def count_documents(self, query: Dict[str, Any]) -> int:
        session = SessionLocal()
        try:
            q = session.query(ProgressTable)
            for key, value in query.items():
                if key not in _PROGRESS_READABLE_COLS:     # [FIX-S1]
                    continue
                q = q.filter(getattr(ProgressTable, key) == value)
            return q.count()
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()


class _SubmissionProxy:
    def __init__(self, manager: DatabaseManager):
        self._m = manager

    def delete_many(self, query: Dict[str, Any]) -> Any:
        session = SessionLocal()
        try:
            q = session.query(SubmissionTable)
            if query:
                for key, value in query.items():
                    if key not in _SUBMISSION_READABLE_COLS:  # [FIX-S1]
                        continue
                    q = q.filter(getattr(SubmissionTable, key) == value)
            count = q.delete(synchronize_session=False)
            session.commit()
            return _FakeResult(count)
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()

    def count_documents(self, query: Dict[str, Any] = None) -> int:
        session = SessionLocal()
        try:
            q = session.query(SubmissionTable)
            if query:
                for key, value in query.items():
                    if key not in _SUBMISSION_READABLE_COLS:  # [FIX-S1]
                        continue
                    q = q.filter(getattr(SubmissionTable, key) == value)
            return q.count()
        except Exception:
            session.rollback()                             # [FIX-S2]
            raise
        finally:
            session.close()


class _FakeResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count
        self.deleted_count  = modified_count


# ============================================================
# Singleton — thread-safe via double-checked locking
# ============================================================

_db_manager: Optional[DatabaseManager] = None
_db_lock = threading.Lock()


def get_db() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        with _db_lock:
            if _db_manager is None:
                _db_manager = DatabaseManager()
    return _db_manager
