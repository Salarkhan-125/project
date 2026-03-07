"""
Run from project root:
  cd ~/ctfwithai
  python seed_leaderboard.py

Creates 10 fake users with realistic points/machines_solved data
so the leaderboard has entries to display.
"""

import sys, os, uuid, random
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'web' / 'database'))

import importlib.util, types

# Bypass web/database/__init__.py (it has a broken relative import)
spec = importlib.util.spec_from_file_location(
    "database",
    root / "web" / "database" / "database.py"
)
db_mod = importlib.util.module_from_spec(spec)
sys.modules["database"] = db_mod
spec.loader.exec_module(db_mod)

get_db    = db_mod.get_db
hash_flag = db_mod.hash_flag
SessionLocal   = db_mod.SessionLocal
SubmissionTable = db_mod.SubmissionTable
_now           = db_mod._now
import bcrypt

db = get_db()

FAKE_USERS = [
    ("ghost_root",   "ghost@hackforge.io",   1200, 8),
    ("xpl01t3r",     "xploit@hackforge.io",  980,  6),
    ("nullbyte",     "null@hackforge.io",     850,  5),
    ("r3v3rse_me",   "reverse@hackforge.io",  720,  4),
    ("p4yload",      "payload@hackforge.io",  600,  4),
    ("sh3llsh0ck",   "shell@hackforge.io",    450,  3),
    ("binw4lker",    "binwalk@hackforge.io",  350,  2),
    ("0verfl0w",     "overflow@hackforge.io", 250,  2),
    ("n00b_h4x",     "noob@hackforge.io",     150,  1),
    ("l34rn3r",      "learner@hackforge.io",  100,  1),
]

hashed_pw = bcrypt.hashpw(b"Hackforge@123", bcrypt.gensalt()).decode()

created = 0
skipped = 0

for username, email, points, machines in FAKE_USERS:
    # Skip if already exists
    existing = db.get_user_by_username(username)
    if existing:
        print(f"  SKIP  {username} (already exists)")
        skipped += 1
        continue

    user_id = f"seed_{uuid.uuid4().hex[:12]}"
    db.create_user({
        "user_id":          user_id,
        "username":         username,
        "email":            email,
        "password":         hashed_pw,
        "role":             "individual",
        "total_points":     points,
        "machines_solved":  machines,
        "campaigns_completed": 0,
    })

    # Record a dummy submission so they pass the "has submitted" filter
    session = SessionLocal()
    try:
        sub = SubmissionTable(
            submission_id  = f"seed_sub_{uuid.uuid4().hex[:16]}",
            user_id        = user_id,
            machine_id     = "seed_machine",
            campaign_id    = "seed_campaign",
            submitted_flag = "HACKFORGE{seed}",
            correct        = True,
            points_awarded = points,
            submitted_at   = _now(),
        )
        session.add(sub)
        session.commit()
    finally:
        session.close()

    print(f"  OK    {username}  pts={points}  machines={machines}")
    created += 1

print(f"\nDone — {created} created, {skipped} skipped.")
