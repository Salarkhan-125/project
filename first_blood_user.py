"""
Seeds realistic solve history for the feed and leaderboard.
Run: cd ~/ctfwithai && python3 seed_solves.py
"""
import sys, uuid
from pathlib import Path
from datetime import datetime, timedelta
import random

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'web' / 'database'))

import importlib.util
spec = importlib.util.spec_from_file_location("database", root / "web" / "database" / "database.py")
db_mod = importlib.util.module_from_spec(spec)
sys.modules["database"] = db_mod
spec.loader.exec_module(db_mod)

SessionLocal    = db_mod.SessionLocal
SubmissionTable = db_mod.SubmissionTable
UserTable       = db_mod.UserTable

session = SessionLocal()

# Get real machines
from sqlalchemy import text
machines = session.execute(text("SELECT machine_id, cve_id FROM generated_machines WHERE deleted_at IS NULL")).fetchall()
if not machines:
    print("No machines found — generate some via Vuln AI first.")
    session.close()
    sys.exit(0)

# Get seed users (the fake leaderboard ones)
seed_users = session.execute(
    text("SELECT user_id, username FROM users WHERE user_id LIKE 'seed_%'")
).fetchall()

print(f"Found {len(machines)} machines, {len(seed_users)} seed users")

now = datetime.utcnow()
created = 0

for machine in machines:
    machine_id = machine.machine_id
    cve_id     = machine.cve_id

    # Shuffle users so first blood is random
    solvers = list(seed_users)
    random.shuffle(solvers)

    # Pick 4-7 users to have solved this machine
    num_solvers = random.randint(4, min(7, len(solvers)))
    solvers = solvers[:num_solvers]

    for i, user in enumerate(solvers):
        # Check if submission already exists
        exists = session.query(SubmissionTable).filter_by(
            user_id=user.user_id, machine_id=machine_id, correct=True
        ).first()
        if exists:
            print(f"  SKIP {user.username} already solved {machine_id}")
            continue

        # Stagger solve times — first blood is earliest
        hours_ago = random.randint(i * 2 + 1, i * 2 + 6)
        solved_at = now - timedelta(hours=hours_ago, minutes=random.randint(0, 59))

        pts = random.choice([100, 150, 200, 250, 300])

        sub = SubmissionTable(
            submission_id  = f"sub_{uuid.uuid4().hex[:16]}",
            user_id        = user.user_id,
            machine_id     = machine_id,
            campaign_id    = "seed_campaign",
            submitted_flag = f"CTFWITHAI{{seed_{cve_id}}}",
            correct        = True,
            points_awarded = pts,
            submitted_at   = solved_at,
        )
        session.add(sub)
        created += 1
        blood = "🩸 FIRST BLOOD" if i == 0 else ""
        print(f"  OK  {user.username:15} → {machine_id}  +{pts}pts  {blood}")

session.commit()
session.close()
print(f"\nDone — {created} solves seeded.")
