"""Base declarativa y piezas compartidas por todos los modelos."""

from datetime import datetime

from sqlalchemy import DateTime, Index, MetaData, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres de constraint predecibles: sin esto, Alembic genera
# migraciones que no pueden eliminar un indice por nombre.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""

    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class MarcaDeTiempo:
    """Agrega la fecha de creacion y la de ultima modificacion."""

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    actualizado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


def indices_unicos_particionados(
    tabla: str, columna: str, admite_nulo: bool = False
) -> tuple[Index, Index]:
    """Unicidad de una columna dentro de su particion de datos.

    Un UNIQUE comun no sirve cuando la misma tabla guarda los datos de
    la aplicacion y los de cada sandbox de la demo: dos visitantes no
    podrian recibir el mismo catalogo sembrado. Y un UNIQUE compuesto
    con la sesion tampoco, porque en SQL dos NULL no son iguales entre
    si, de modo que la aplicacion real admitiria duplicados.

    La solucion son dos indices parciales: uno sobre las filas de la
    aplicacion y otro por sesion de demo.

    Args:
        tabla: nombre de la tabla, para nombrar los indices.
        columna: columna que debe ser unica.
        admite_nulo: si la columna es opcional, los nulos se excluyen
            para que varias filas puedan quedar sin el dato.
    """
    condicion_app = f"{columna} IS NOT NULL" if admite_nulo else None
    condicion_demo = "id_sesion_demo IS NOT NULL"
    if admite_nulo:
        condicion_demo = f"{condicion_demo} AND {columna} IS NOT NULL"

    filtro_app = "id_sesion_demo IS NULL"
    if condicion_app:
        filtro_app = f"{filtro_app} AND {condicion_app}"

    return (
        Index(
            f"uq_{tabla}_{columna}_app",
            columna,
            unique=True,
            postgresql_where=text(filtro_app),
            sqlite_where=text(filtro_app),
        ),
        Index(
            f"uq_{tabla}_{columna}_demo",
            columna,
            "id_sesion_demo",
            unique=True,
            postgresql_where=text(condicion_demo),
            sqlite_where=text(condicion_demo),
        ),
    )


def sin_nulo[T](valor: T | None, reemplazo: T) -> T:
    """Devuelve el valor, o el reemplazo si todavia es nulo.

    Los valores por defecto de una columna los aplica la base en el
    INSERT, no el constructor de Python: un objeto recien construido
    tiene None en toda columna que no se haya pasado a mano. Las
    propiedades calculadas se leen antes de guardar -- por ejemplo al
    previsualizar una importacion CSV, que muestra el resultado sin
    escribir nada -- asi que tienen que tolerar ese estado.
    """
    return reemplazo if valor is None else valor
