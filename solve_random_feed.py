"""
Solve simulator — runs as a background daemon.
Every 20-90 minutes it picks a random seed user + machine and inserts a correct submission,
keeping the solve feed alive and realistic.

Run once (background):
  cd ~/ctfwithai
  nohup python3 solve_simulator.py >> logs/simulator.log 2>&1 &

To stop:
  pkill -f solve_simulator.py
"""
import sys, uuid, time, random, logging
from pathlib import Path
from datetime import datetime

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

from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger("simulator")

def get_candidates(session):
    machines = session.execute(
        text("SELECT machine_id FROM generated_machines WHERE deleted_at IS NULL AND status='ready'")
    ).fetchall()
    users = session.execute(
        text("SELECT user_id, username FROM users WHERE user_id LIKE 'seed_%'")
    ).fetchall()
    return machines, users

def already_solved(session, user_id, machine_id):
    return session.query(SubmissionTable).filter_by(
        user_id=user_id, machine_id=machine_id, correct=True
    ).first() is not None

def insert_solve(session, user_id, username, machine_id):
    pts = random.choice([100, 150, 200, 250, 300])
    sub = SubmissionTable(
        submission_id  = f"sim_{uuid.uuid4().hex[:16]}",
        user_id        = user_id,
        machine_id     = machine_id,
        campaign_id    = "seed_campaign",
        submitted_flag = f"HACKFORGE{{sim_{machine_id}}}",
        correct        = True,
        points_awarded = pts,
        submitted_at   = datetime.utcnow(),
    )
    session.add(sub)
    session.commit()
    log.info(f"✅ {username} solved {machine_id} +{pts}pts")

def tick():
    session = SessionLocal()
    try:
        machines, users = get_candidates(session)
        if not machines or not users:
            log.warning("No machines or users found — skipping tick")
            return

        # Try up to 10 random combos to find an unsolved one
        for _ in range(10):
            user    = random.choice(users)
            machine = random.choice(machines)
            if not already_solved(session, user.user_id, machine.machine_id):
                insert_solve(session, user.user_id, user.username, machine.machine_id)
                return

        log.info("All combos already solved — nothing to insert this tick")
    except Exception as e:
        log.error(f"Tick error: {e}", exc_info=True)
    finally:
        session.close()

if __name__ == "__main__":
    log.info("🚀 Solve simulator started")
    while True:
        tick()
        delay = random.randint(20 * 60, 90 * 60)  # 20–90 min
        log.info(f"⏳ Next solve in {delay//60} minutes")
        time.sleep(delay)
