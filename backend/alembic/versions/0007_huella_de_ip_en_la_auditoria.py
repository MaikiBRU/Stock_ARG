"""huella de ip en la auditoria

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17 10:00:00.000000

La auditoria guardaba la direccion en claro, tambien la de los
visitantes anonimos de la demo. Pasa a guardar su huella, como las
sesiones de demo. Lo que ya estaba escrito no se puede convertir: el
hash lleva la clave de la aplicacion, asi que se vacia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "auditoria"


def _columnas() -> set[str]:
    """Columnas que la tabla de auditoria tiene ahora mismo."""
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(TABLA)}


def upgrade() -> None:
    if "ip_hash" in _columnas():
        return
    # Modo batch: SQLite no renombra columnas con un ALTER simple.
    with op.batch_alter_table(TABLA) as lote:
        lote.alter_column(
            "ip",
            new_column_name="ip_hash",
            existing_type=sa.String(64),
            existing_nullable=True,
        )
    op.execute(f"UPDATE {TABLA} SET ip_hash = NULL")


def downgrade() -> None:
    if "ip" in _columnas():
        return
    with op.batch_alter_table(TABLA) as lote:
        lote.alter_column(
            "ip_hash",
            new_column_name="ip",
            existing_type=sa.String(64),
            existing_nullable=True,
        )
