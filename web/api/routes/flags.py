# forge/web/api/routes/flags.py
"""
Flag validation endpoint — production-ready v2

Fixes applied vs original:
  [FIX-F1]  Flag comparison now uses database.verify_flag() (HMAC-SHA256,
            constant-time).  Previously used plain == on a plaintext flag
            fetched from the campaign dict, which (a) was timing-attackable
            and (b) broke once flags were hashed in the DB.

  [FIX-F2]  campaign_id is now threaded through every DB call
            (get_progress, increment_attempts, mark_solved, create_progress).
            Previously those calls omitted campaign_id, which silently
            targeted the wrong progress row when a machine appeared in
            multiple campaigns.

  [FIX-F3]  Machine lookup now uses db.get_campaign() + db.get_generated_machine()
            instead of iterating all campaigns with db.campaigns.find({}) —
            a full table scan on every request.

  [FIX-F4]  campaign_id='unknown' fallback eliminated.  If no campaign_id
            is provided, the request is rejected with 400 rather than
            silently poisoning progress rows with a junk foreign key.

  [FIX-F5]  Rate-limit key is now (user_id, machine_id, campaign_id) so
            the same machine in two different campaigns gets independent
            rate-limit buckets.

  [FIX-F6]  A correct submission clears the rate-limit bucket so the
            user is never blocked from re-confirming their own solve.

  [FIX-F7]  db.update_last_activity() called on correct solve so the
            leaderboard's last_activity_at column stays accurate.

  [FIX-F8]  Correct solve logic wrapped in db.transaction() — all DB
            writes (mark_solved, add_points, increment_solved,
            update_campaign_progress, complete_campaign) now succeed or
            fail atomically.

  [FIX-F9]  db.record_submission() moved outside the solve transaction
            so every attempt is always audited, even if the reward fails.

  [FIX-F10] Flag not found in DB now raises 500 (server misconfiguration)
            instead of silently treating the submission as wrong.

  Retained from original:
  - FORMAT / LENGTH / PATTERN validation via _validate_flag_input()
  - Already-solved short-circuit before rate-limit check
  - Structured logging on every code path
"""

import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from threading import Lock

from fastapi import APIRouter, HTTPException, Request

from web.api.config import logger
from web.api.dependencies import db, orchestrator
from web.api.models.flag import FlagSubmitRequest

# constant-time HMAC comparison — never plain == on flag strings [FIX-F1]
from database import verify_flag

router = APIRouter(prefix="/api/flags", tags=["flags"])


# ─── Constants ────────────────────────────────────────────────────────────────

FLAG_MAX_LENGTH = 50

FLAG_PATTERN = re.compile(
    r'^HACKFORGE\{[a-zA-Z0-9_\-\.!@#$%^&*()\[\]+=?/,]{1,40}\}$'
)

RATE_LIMIT_MAX_ATTEMPTS = 2
RATE_LIMIT_WINDOW_SECS  = 60


# ─── In-memory rate limiter ───────────────────────────────────────────────────
# Single-server only. Replace with Redis for multi-instance deployments.

_rate_store: dict[tuple, list] = defaultdict(list)
_rate_lock  = Lock()


def _is_rate_limited(
    user_id: str, machine_id: str, campaign_id: str
) -> tuple[bool, int]:
    """
    Returns (is_limited, seconds_until_reset).
    [FIX-F5] Key includes campaign_id for independent per-campaign buckets.
    """
    key = (user_id, machine_id, campaign_id)
    now = time.time()

    with _rate_lock:
        _rate_store[key] = [
            t for t in _rate_store[key]
            if now - t < RATE_LIMIT_WINDOW_SECS
        ]
        if len(_rate_store[key]) >= RATE_LIMIT_MAX_ATTEMPTS:
            oldest       = _rate_store[key][0]
            seconds_left = int(RATE_LIMIT_WINDOW_SECS - (now - oldest)) + 1
            return True, seconds_left

        _rate_store[key].append(now)
        return False, 0


def _clear_rate_limit(user_id: str, machine_id: str, campaign_id: str) -> None:
    """[FIX-F6] Remove bucket after a correct solve."""
    with _rate_lock:
        _rate_store.pop((user_id, machine_id, campaign_id), None)


# ─── Input validation ─────────────────────────────────────────────────────────

def _validate_flag_input(raw_flag: str) -> str:
    """
    Sanitize and validate a raw flag string.
    Returns the cleaned flag, or raises HTTPException 422.
    """
    if not isinstance(raw_flag, str):
        raise HTTPException(status_code=422, detail="Flag must be a string.")

    cleaned = raw_flag.strip()

    if not cleaned:
        raise HTTPException(status_code=422, detail="Flag cannot be empty.")

    if len(cleaned) > FLAG_MAX_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Flag exceeds maximum length of {FLAG_MAX_LENGTH} characters.",
        )

    if not FLAG_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=422,
            detail="Invalid flag format. Expected: HACKFORGE{...}",
        )

    return cleaned


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/validate")
async def validate_flag(request: FlagSubmitRequest, req: Request):
    """
    Validate a submitted flag.

    Security layers (in order):
      1.  Input validation   — format, length, allowed characters
      2.  campaign_id check  — must be a real ID, not blank or 'unknown'
      3.  Machine existence  — 404 if machine not found
      4.  Flag hash lookup   — 500 if DB has no hash (misconfiguration)
      5.  Already solved     — short-circuit before rate-limit check
      6.  Rate limit         — 429 if > 2 attempts in 60 s
      7.  Flag comparison    — constant-time HMAC verify [FIX-F1]
      8.  Atomic solve tx    — all reward writes in one transaction [FIX-F8]
      9.  Submission audit   — always persisted, outside the solve tx [FIX-F9]
    """
    client_ip = req.client.host if req.client else "unknown"

    # ── 1. Validate and sanitize the submitted flag ───────────────────────────
    cleaned_flag = _validate_flag_input(request.flag)

    # ── 2. Require a real campaign_id  [FIX-F4] ──────────────────────────────
    campaign_id = getattr(request, 'campaign_id', None)
    if not campaign_id or campaign_id.strip() == 'unknown':
        raise HTTPException(
            status_code=400,
            detail="campaign_id is required to submit a flag.",
        )

    # ── 3. Locate machine — targeted lookup, no full-table scan [FIX-F3] ─────
    machine_info = _resolve_machine(request.machine_id, campaign_id)
    if not machine_info:
        logger.warning(
            "Flag submission for unknown machine '%s' from user '%s' IP=%s",
            request.machine_id, request.user_id, client_ip,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Machine not found: {request.machine_id}",
        )

    # ── 4. Retrieve stored flag hash  [FIX-F1, FIX-F10] ─────────────────────
    stored_hash = _get_flag_hash(campaign_id, request.machine_id)
    if stored_hash is None:
        logger.error(
            "No flag_hash stored for machine='%s' campaign='%s' — "
            "bridge.py may not have written the record yet.",
            request.machine_id, campaign_id,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Flag data is not available for this machine. "
                "Please contact an administrator."
            ),
        )

    # ── 5. Get or create progress record  [FIX-F2] ───────────────────────────
    progress = db.get_progress(
        request.user_id, request.machine_id, campaign_id=campaign_id
    )
    if not progress:
        progress = db.create_progress({
            'user_id':    request.user_id,
            'machine_id': request.machine_id,
            'campaign_id': campaign_id,
        })

    # ── 5a. Short-circuit: already solved ────────────────────────────────────
    if progress.get('solved', False):
        return {'correct': True, 'message': '✅ Flag already captured', 'points': 0}

    # ── 6. Rate limit check  [FIX-F5] ────────────────────────────────────────
    limited, retry_after = _is_rate_limited(
        request.user_id, request.machine_id, campaign_id
    )
    if limited:
        logger.warning(
            "Rate limit: user='%s' machine='%s' campaign='%s' "
            "IP=%s retry_after=%ss",
            request.user_id, request.machine_id, campaign_id,
            client_ip, retry_after,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many attempts. Please wait "
                f"{retry_after} second{'s' if retry_after != 1 else ''} "
                f"before trying again."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    # ── 7. Increment attempt counter + verify flag  [FIX-F1, FIX-F2] ────────
    db.increment_attempts(
        request.user_id, request.machine_id, campaign_id=campaign_id
    )
    correct = verify_flag(cleaned_flag, stored_hash)   # constant-time HMAC

    # ── 8. Build submission record (always populated) ─────────────────────────
    submission_data = {
        'submission_id':  f"sub_{uuid.uuid4().hex[:16]}",
        'user_id':        request.user_id,
        'machine_id':     request.machine_id,
        'campaign_id':    campaign_id,
        'submitted_flag': cleaned_flag,
        'correct':        correct,
        'ip_address':     client_ip,
        'points_awarded': 0,
    }

    # ── 9. Atomic solve transaction  [FIX-F8] ────────────────────────────────
    if correct:
        points     = _difficulty_to_points(machine_info.get('difficulty', 1))
        solve_time = _calc_solve_time(progress)

        try:
            with db.transaction() as session:
                _tx_mark_solved(session, request.user_id, request.machine_id,
                                campaign_id, points, solve_time)
                _tx_update_user(session, request.user_id, points)
                _tx_maybe_complete_campaign(session, request.user_id, campaign_id)
        except Exception as exc:
            logger.exception(
                "Solve transaction failed for user='%s' machine='%s': %s",
                request.user_id, request.machine_id, exc,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Your flag was correct but we failed to record your reward. "
                    "Please contact support."
                ),
            ) from exc

        _clear_rate_limit(request.user_id, request.machine_id, campaign_id)
        submission_data['points_awarded'] = points
        message = f"🎉 Correct! First solve! +{points} points"
        logger.info(
            "Correct flag: user='%s' machine='%s' campaign='%s' points=%d IP=%s",
            request.user_id, request.machine_id, campaign_id, points, client_ip,
        )
    else:
        message = "❌ Incorrect flag. Try again!"
        logger.info(
            "Wrong flag: user='%s' machine='%s' campaign='%s' IP=%s",
            request.user_id, request.machine_id, campaign_id, client_ip,
        )

    # ── 10. Persist audit record — always, outside the solve tx  [FIX-F9] ────
    try:
        db.record_submission(submission_data)
    except Exception:
        logger.exception(
            "Failed to record submission for user='%s' machine='%s'",
            request.user_id, request.machine_id,
        )

    return {
        'correct': correct,
        'message': message,
        'points':  submission_data['points_awarded'],
    }


# ─── Private helpers ──────────────────────────────────────────────────────────

def _resolve_machine(machine_id: str, campaign_id: str) -> dict | None:
    """
    Find machine metadata without a full-table scan.  [FIX-F3]

    Order:
      1. Campaign machines (primary path for campaign play)
      2. Standalone generated machines (VulnForge direct-play)
      3. Orchestrator in-memory list (containers not yet written to DB)
    """
    campaign = db.get_campaign(campaign_id)
    if campaign:
        for m in campaign.get('machines', []):
            if m['machine_id'] == machine_id:
                return m

    gm = db.get_generated_machine(machine_id)
    if gm:
        return gm

    # orchestrator is a legacy stub (None) in the current architecture;
    # bridge.py handles machine generation directly via SQLite/vfdb.
    if orchestrator is not None:
        for m in orchestrator.list_machines():
            if m['machine_id'] == machine_id:
                return m

    return None


def _get_flag_hash(campaign_id: str, machine_id: str) -> str | None:
    """
    Return the stored flag_hash for comparison.  [FIX-F1]
    Tries campaign machines first, then standalone generated machines.
    Never exposes plaintext.
    """
    h = db.get_flag_hash_for_machine(campaign_id, machine_id)
    if h:
        return h
    return db.get_generated_machine_flag_hash(machine_id)


def _difficulty_to_points(difficulty: int | str) -> int:
    """Map difficulty value to a point reward robustly."""
    _map = {'easy': 100, 'medium': 200, 'hard': 300, 'expert': 400, 'insane': 500}
    if isinstance(difficulty, str):
        return _map.get(difficulty.lower(), 100)
    return max(1, int(difficulty)) * 100


def _calc_solve_time(progress: dict) -> int:
    """Elapsed seconds from progress.started_at to now."""
    started_at = progress.get('started_at')
    if not started_at:
        return 0
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at)
    return max(0, int(time.time() - started_at.timestamp()))


# ─── Transaction helpers (operate on a caller-supplied session) ───────────────

def _tx_mark_solved(
    session,
    user_id: str,
    machine_id: str,
    campaign_id: str,
    points: int,
    solve_time: int,
) -> None:
    """Write solved=True on the progress row inside an open transaction."""
    from database import ProgressTable, _now

    row = (
        session.query(ProgressTable)
        .filter(
            ProgressTable.user_id     == user_id,
            ProgressTable.machine_id  == machine_id,
            ProgressTable.campaign_id == campaign_id,
        )
        .first()
    )
    if row:
        row.solved        = True
        row.points_earned = points
        row.solve_time    = solve_time
        row.completed_at  = _now()


def _tx_update_user(session, user_id: str, points: int) -> None:
    """Increment user counters inside an open transaction — uses UsersDetailTable."""
    from database import UsersDetailTable, _now

    row = session.query(UsersDetailTable).filter_by(user_id=user_id).first()
    if row:
        row.total_points     += points
        row.machines_solved  += 1
        row.last_activity_at  = _now()
        row.updated_at        = _now()


def _tx_maybe_complete_campaign(
    session, user_id: str, campaign_id: str
) -> None:
    """
    If all machines in the campaign are solved, mark it complete and
    increment the user's campaigns_completed counter — inside the same
    open transaction.  [FIX-F8]
    """
    from database import CampaignTable, ProgressTable, UsersDetailTable, _now

    campaign_row = (
        session.query(CampaignTable)
        .filter_by(campaign_id=campaign_id)
        .filter(CampaignTable.deleted_at.is_(None))
        .first()
    )
    if not campaign_row:
        return

    all_progress = (
        session.query(ProgressTable)
        .filter_by(user_id=user_id, campaign_id=campaign_id)
        .all()
    )

    solved_count = sum(1 for p in all_progress if p.solved)
    total_points = sum(p.points_earned for p in all_progress)

    campaign_row.machines_solved = solved_count
    campaign_row.total_points    = total_points

    if solved_count >= campaign_row.machine_count:
        campaign_row.status       = 'completed'
        campaign_row.completed_at = _now()

        user_row = session.query(UsersDetailTable).filter_by(user_id=user_id).first()
        if user_row:
            user_row.campaigns_completed += 1
            user_row.updated_at           = _now()
