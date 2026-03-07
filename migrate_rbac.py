"""
RBAC Migration — Collapse role + account_type into single role field

Run this ONCE after deploying the updated code.
It will:
  1. Merge existing role/account_type into the new role values
  2. Drop the account_type column from the users table

Usage:
    python migrate_rbac.py
"""
import sys
import os

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
    user_columns = [col['name'] for col in inspector.get_columns('users')]

    with engine.connect() as conn:

        # ── 1. Merge role values ─────────────────────────────────────────────
        # Old: role='staff' + account_type='enterprise'  → role='enterprise_staff'
        # Old: role='admin' + account_type='enterprise'  → role='enterprise_admin'
        # Old: role='instructor' + account_type='enterprise' → role='enterprise_staff'
        # Old: role='individual' + account_type='individual' → role='individual' (no change)

        if 'account_type' in user_columns:
            # Staff & instructor → enterprise_staff
            result1 = conn.execute(text("""
                UPDATE users
                SET role = 'enterprise_staff'
                WHERE account_type = 'enterprise'
                  AND role IN ('staff', 'instructor')
            """))
            print(f"[OK] {result1.rowcount} users updated: staff/instructor → enterprise_staff")

            # Admin → enterprise_admin
            result2 = conn.execute(text("""
                UPDATE users
                SET role = 'enterprise_admin'
                WHERE account_type = 'enterprise'
                  AND role = 'admin'
            """))
            print(f"[OK] {result2.rowcount} users updated: admin → enterprise_admin")

            # Ensure all individual accounts have role='individual'
            result3 = conn.execute(text("""
                UPDATE users
                SET role = 'individual'
                WHERE account_type = 'individual'
                  AND role NOT IN ('individual')
            """))
            print(f"[OK] {result3.rowcount} users normalized to role='individual'")

            conn.commit()

            # ── 2. Drop the account_type column ─────────────────────────────
            conn.execute(text("ALTER TABLE users DROP COLUMN account_type"))
            conn.commit()
            print("[OK] Dropped 'account_type' column from users table")

        else:
            print("[SKIP] 'account_type' column does not exist — migration already applied")

        print("\n[DONE] RBAC migration complete!")
        print("  New role values: individual, enterprise_staff, enterprise_admin")


if __name__ == '__main__':
    migrate()
