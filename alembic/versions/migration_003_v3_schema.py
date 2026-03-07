"""
Alembic migration: v2 → v3 schema changes
Safe to re-run — checks if each column/index exists before adding it.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '003_v3_schema'
down_revision = None
branch_labels = None
depends_on    = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_columns(table_name: str) -> list:
    """Return a list of existing column names for a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return [col['name'] for col in inspector.get_columns(table_name)]


def _get_indexes(table_name: str) -> list:
    """Return a list of existing index names for a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return [idx['name'] for idx in inspector.get_indexes(table_name)]


def _column_exists(table_name: str, column_name: str) -> bool:
    return column_name in _get_columns(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in _get_indexes(table_name)


# ─── Upgrade ──────────────────────────────────────────────────────────────────

def upgrade() -> None:

    # ── users: add last_activity_at ───────────────────────────────────────────
    if not _column_exists('users', 'last_activity_at'):
        op.add_column('users', sa.Column('last_activity_at', sa.DateTime(), nullable=True))
        op.execute("UPDATE users SET last_activity_at = updated_at WHERE last_activity_at IS NULL")

    if not _index_exists('users', 'idx_users_last_activity'):
        op.create_index('idx_users_last_activity', 'users', ['last_activity_at'])

    # ── campaigns: add deleted_at ─────────────────────────────────────────────
    if not _column_exists('campaigns', 'deleted_at'):
        op.add_column('campaigns', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    if not _index_exists('campaigns', 'idx_campaigns_deleted_at'):
        op.create_index('idx_campaigns_deleted_at', 'campaigns', ['deleted_at'])

    # ── campaign_machines: add flag_hash, drop flag ───────────────────────────
    if not _column_exists('campaign_machines', 'flag_hash'):
        op.add_column('campaign_machines', sa.Column('flag_hash', sa.String(64), nullable=True))
        op.execute("UPDATE campaign_machines SET flag_hash = SHA2(flag, 256) WHERE flag_hash IS NULL")
        op.alter_column('campaign_machines', 'flag_hash',
                        existing_type=sa.String(64),
                        nullable=False)

    if _column_exists('campaign_machines', 'flag'):
        op.drop_column('campaign_machines', 'flag')

    # ── generated_machines: add flag_hash, deleted_at, drop flag_content ──────
    if not _column_exists('generated_machines', 'flag_hash'):
        op.add_column('generated_machines', sa.Column('flag_hash', sa.String(64), nullable=True))
        op.execute(
            "UPDATE generated_machines SET flag_hash = SHA2(flag_content, 256) "
            "WHERE flag_content IS NOT NULL AND flag_hash IS NULL"
        )

    if not _column_exists('generated_machines', 'deleted_at'):
        op.add_column('generated_machines', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    if not _index_exists('generated_machines', 'idx_gm_deleted_at'):
        op.create_index('idx_gm_deleted_at', 'generated_machines', ['deleted_at'])

    if _column_exists('generated_machines', 'flag_content'):
        op.drop_column('generated_machines', 'flag_content')

    # ── progress: add machine_id index ────────────────────────────────────────
    if not _index_exists('progress', 'idx_progress_machine_id'):
        op.create_index('idx_progress_machine_id', 'progress', ['machine_id'])


# ─── Downgrade ────────────────────────────────────────────────────────────────

def downgrade() -> None:

    if _index_exists('progress', 'idx_progress_machine_id'):
        op.drop_index('idx_progress_machine_id', table_name='progress')

    if not _column_exists('generated_machines', 'flag_content'):
        op.add_column('generated_machines', sa.Column('flag_content', sa.Text(), nullable=True))

    if _index_exists('generated_machines', 'idx_gm_deleted_at'):
        op.drop_index('idx_gm_deleted_at', table_name='generated_machines')

    if _column_exists('generated_machines', 'deleted_at'):
        op.drop_column('generated_machines', 'deleted_at')

    if _column_exists('generated_machines', 'flag_hash'):
        op.drop_column('generated_machines', 'flag_hash')

    if not _column_exists('campaign_machines', 'flag'):
        op.add_column('campaign_machines', sa.Column('flag', sa.Text(), nullable=True))

    if _column_exists('campaign_machines', 'flag_hash'):
        op.drop_column('campaign_machines', 'flag_hash')

    if _index_exists('campaigns', 'idx_campaigns_deleted_at'):
        op.drop_index('idx_campaigns_deleted_at', table_name='campaigns')

    if _column_exists('campaigns', 'deleted_at'):
        op.drop_column('campaigns', 'deleted_at')

    if _index_exists('users', 'idx_users_last_activity'):
        op.drop_index('idx_users_last_activity', table_name='users')

    if _column_exists('users', 'last_activity_at'):
        op.drop_column('users', 'last_activity_at')