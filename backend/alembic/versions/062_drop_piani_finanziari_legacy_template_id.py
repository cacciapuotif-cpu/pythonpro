"""NEW-029 — migra e droppa ``piani_finanziari.legacy_template_id``.

``legacy_template_id`` e' una colonna relitto (non e' una FK dichiarata, non
piu' referenziata da crud dopo E1.2). Sul DB reale sopravvive un solo valore
non-null (piano id=4 -> 14) e nemmeno lo si ritiene semanticamente valido: e'
un riferimento pendente.

Decisione utente (2026-07-22): "droppa migrando" — prima si PRESERVA il dato in
modo durevole e non distruttivo, poi si droppa la colonna.

Stadio "migrando" (preserva)
----------------------------
Per ogni piano con ``legacy_template_id`` non-null si scrive UNA riga in
``audit_logs`` (modello ``AuditLog``, audit di dominio append-only):

    entity    = 'PianoFinanziario'
    action    = 'legacy_template_id_dropped'
    old_value = '{"piano_id": <id>, "legacy_template_id": <valore>}'

``audit_logs`` e' il target piu' pulito: e' pensato per le variazioni di dominio
(entity/action/old_value), quindi il relitto viene conservato per completezza di
audit senza inquinare campi utente (``note``/``note_ente``). L'immutabilita' del
modello e' imposta solo a livello ORM (event listener SQLAlchemy): un INSERT SQL
diretto da migration e' lecito e non toccato da quei guard.

Stadio drop
-----------
``DROP COLUMN legacy_template_id``.

Downgrade
---------
Ricrea la colonna VUOTA (``Integer`` nullable). Il ripristino del valore non e'
richiesto: resta preservato in ``audit_logs``.

Revision ID: 062
Revises: 061
"""
from alembic import op
import sqlalchemy as sa


revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column("piani_finanziari", "legacy_template_id"):
        # Idempotenza: gia' droppata (o schema creato da metadata senza colonna).
        return

    # Stadio "migrando": preserva i valori residui in audit_logs PRIMA del drop.
    if "audit_logs" in sa.inspect(bind).get_table_names():
        rows = bind.execute(
            sa.text(
                "SELECT id, legacy_template_id FROM piani_finanziari "
                "WHERE legacy_template_id IS NOT NULL"
            )
        ).fetchall()
        for piano_id, legacy_value in rows:
            old_value = (
                '{{"piano_id": {pid}, "legacy_template_id": {val}}}'.format(
                    pid=int(piano_id), val=int(legacy_value)
                )
            )
            bind.execute(
                sa.text(
                    "INSERT INTO audit_logs "
                    "(entity, action, old_value, new_value, user_id, created_at) "
                    "VALUES (:entity, :action, :old_value, NULL, NULL, "
                    + _now_expr(bind)
                    + ")"
                ),
                {
                    "entity": "PianoFinanziario",
                    "action": "legacy_template_id_dropped",
                    "old_value": old_value,
                },
            )

    op.drop_column("piani_finanziari", "legacy_template_id")


def downgrade() -> None:
    # Ricrea la colonna VUOTA. Il valore originale resta in audit_logs.
    if not _has_column("piani_finanziari", "legacy_template_id"):
        op.add_column(
            "piani_finanziari",
            sa.Column("legacy_template_id", sa.Integer(), nullable=True),
        )


def _now_expr(bind) -> str:
    return "now()" if bind.dialect.name == "postgresql" else "CURRENT_TIMESTAMP"
