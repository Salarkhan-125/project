"""
Shared dependencies for HackForge API

Two database systems run in parallel — they serve different purposes
and must never replace each other:

  db   → MySQL (DatabaseManager)  — users, sessions, campaigns,
                                     progress, submissions, leaderboard
  vfdb → SQLite (VulnForge queue) — machine generation job queue,
                                     VulnForge worker communication
"""
import sys
from .config import (
    CORE_PATH,
    DOCKER_PATH,
    DATABASE_PATH,
    GENERATED_MACHINES_DIR,
    logger
)

# ── Ensure all required paths are on sys.path ─────────────────────────────────
for path in (CORE_PATH, DOCKER_PATH, DATABASE_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


# ── 1. MySQL DatabaseManager (primary application database) ──────────────────
#       Handles: users, sessions, campaigns, progress, submissions, leaderboard
try:
    from database import get_db
    db = get_db()
    logger.info("✓ MySQL DatabaseManager (db) initialized")
except ImportError as e:
    logger.error(f"✗ Failed to import database (MySQL): {e}")
    logger.error("  Make sure database.py exists and DATABASE_PATH is correct")
    logger.error("  Install dependencies: pip install sqlalchemy pymysql")
    raise
except Exception as e:
    logger.error(f"✗ Failed to initialize MySQL DatabaseManager: {e}")
    raise


# ── 2. VulnForge SQLite job queue (machine generation only) ──────────────────
#       Handles: machine generation jobs, VulnForge worker communication
try:
    import vfdb
    vfdb.init_db()
    logger.info("✓ VulnForge SQLite queue (vfdb) initialized")
except ImportError as e:
    logger.error(f"✗ Failed to import vfdb (VulnForge SQLite): {e}")
    logger.error("  Make sure core/vfdb.py exists and CORE_PATH is correct")
    raise
except Exception as e:
    logger.error(f"✗ Failed to initialize vfdb: {e}")
    raise


logger.info(f"Machines directory: {GENERATED_MACHINES_DIR}")
logger.info("✓ All dependencies initialized")
logger.info("  • db   → MySQL  (users, campaigns, progress, sessions, submissions)")
logger.info("  • vfdb → SQLite (VulnForge machine generation job queue)")

# ── 3. Legacy orchestrator stub ───────────────────────────────────────────────
#       The old Orchestrator class has been replaced by bridge.py + docker SDK.
#       docker.py and flags.py import this name; setting to None keeps them
#       loading without crashing. Any endpoint that calls orchestrator.*
#       will gracefully fail at runtime (not at startup).
orchestrator = None
