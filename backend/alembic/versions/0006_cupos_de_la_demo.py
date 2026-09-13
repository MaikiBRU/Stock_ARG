"""cupos de la demo

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-13 19:00:00.000000

Contadores de importaciones y exportaciones por sandbox (RF-J06). Las
sesiones que ya existen arrancan en cero.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "sesiones_demo"
COLUMNAS = ("importaciones", "exportaciones")


def _columnas() -> set[str]:
    """Columnas que la tabla de sesiones tiene ahora mismo."""
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(TABLA)}


def upgrade() -> None:
    existentes = _columnas()
    for columna in COLUMNAS:
        if columna not in existentes:
            op.add_column(
                TABLA,
                sa.Column(
                    columna, sa.Integer(), nullable=False, server_default="0"
                ),
            )


def downgrade() -> None:
    existentes = _columnas()
    for columna in reversed(COLUMNAS):
        if columna in existentes:
            op.drop_column(TABLA, columna)
