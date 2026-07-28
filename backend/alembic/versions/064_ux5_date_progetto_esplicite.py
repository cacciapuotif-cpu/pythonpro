"""UX-5 — separa date amministrative, formative e di chiusura.

Migration volutamente additiva: le colonne legacy dell'intervallo restano
inalterate e nessun valore viene copiato nei nuovi campi. La qualificazione dei
dati legacy richiede verifica umana dell'atto.

Revision ID: 064
Revises: 063
"""

from alembic import op
import sqlalchemy as sa


revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None


NUOVE_COLONNE = (
    "data_avvio_piano",
    "data_termine_piano",
    "data_avvio_attivita_formative",
    "data_fine_attivita_formative",
    "data_termine_rendicontazione",
    "data_chiusura_effettiva",
)


def upgrade() -> None:
    for name in NUOVE_COLONNE:
        op.add_column("projects", sa.Column(name, sa.Date(), nullable=True))

    for name in (
        "data_avvio_piano",
        "data_termine_piano",
        "data_termine_rendicontazione",
    ):
        op.create_index(f"ix_projects_{name}", "projects", [name], unique=False)

    checks = (
        (
            "ck_project_approvazione_avvio_piano",
            "data_approvazione IS NULL OR data_avvio_piano IS NULL "
            "OR data_approvazione <= data_avvio_piano",
        ),
        (
            "ck_project_avvio_termine_piano",
            "data_avvio_piano IS NULL OR data_termine_piano IS NULL "
            "OR data_avvio_piano <= data_termine_piano",
        ),
        (
            "ck_project_attivita_formative_range",
            "data_avvio_attivita_formative IS NULL OR data_fine_attivita_formative IS NULL "
            "OR data_avvio_attivita_formative <= data_fine_attivita_formative",
        ),
        (
            "ck_project_attivita_dopo_avvio_piano",
            "data_avvio_piano IS NULL OR data_avvio_attivita_formative IS NULL "
            "OR data_avvio_piano <= data_avvio_attivita_formative",
        ),
        (
            "ck_project_attivita_entro_termine_piano",
            "data_termine_piano IS NULL OR data_fine_attivita_formative IS NULL "
            "OR data_fine_attivita_formative <= data_termine_piano",
        ),
        (
            "ck_project_rendicontazione_dopo_attivita",
            "data_fine_attivita_formative IS NULL OR data_termine_rendicontazione IS NULL "
            "OR data_fine_attivita_formative <= data_termine_rendicontazione",
        ),
        (
            "ck_project_chiusura_dopo_attivita",
            "data_fine_attivita_formative IS NULL OR data_chiusura_effettiva IS NULL "
            "OR data_fine_attivita_formative <= data_chiusura_effettiva",
        ),
    )
    for name, condition in checks:
        op.create_check_constraint(name, "projects", condition)


def downgrade() -> None:
    for name in (
        "ck_project_chiusura_dopo_attivita",
        "ck_project_rendicontazione_dopo_attivita",
        "ck_project_attivita_entro_termine_piano",
        "ck_project_attivita_dopo_avvio_piano",
        "ck_project_attivita_formative_range",
        "ck_project_avvio_termine_piano",
        "ck_project_approvazione_avvio_piano",
    ):
        op.drop_constraint(name, "projects", type_="check")

    for name in (
        "data_termine_rendicontazione",
        "data_termine_piano",
        "data_avvio_piano",
    ):
        op.drop_index(f"ix_projects_{name}", table_name="projects")

    for name in reversed(NUOVE_COLONNE):
        op.drop_column("projects", name)
