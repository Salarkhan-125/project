"""
Database Restructuring Migration Script
========================================
Migrates the hackforge database from a single 'users' table to:
  - org_admins    (enterprise_admin accounts)
  - org_staff     (enterprise_staff accounts)
  - users         (individual accounts only)
  - users_detail  (extended profile & stats for individual accounts)

Run:  python migrate_db_restructure.py

This script is idempotent — re-running it is safe; it checks for existing
tables and data before each step.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# ── Load .env ────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Check your .env file.")
    sys.exit(1)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def step(n, title):
    print(f"\n{'='*60}")
    print(f"  STEP {n}: {title}")
    print(f"{'='*60}")


def table_exists(name):
    insp = inspect(engine)
    return name in insp.get_table_names()


def column_exists(table, col):
    insp = inspect(engine)
    columns = [c['name'] for c in insp.get_columns(table)]
    return col in columns


def main():
    print("\n🔧 HackForge Database Restructuring Migration")
    print(f"   Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"   Time:     {datetime.now().isoformat()}\n")

    session = Session()

    try:
        # ── Pre-flight: count existing data ──────────────────────────
        total_users = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        admin_count = session.execute(text(
            "SELECT COUNT(*) FROM users WHERE role = 'enterprise_admin'"
        )).scalar()
        staff_count = session.execute(text(
            "SELECT COUNT(*) FROM users WHERE role = 'enterprise_staff'"
        )).scalar()
        individual_count = session.execute(text(
            "SELECT COUNT(*) FROM users WHERE role = 'individual'"
        )).scalar()

        print(f"📊 Current users table: {total_users} total")
        print(f"   • {individual_count} individual")
        print(f"   • {admin_count} enterprise_admin")
        print(f"   • {staff_count} enterprise_staff")

        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Create org_admins table
        # ═══════════════════════════════════════════════════════════════
        step(1, "Create org_admins table")
        if table_exists('org_admins'):
            print("   ⏭  Table 'org_admins' already exists — skipping creation.")
        else:
            session.execute(text("""
                CREATE TABLE org_admins (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    user_id         VARCHAR(64)  NOT NULL UNIQUE,
                    email           VARCHAR(256) NOT NULL UNIQUE,
                    password        VARCHAR(256) NOT NULL,
                    org_name        VARCHAR(256) NOT NULL,
                    organization_id VARCHAR(64)  NOT NULL,
                    role            VARCHAR(32)  NOT NULL DEFAULT 'enterprise_admin',
                    account_type    VARCHAR(32)  NOT NULL DEFAULT 'enterprise',
                    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    last_activity_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_oa_user_id (user_id),
                    INDEX idx_oa_email (email),
                    INDEX idx_oa_org (organization_id),
                    INDEX idx_oa_activity (last_activity_at),
                    FOREIGN KEY (organization_id)
                        REFERENCES organizations(organization_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            session.commit()
            print("   ✅ Created 'org_admins' table.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: Migrate enterprise_admin rows → org_admins
        # ═══════════════════════════════════════════════════════════════
        step(2, "Migrate enterprise_admin → org_admins")
        existing_admins = session.execute(text(
            "SELECT COUNT(*) FROM org_admins"
        )).scalar()
        if existing_admins > 0:
            print(f"   ⏭  org_admins already has {existing_admins} rows — skipping migration.")
        elif admin_count > 0:
            session.execute(text("""
                INSERT INTO org_admins (user_id, email, password, org_name, organization_id,
                                        role, account_type, created_at, updated_at, last_activity_at)
                SELECT u.user_id, u.email, u.password,
                       COALESCE(o.name, ''),
                       u.organization_id,
                       'enterprise_admin', 'enterprise',
                       u.created_at, u.updated_at, u.last_activity_at
                FROM users u
                LEFT JOIN organizations o ON u.organization_id = o.organization_id
                WHERE u.role = 'enterprise_admin'
                  AND u.organization_id IS NOT NULL
            """))
            session.commit()
            migrated = session.execute(text("SELECT COUNT(*) FROM org_admins")).scalar()
            print(f"   ✅ Migrated {migrated} enterprise_admin rows to org_admins.")
        else:
            print("   ⏭  No enterprise_admin rows to migrate.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: Create org_staff table
        # ═══════════════════════════════════════════════════════════════
        step(3, "Create org_staff table")
        if table_exists('org_staff'):
            print("   ⏭  Table 'org_staff' already exists — skipping creation.")
        else:
            session.execute(text("""
                CREATE TABLE org_staff (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    user_id         VARCHAR(64)  NOT NULL UNIQUE,
                    full_name       VARCHAR(256),
                    email           VARCHAR(256) NOT NULL UNIQUE,
                    password        VARCHAR(256) NOT NULL,
                    org_name        VARCHAR(256) NOT NULL,
                    organization_id VARCHAR(64)  NOT NULL,
                    role            VARCHAR(32)  NOT NULL DEFAULT 'enterprise_staff',
                    account_type    VARCHAR(32)  NOT NULL DEFAULT 'enterprise',
                    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    last_activity_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_os_user_id (user_id),
                    INDEX idx_os_email (email),
                    INDEX idx_os_org (organization_id),
                    INDEX idx_os_activity (last_activity_at),
                    FOREIGN KEY (organization_id)
                        REFERENCES organizations(organization_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            session.commit()
            print("   ✅ Created 'org_staff' table.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 4: Migrate enterprise_staff rows → org_staff
        # ═══════════════════════════════════════════════════════════════
        step(4, "Migrate enterprise_staff → org_staff")
        existing_staff = session.execute(text(
            "SELECT COUNT(*) FROM org_staff"
        )).scalar()
        if existing_staff > 0:
            print(f"   ⏭  org_staff already has {existing_staff} rows — skipping migration.")
        elif staff_count > 0:
            session.execute(text("""
                INSERT INTO org_staff (user_id, full_name, email, password, org_name,
                                       organization_id, role, account_type,
                                       created_at, updated_at, last_activity_at)
                SELECT u.user_id, u.full_name, u.email, u.password,
                       COALESCE(o.name, ''),
                       u.organization_id,
                       'enterprise_staff', 'enterprise',
                       u.created_at, u.updated_at, u.last_activity_at
                FROM users u
                LEFT JOIN organizations o ON u.organization_id = o.organization_id
                WHERE u.role = 'enterprise_staff'
                  AND u.organization_id IS NOT NULL
            """))
            session.commit()
            migrated = session.execute(text("SELECT COUNT(*) FROM org_staff")).scalar()
            print(f"   ✅ Migrated {migrated} enterprise_staff rows to org_staff.")
        else:
            print("   ⏭  No enterprise_staff rows to migrate.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 5: Update stu_detail FK reference
        # ═══════════════════════════════════════════════════════════════
        step(5, "Update stu_detail FK (users → org_staff)")
        if table_exists('stu_detail'):
            # Check if the FK still references users
            try:
                # Drop old FK and add new one pointing to org_staff
                # First, find the constraint name
                fk_rows = session.execute(text("""
                    SELECT CONSTRAINT_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'stu_detail'
                      AND COLUMN_NAME = 'staff_user_id'
                      AND REFERENCED_TABLE_NAME = 'users'
                """)).fetchall()

                if fk_rows:
                    for fk_row in fk_rows:
                        fk_name = fk_row[0]
                        session.execute(text(f"ALTER TABLE stu_detail DROP FOREIGN KEY `{fk_name}`"))
                        print(f"   Dropped old FK: {fk_name}")

                    session.execute(text("""
                        ALTER TABLE stu_detail
                        ADD CONSTRAINT fk_stu_staff_org
                        FOREIGN KEY (staff_user_id) REFERENCES org_staff(user_id)
                        ON DELETE CASCADE
                    """))
                    session.commit()
                    print("   ✅ Updated stu_detail FK to reference org_staff.user_id")
                else:
                    print("   ⏭  FK already updated or not found — skipping.")
            except Exception as e:
                print(f"   ⚠  FK update skipped (may already be correct): {e}")
                session.rollback()
        else:
            print("   ⏭  stu_detail table does not exist — skipping.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 6: Create users_detail table
        # ═══════════════════════════════════════════════════════════════
        step(6, "Create users_detail table")
        if table_exists('users_detail'):
            print("   ⏭  Table 'users_detail' already exists — skipping creation.")
        else:
            session.execute(text("""
                CREATE TABLE users_detail (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    user_id          VARCHAR(64) NOT NULL UNIQUE,
                    full_name        VARCHAR(256),
                    email            VARCHAR(256),
                    total_points     INT DEFAULT 0,
                    machines_solved  INT DEFAULT 0,
                    campaigns_completed INT DEFAULT 0,
                    current_streak   INT DEFAULT 0,
                    longest_streak   INT DEFAULT 0,
                    preferences      JSON,
                    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_ud_user_id (user_id),
                    INDEX idx_ud_activity (last_activity_at),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            session.commit()
            print("   ✅ Created 'users_detail' table.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 7: Migrate individual user stats → users_detail
        # ═══════════════════════════════════════════════════════════════
        step(7, "Migrate individual user stats → users_detail")
        existing_details = session.execute(text(
            "SELECT COUNT(*) FROM users_detail"
        )).scalar()
        if existing_details > 0:
            print(f"   ⏭  users_detail already has {existing_details} rows — skipping.")
        elif individual_count > 0:
            # Check which columns exist before migrating
            has_total_points = column_exists('users', 'total_points')
            if has_total_points:
                session.execute(text("""
                    INSERT INTO users_detail (user_id, full_name, email,
                                              total_points, machines_solved,
                                              campaigns_completed, current_streak,
                                              longest_streak, preferences,
                                              updated_at, last_activity_at)
                    SELECT user_id, full_name, email,
                           COALESCE(total_points, 0),
                           COALESCE(machines_solved, 0),
                           COALESCE(campaigns_completed, 0),
                           COALESCE(current_streak, 0),
                           COALESCE(longest_streak, 0),
                           preferences,
                           updated_at, last_activity_at
                    FROM users
                    WHERE role = 'individual'
                """))
            else:
                # Columns already removed — just create minimal detail rows
                session.execute(text("""
                    INSERT INTO users_detail (user_id, full_name, email,
                                              total_points, machines_solved)
                    SELECT user_id, full_name, email, 0, 0
                    FROM users
                    WHERE role = 'individual'
                """))
            session.commit()
            migrated = session.execute(text("SELECT COUNT(*) FROM users_detail")).scalar()
            print(f"   ✅ Migrated {migrated} individual user detail rows.")
        else:
            print("   ⏭  No individual users to migrate.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 8: Remove enterprise rows from users table
        # ═══════════════════════════════════════════════════════════════
        step(8, "Remove enterprise rows from users table")
        enterprise_remaining = session.execute(text(
            "SELECT COUNT(*) FROM users WHERE role IN ('enterprise_admin', 'enterprise_staff')"
        )).scalar()
        if enterprise_remaining > 0:
            session.execute(text(
                "DELETE FROM users WHERE role IN ('enterprise_admin', 'enterprise_staff')"
            ))
            session.commit()
            print(f"   ✅ Removed {enterprise_remaining} enterprise rows from users table.")
        else:
            print("   ⏭  No enterprise rows to remove.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 9: Add account_type column to users (if not exists)
        # ═══════════════════════════════════════════════════════════════
        step(9, "Add account_type column to users")
        if column_exists('users', 'account_type'):
            print("   ⏭  Column 'account_type' already exists — skipping.")
        else:
            session.execute(text(
                "ALTER TABLE users ADD COLUMN account_type VARCHAR(32) NOT NULL DEFAULT 'individual'"
            ))
            session.commit()
            print("   ✅ Added 'account_type' column.")

        # ═══════════════════════════════════════════════════════════════
        # STEP 10: Drop migrated columns from users table
        # ═══════════════════════════════════════════════════════════════
        step(10, "Drop migrated columns from users table")
        cols_to_drop = [
            'organization_id', 'total_points', 'machines_solved',
            'campaigns_completed', 'current_streak', 'longest_streak',
            'preferences', 'updated_at', 'last_activity_at',
        ]

        # First drop FK on organization_id if it exists
        if column_exists('users', 'organization_id'):
            try:
                fk_rows = session.execute(text("""
                    SELECT CONSTRAINT_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                      AND COLUMN_NAME = 'organization_id'
                      AND REFERENCED_TABLE_NAME = 'organizations'
                """)).fetchall()
                for fk_row in fk_rows:
                    fk_name = fk_row[0]
                    session.execute(text(f"ALTER TABLE users DROP FOREIGN KEY `{fk_name}`"))
                    print(f"   Dropped FK: {fk_name}")
                session.commit()
            except Exception as e:
                print(f"   ⚠  FK drop skipped: {e}")
                session.rollback()

        for col in cols_to_drop:
            if column_exists('users', col):
                try:
                    session.execute(text(f"ALTER TABLE users DROP COLUMN `{col}`"))
                    session.commit()
                    print(f"   ✅ Dropped column: {col}")
                except Exception as e:
                    print(f"   ⚠  Could not drop '{col}': {e}")
                    session.rollback()
            else:
                print(f"   ⏭  Column '{col}' already gone — skipping.")

        # ═══════════════════════════════════════════════════════════════
        # VERIFICATION
        # ═══════════════════════════════════════════════════════════════
        step("✓", "VERIFICATION")
        final_users   = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        final_admins  = session.execute(text("SELECT COUNT(*) FROM org_admins")).scalar()
        final_staff   = session.execute(text("SELECT COUNT(*) FROM org_staff")).scalar()
        final_detail  = session.execute(text("SELECT COUNT(*) FROM users_detail")).scalar()

        print(f"\n📊 Final state:")
        print(f"   • users (individual):  {final_users}")
        print(f"   • org_admins:          {final_admins}")
        print(f"   • org_staff:           {final_staff}")
        print(f"   • users_detail:        {final_detail}")

        expected_total = individual_count
        if final_users == expected_total:
            print(f"\n   ✅ Users table correctly has {final_users} individual accounts.")
        else:
            print(f"\n   ⚠  Users table has {final_users} rows (expected {expected_total})")

        if final_admins == admin_count:
            print(f"   ✅ org_admins correctly has {final_admins} admin accounts.")
        else:
            print(f"   ⚠  org_admins has {final_admins} rows (expected {admin_count})")

        if final_staff == staff_count:
            print(f"   ✅ org_staff correctly has {final_staff} staff accounts.")
        else:
            print(f"   ⚠  org_staff has {final_staff} rows (expected {staff_count})")

        print(f"\n🎉 Migration complete!")

    except Exception as e:
        session.rollback()
        print(f"\n❌ MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
