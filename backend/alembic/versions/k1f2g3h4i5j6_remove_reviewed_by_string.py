"""remove reviewed_by string from agent review actions

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-04-07 14:45:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _fk_names(inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = _column_names(inspector, "agent_review_actions")
    indexes = _index_names(inspector, "agent_review_actions")
    foreign_keys = _fk_names(inspector, "agent_review_actions")

    if "reviewed_by" in columns and "reviewed_by_user_id" in columns:
        op.execute(
            """
            UPDATE agent_review_actions ara
            SET reviewed_by_user_id = u.id
            FROM users u
            WHERE ara.reviewed_by_user_id IS NULL
              AND ara.reviewed_by IS NOT NULL
              AND (
                    lower(u.username) = lower(ara.reviewed_by)
                 OR lower(u.email) = lower(ara.reviewed_by)
              )
            """
        )

    if "reviewed_by_user_id" in columns and "fk_agent_review_actions_reviewed_by_user_id_users" not in foreign_keys:
        op.create_foreign_key(
            "fk_agent_review_actions_reviewed_by_user_id_users",
            "agent_review_actions",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "ix_agent_review_actions_reviewed_by" in indexes:
        op.drop_index("ix_agent_review_actions_reviewed_by", table_name="agent_review_actions")

    if "reviewed_by" in columns:
        op.drop_column("agent_review_actions", "reviewed_by")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = _column_names(inspector, "agent_review_actions")
    indexes = _index_names(inspector, "agent_review_actions")
    foreign_keys = _fk_names(inspector, "agent_review_actions")

    if "reviewed_by" not in columns:
        op.add_column("agent_review_actions", sa.Column("reviewed_by", sa.String(length=100), nullable=True))

    op.execute(
        """
        UPDATE agent_review_actions ara
        SET reviewed_by = COALESCE(ara.reviewed_by, u.username, u.email)
        FROM users u
        WHERE ara.reviewed_by_user_id = u.id
          AND ara.reviewed_by IS NULL
        """
    )

    if "ix_agent_review_actions_reviewed_by" not in indexes:
        op.create_index("ix_agent_review_actions_reviewed_by", "agent_review_actions", ["reviewed_by"], unique=False)

    if "fk_agent_review_actions_reviewed_by_user_id_users" in foreign_keys:
        op.drop_constraint("fk_agent_review_actions_reviewed_by_user_id_users", "agent_review_actions", type_="foreignkey")
