"""
One-time migration script to add enterprise columns to existing MySQL tables.
Run this once after updating database.py with the new OrganizationTable and enterprise fields.

Usage:
    python migrate_enterprise.py
"""
import sys
import os

# Add the project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / '.env')

from sqlalchemy import create_engine, text, inspect

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'mysql+pymysql://root:yourpassword@localhost:3306/hackforge'
)

engine = create_engine(DATABASE_URL, echo=False)


def migrate():
    inspector = inspect(engine)

    with engine.connect() as conn:
        # ── 1. Create organizations table if it doesn't exist ────────────────
        existing_tables = inspector.get_table_names()
        if 'organizations' not in existing_tables:
            conn.execute(text("""
                CREATE TABLE organizations (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    organization_id VARCHAR(64) NOT NULL UNIQUE,
                    name            VARCHAR(256) NOT NULL,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_org_id (organization_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            print("[OK] Created 'organizations' table")
        else:
            print("[SKIP] 'organizations' table already exists")

        # ── 2. Add account_type column to users table ────────────────────────
        user_columns = [col['name'] for col in inspector.get_columns('users')]

        if 'account_type' not in user_columns:
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN account_type VARCHAR(32) NOT NULL DEFAULT 'individual'
                AFTER `role`
            """))
            print("[OK] Added 'account_type' column to users")
        else:
            print("[SKIP] 'account_type' column already exists in users")

        # ── 3. Add organization_id column to users table ─────────────────────
        if 'organization_id' not in user_columns:
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN organization_id VARCHAR(64) NULL DEFAULT NULL
                AFTER account_type
            """))
            # Add foreign key
            conn.execute(text("""
                ALTER TABLE users
                ADD CONSTRAINT fk_users_organization
                FOREIGN KEY (organization_id) REFERENCES organizations(organization_id)
                ON DELETE SET NULL
            """))
            conn.execute(text("""
                CREATE INDEX idx_users_org_id ON users (organization_id)
            """))
            print("[OK] Added 'organization_id' column to users (with FK)")
        else:
            print("[SKIP] 'organization_id' column already exists in users")

        conn.commit()
        print("\n[DONE] Migration complete!")


if __name__ == '__main__':
    migrate()
