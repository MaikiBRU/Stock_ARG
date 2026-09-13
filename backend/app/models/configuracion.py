"""Configuracion del comercio (RF-I06).

Clave y valor en lugar de una columna por opcion: agregar un parametro
no obliga a migrar el esquema, y la particion de la demo funciona igual
que en el resto del sistema.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MarcaDeTiempo, indices_unicos_particionados


class Configuracion(MarcaDeTiempo, Base):
    """Un parametro configurable del comercio."""

    __tablename__ = "configuracion"
    __table_args__ = indices_unicos_particionados("configuracion", "clave")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    valor: Mapped[str] = mapped_column(String(255), nullable=False)
    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
