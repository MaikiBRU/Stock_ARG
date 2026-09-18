"""ajuste de stock a cero

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-18 19:00:00.000000

Un ajuste registra el stock contado. Si el estante esta vacio, lo
contado es cero, y la regla "cantidad > 0" lo impedia: habia que
disfrazarlo de salida. El resto de los tipos sigue exigiendo una
cantidad positiva.
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "movimientos_stock"
# Nombres cortos: la convencion de nombres agrega "ck_<tabla>_".
VIEJA = "cantidad_positiva"
NUEVA = "cantidad_valida"


def upgrade() -> None:
    # Modo batch: SQLite no cambia restricciones con un ALTER simple.
    with op.batch_alter_table(TABLA) as lote:
        lote.drop_constraint(VIEJA, type_="check")
        lote.create_check_constraint(
            NUEVA, "cantidad > 0 OR (tipo = 'AJUSTE' AND cantidad = 0)"
        )


def downgrade() -> None:
    # Con ajustes a cero ya registrados la regla vieja no se puede
    # restaurar: la base la rechaza y hay que revisar esas filas a mano.
    with op.batch_alter_table(TABLA) as lote:
        lote.drop_constraint(NUEVA, type_="check")
        lote.create_check_constraint(VIEJA, "cantidad > 0")
