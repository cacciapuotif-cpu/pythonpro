"""Wave 2.1: snapshot persistente e audit sblocco timesheet.

Revision ID: 056
Revises: 055
"""

from alembic import op
import sqlalchemy as sa


revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("timesheet_generati", sa.Column("generato_da_user_id", sa.Integer(), nullable=True))
    op.add_column("timesheet_generati", sa.Column("sbloccato_da_user_id", sa.Integer(), nullable=True))
    op.add_column("timesheet_generati", sa.Column("sblocco_motivo", sa.Text(), nullable=True))
    op.add_column(
        "timesheet_generati",
        sa.Column("totale_ore", sa.Numeric(8, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "timesheet_generati",
        sa.Column("presenze_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_timesheet_generati_generato_da_user",
        "timesheet_generati",
        "users",
        ["generato_da_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_timesheet_generati_sbloccato_da_user",
        "timesheet_generati",
        "users",
        ["sbloccato_da_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "timesheet_righe",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timesheet_id", sa.Integer(), nullable=False),
        sa.Column("attendance_id", sa.Integer(), nullable=True),
        sa.Column("data", sa.DateTime(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["attendance_id"], ["attendances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["timesheet_id"], ["timesheet_generati.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timesheet_righe_id", "timesheet_righe", ["id"])
    op.create_index("ix_timesheet_righe_timesheet_id", "timesheet_righe", ["timesheet_id"])
    op.create_index("ix_timesheet_righe_attendance_id", "timesheet_righe", ["attendance_id"])

    # I PDF storici non contengono dati strutturati interrogabili. Al momento
    # dell'upgrade congeliamo quindi, per ogni versione legacy, le presenze
    # correnti dell'assignment: da questo punto in avanti update/delete sono
    # protetti e un PDF mancante può essere ricostruito senza leggere dati live.
    op.execute(
        """
        INSERT INTO timesheet_righe (
            timesheet_id, attendance_id, data, start_time, end_time, hours, notes
        )
        SELECT
            tg.id, a.id, a.date, a.start_time, a.end_time, a.hours, a.notes
        FROM timesheet_generati AS tg
        JOIN attendances AS a ON a.assignment_id = tg.assignment_id
        """
    )
    op.execute(
        """
        UPDATE timesheet_generati AS tg
        SET
            totale_ore = snapshot.totale_ore,
            presenze_count = snapshot.presenze_count
        FROM (
            SELECT
                timesheet_id,
                COALESCE(SUM(hours), 0) AS totale_ore,
                COUNT(*) AS presenze_count
            FROM timesheet_righe
            GROUP BY timesheet_id
        ) AS snapshot
        WHERE snapshot.timesheet_id = tg.id
        """
    )


def downgrade():
    op.drop_index("ix_timesheet_righe_attendance_id", table_name="timesheet_righe")
    op.drop_index("ix_timesheet_righe_timesheet_id", table_name="timesheet_righe")
    op.drop_index("ix_timesheet_righe_id", table_name="timesheet_righe")
    op.drop_table("timesheet_righe")
    op.drop_constraint("fk_timesheet_generati_sbloccato_da_user", "timesheet_generati", type_="foreignkey")
    op.drop_constraint("fk_timesheet_generati_generato_da_user", "timesheet_generati", type_="foreignkey")
    op.drop_column("timesheet_generati", "presenze_count")
    op.drop_column("timesheet_generati", "totale_ore")
    op.drop_column("timesheet_generati", "sblocco_motivo")
    op.drop_column("timesheet_generati", "sbloccato_da_user_id")
    op.drop_column("timesheet_generati", "generato_da_user_id")
