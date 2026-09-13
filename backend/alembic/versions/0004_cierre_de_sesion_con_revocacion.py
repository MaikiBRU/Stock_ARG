"""cierre de sesion con revocacion

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-13 12:51:15.347296
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columnas() -> set[str]:
    """Columnas que la tabla de usuarios tiene ahora mismo."""
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns("usuarios")}


def upgrade() -> None:
    if "version_sesion" not in _columnas():
        op.add_column(
            "usuarios",
            sa.Column(
                "version_sesion",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    if "version_sesion" in _columnas():
        op.drop_column("usuarios", "version_sesion")
