"""
VulnForge - Shared Database Layer
SQLite-backed job queue for single machines and campaigns
"""
from pathlib import Path
import sqlite3
import json
import uuid
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get(
    "VULNFORGE_DB",
    str(Path(__file__).resolve().parent / "vulnforge.db")
)


# ─────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe for concurrent readers/writers
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id           TEXT PRIMARY KEY,
            name         TEXT,
            teacher_id   TEXT,
            vuln_spec    TEXT,          -- JSON: shared spec for all students
            student_count INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'pending',
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id           TEXT PRIMARY KEY,
            campaign_id  TEXT,          -- NULL for single-user machines
            student_id   TEXT,          -- session_id for singles, student name for campaigns
            spec_json    TEXT NOT NULL, -- the full generation prompt JSON
            status       TEXT DEFAULT 'pending',   -- pending | generating | done | failed
            port         INTEGER,
            machine_id   TEXT,
            machine_dir  TEXT,
            error        TEXT,
            created_at   TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_campaign ON jobs(campaign_id);

        CREATE TABLE IF NOT EXISTS vulhub_recipes (
            cve_id       TEXT PRIMARY KEY,
            path         TEXT,
            compose_yml  TEXT,
            dockerfile   TEXT,
            port         INTEGER DEFAULT 80,
            tags         TEXT,
            fetched_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS install_strategies (
            cve_id          TEXT PRIMARY KEY,
            base_image      TEXT,
            install_method  TEXT,
            install_package TEXT,
            install_version TEXT,
            extra_commands  TEXT,
            source_url      TEXT,
            fetched_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ctf_challenges (
            challenge_id    TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            source          TEXT NOT NULL,     -- 'ctftraining' | 'sniperoj' | 'omega-coder'
            repo_path       TEXT NOT NULL,     -- path within the repo (e.g. 'web/baby-sqli')
            category        TEXT DEFAULT 'web',-- 'web' | 'pwn' | 'misc' | 'crypto'
            vuln_types      TEXT DEFAULT '[]', -- JSON array: ["sqli", "ssti", "rce", ...]
            description     TEXT DEFAULT '',
            compose_yml     TEXT,
            dockerfile      TEXT,
            port            INTEGER DEFAULT 80,
            difficulty      TEXT DEFAULT 'medium',
            tags            TEXT DEFAULT '[]', -- JSON array of tags
            fetched_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_ctf_source ON ctf_challenges(source);
        CREATE INDEX IF NOT EXISTS idx_ctf_category ON ctf_challenges(category);
        """)
    print(f"[DB] Initialized: {DB_PATH}")


# ─────────────────────────────────────────────
# PORT REGISTRY
# ─────────────────────────────────────────────

PORT_START = 8100
PORT_END   = 8999

def _is_port_free_on_os(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def get_next_port() -> int:
    """
    Pick a random free port in range 8100-8999.
    Double-checks against DB (other jobs) AND OS (other processes).
    """
    import random
    with get_db() as db:
        rows = db.execute("SELECT port FROM jobs WHERE port IS NOT NULL").fetchall()
        used_in_db = {r["port"] for r in rows}

    all_ports = list(range(PORT_START, PORT_END + 1))
    random.shuffle(all_ports)

    for port in all_ports:
        if port in used_in_db:
            continue
        if _is_port_free_on_os(port):
            return port

    raise RuntimeError(f"No free ports available in range {PORT_START}-{PORT_END}")


# ─────────────────────────────────────────────
# JOB CRUD
# ─────────────────────────────────────────────

def create_job(session_id: str, spec: dict, campaign_id: str = None, student_id: str = None) -> str:
    job_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            """INSERT INTO jobs (id, campaign_id, student_id, spec_json, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (job_id, campaign_id, student_id or session_id, json.dumps(spec))
        )
    print(f"[DB] Job created: {job_id}")
    return job_id


def get_job(job_id: str) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_pending_jobs(limit: int = 5) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status + optional fields: port, machine_id, machine_dir, error"""
    fields = {"status": status}
    if status in ("done", "failed"):
        fields["completed_at"] = datetime.utcnow().isoformat()
    fields.update(kwargs)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values     = list(fields.values()) + [job_id]

    with get_db() as db:
        db.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
    print(f"[DB] Job {job_id[:8]}… → {status}")


def list_jobs(limit: int = 50) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT id, student_id, status, port, machine_id, created_at, completed_at "
            "FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# CAMPAIGN CRUD
# ─────────────────────────────────────────────

def create_campaign(name: str, teacher_id: str, vuln_spec: dict, student_count: int) -> str:
    campaign_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            """INSERT INTO campaigns (id, name, teacher_id, vuln_spec, student_count)
               VALUES (?, ?, ?, ?, ?)""",
            (campaign_id, name, teacher_id, json.dumps(vuln_spec), student_count)
        )
    print(f"[DB] Campaign created: {campaign_id}")
    return campaign_id


def get_campaign(campaign_id: str) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        # Attach job stats
        stats = db.execute(
            """SELECT status, COUNT(*) as cnt FROM jobs
               WHERE campaign_id = ? GROUP BY status""",
            (campaign_id,)
        ).fetchall()
        result["job_stats"] = {r["status"]: r["cnt"] for r in stats}
        return result


def get_campaign_jobs(campaign_id: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM jobs WHERE campaign_id = ? ORDER BY created_at ASC",
            (campaign_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# VULHUB RECIPES CRUD
# ─────────────────────────────────────────────

def store_vulhub_recipe(cve_id: str, path: str, compose_yml: str,
                         dockerfile: str, port: int, tags: list):
    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO vulhub_recipes
               (cve_id, path, compose_yml, dockerfile, port, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cve_id, path, compose_yml, dockerfile or "", port, json.dumps(tags))
        )


def get_vulhub_recipe(cve_id: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM vulhub_recipes WHERE cve_id = ?", (cve_id,)
        ).fetchone()
        if not row:
            return None
        r = dict(row)
        r["tags"] = json.loads(r.get("tags") or "[]")
        return r


def get_vulhub_count() -> int:
    with get_db() as db:
        return db.execute("SELECT COUNT(*) FROM vulhub_recipes").fetchone()[0]


# ─────────────────────────────────────────────
# INSTALL STRATEGIES CRUD
# ─────────────────────────────────────────────

def store_install_strategy(cve_id: str, base_image: str, install_method: str,
                            install_package: str, install_version: str,
                            extra_commands: list, source_url: str):
    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO install_strategies
               (cve_id, base_image, install_method, install_package,
                install_version, extra_commands, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cve_id, base_image, install_method, install_package,
             install_version, json.dumps(extra_commands), source_url)
        )


def get_install_strategy(cve_id: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM install_strategies WHERE cve_id = ?", (cve_id,)
        ).fetchone()
        if not row:
            return None
        r = dict(row)
        r["extra_commands"] = json.loads(r.get("extra_commands") or "[]")
        return r

# ─────────────────────────────────────────────
# CTF CHALLENGES CRUD
# ─────────────────────────────────────────────

def store_ctf_challenge(challenge_id: str, name: str, source: str,
                         repo_path: str, category: str = "web",
                         vuln_types: list = None, description: str = "",
                         compose_yml: str = "", dockerfile: str = "",
                         port: int = 80, difficulty: str = "medium",
                         tags: list = None):
    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO ctf_challenges
               (challenge_id, name, source, repo_path, category,
                vuln_types, description, compose_yml, dockerfile,
                port, difficulty, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (challenge_id, name, source, repo_path, category,
             json.dumps(vuln_types or []), description,
             compose_yml or "", dockerfile or "", port, difficulty,
             json.dumps(tags or []))
        )


def get_ctf_challenge(challenge_id: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM ctf_challenges WHERE challenge_id = ?",
            (challenge_id,)
        ).fetchone()
        if not row:
            return None
        r = dict(row)
        r["vuln_types"] = json.loads(r.get("vuln_types") or "[]")
        r["tags"] = json.loads(r.get("tags") or "[]")
        return r


def list_ctf_challenges(source: str = None, category: str = None) -> list[dict]:
    with get_db() as db:
        query = "SELECT * FROM ctf_challenges WHERE 1=1"
        params = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY name ASC"
        rows = db.execute(query, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            r["vuln_types"] = json.loads(r.get("vuln_types") or "[]")
            r["tags"] = json.loads(r.get("tags") or "[]")
            results.append(r)
        return results


def get_ctf_count(source: str = None) -> int:
    with get_db() as db:
        if source:
            return db.execute(
                "SELECT COUNT(*) FROM ctf_challenges WHERE source = ?",
                (source,)
            ).fetchone()[0]
        return db.execute("SELECT COUNT(*) FROM ctf_challenges").fetchone()[0]


if __name__ == "__main__":
    init_db()
    print("✅ DB ready")
