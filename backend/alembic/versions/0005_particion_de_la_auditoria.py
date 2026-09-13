"""particion de la auditoria

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-13 18:00:00.000000

La tabla de auditoria era la unica sin id_sesion_demo. Las lineas que
ya existen pertenecen a la aplicacion y quedan con NULL: ninguna fila
cambia de particion.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "auditoria"
COLUMNA = "id_sesion_demo"
INDICE = "ix_auditoria_id_sesion_demo"
CLAVE_FORANEA = "fk_auditoria_id_sesion_demo_sesiones_demo"


def _columnas() -> set[str]:
    """Columnas que la tabla de auditoria tiene ahora mismo."""
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(TABLA)}


def upgrade() -> None:
    if COLUMNA in _columnas():
        return
    # Modo batch: SQLite no agrega claves foraneas con ALTER TABLE.
    with op.batch_alter_table(TABLA) as lote:
        lote.add_column(sa.Column(COLUMNA, sa.String(64), nullable=True))
        lote.create_index(INDICE, [COLUMNA])
        lote.create_foreign_key(
            CLAVE_FORANEA,
            "sesiones_demo",
            [COLUMNA],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    if COLUMNA not in _columnas():
        return
    with op.batch_alter_table(TABLA) as lote:
        lote.drop_constraint(CLAVE_FORANEA, type_="foreignkey")
        lote.drop_index(INDICE)
        lote.drop_column(COLUMNA)
