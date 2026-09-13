"""anulacion de compras y configuracion del comercio

Revision ID: 0003
Revises: 0002

Se escribe a mano y no se deja la version autogenerada por dos motivos
(RNF-09):

1. "estado" es NOT NULL. Sin un valor por defecto del lado del servidor,
   agregarlo sobre una tabla de compras que ya tiene filas falla: las
   existentes no tendrian valor. Se crea con default, se usa para las
   filas viejas, y queda como default tambien para las nuevas.
2. SQLite no admite agregar una clave foranea a una tabla existente. El
   modo por lotes de Alembic recrea la tabla y funciona igual en
   PostgreSQL, que es donde corre en produccion.

Cada paso consulta el catalogo antes de actuar, asi que volver a
aplicarla no rompe nada.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADO_COMPRA = sa.Enum(
    "REGISTRADA", "ANULADA", name="estadocompra", native_enum=False, length=20
)


def _columnas(tabla: str) -> set[str]:
    """Columnas que la tabla tiene ahora mismo."""
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(tabla)}


def _tablas() -> set[str]:
    """Tablas existentes en la base."""
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indices(tabla: str) -> set[str]:
    """Indices existentes de una tabla."""
    inspector = sa.inspect(op.get_bind())
    return {i["name"] for i in inspector.get_indexes(tabla)}


def upgrade() -> None:
    if "configuracion" not in _tablas():
        op.create_table(
            "configuracion",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("clave", sa.String(length=60), nullable=False),
            sa.Column("valor", sa.String(length=255), nullable=False),
            sa.Column(
                "id_sesion_demo", sa.String(length=64), nullable=True
            ),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "actualizado_en", sa.DateTime(timezone=True), nullable=True
            ),
            sa.ForeignKeyConstraint(
                ["id_sesion_demo"],
                ["sesiones_demo.id"],
                name=op.f("fk_configuracion_id_sesion_demo_sesiones_demo"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_configuracion")),
        )
        op.create_index(
            op.f("ix_configuracion_clave"),
            "configuracion",
            ["clave"],
            unique=False,
        )
        op.create_index(
            op.f("ix_configuracion_id_sesion_demo"),
            "configuracion",
            ["id_sesion_demo"],
            unique=False,
        )
        op.create_index(
            "uq_configuracion_clave_app",
            "configuracion",
            ["clave"],
            unique=True,
            postgresql_where=sa.text("id_sesion_demo IS NULL"),
            sqlite_where=sa.text("id_sesion_demo IS NULL"),
        )
        op.create_index(
            "uq_configuracion_clave_demo",
            "configuracion",
            ["clave", "id_sesion_demo"],
            unique=True,
            postgresql_where=sa.text("id_sesion_demo IS NOT NULL"),
            sqlite_where=sa.text("id_sesion_demo IS NOT NULL"),
        )

    existentes = _columnas("compras")

    if "estado" not in existentes:
        # El default del servidor completa las compras ya cargadas, que
        # por definicion estan registradas y no anuladas.
        op.add_column(
            "compras",
            sa.Column(
                "estado",
                ESTADO_COMPRA,
                nullable=False,
                server_default="REGISTRADA",
            ),
        )
    if "anulada_en" not in existentes:
        op.add_column(
            "compras",
            sa.Column("anulada_en", sa.DateTime(timezone=True), nullable=True),
        )
    if "motivo_anulacion" not in existentes:
        op.add_column(
            "compras",
            sa.Column(
                "motivo_anulacion", sa.String(length=255), nullable=True
            ),
        )

    if "ix_compras_estado" not in _indices("compras"):
        op.create_index(
            op.f("ix_compras_estado"), "compras", ["estado"], unique=False
        )

    if "id_usuario_anulacion" not in _columnas("compras"):
        # La columna y su clave foranea se agregan juntas en modo por
        # lotes: SQLite no sabe alterar constraints, y este modo recrea
        # la tabla. En PostgreSQL se traduce a un ALTER normal.
        with op.batch_alter_table("compras") as lote:
            lote.add_column(
                sa.Column("id_usuario_anulacion", sa.Integer(), nullable=True)
            )
            lote.create_foreign_key(
                op.f("fk_compras_id_usuario_anulacion_usuarios"),
                "usuarios",
                ["id_usuario_anulacion"],
                ["id"],
            )


def downgrade() -> None:
    if "id_usuario_anulacion" in _columnas("compras"):
        with op.batch_alter_table("compras") as lote:
            lote.drop_constraint(
                op.f("fk_compras_id_usuario_anulacion_usuarios"),
                type_="foreignkey",
            )
            lote.drop_column("id_usuario_anulacion")

    if "ix_compras_estado" in _indices("compras"):
        op.drop_index(op.f("ix_compras_estado"), table_name="compras")

    existentes = _columnas("compras")
    for columna in ("motivo_anulacion", "anulada_en", "estado"):
        if columna in existentes:
            op.drop_column("compras", columna)

    if "configuracion" in _tablas():
        op.drop_table("configuracion")
