"""Entidades de catalogo: categorias, medios de pago y contactos.

Clientes y proveedores ganan aca los datos que la version de escritorio
no tenia: documento o CUIT, telefono, correo, direccion y localidad.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MarcaDeTiempo, indices_unicos_particionados


def _columna_demo() -> Mapped[str | None]:
    """Clave de particion del sandbox, nula en los datos de la app."""
    return mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


class Categoria(MarcaDeTiempo, Base):
    """Rubro al que pertenece un producto."""

    __tablename__ = "categorias"
    __table_args__ = indices_unicos_particionados("categorias", "nombre")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_sesion_demo: Mapped[str | None] = _columna_demo()


class MedioPago(MarcaDeTiempo, Base):
    """Forma de cobro admitida: efectivo, debito, credito, QR."""

    __tablename__ = "medios_pago"
    __table_args__ = indices_unicos_particionados("medios_pago", "nombre")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Solo el efectivo pide importe recibido y calcula vuelto (RF-E08).
    es_efectivo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_sesion_demo: Mapped[str | None] = _columna_demo()


class Cliente(MarcaDeTiempo, Base):
    """Persona que compra en el comercio."""

    __tablename__ = "clientes"
    __table_args__ = indices_unicos_particionados(
        "clientes", "documento", admite_nulo=True
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    apellido: Mapped[str | None] = mapped_column(String(80), nullable=True)
    documento: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    cuit: Mapped[str | None] = mapped_column(String(15), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(180), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(90), nullable=True)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_sesion_demo: Mapped[str | None] = _columna_demo()

    @property
    def nombre_completo(self) -> str:
        """Nombre y apellido en una sola cadena."""
        return f"{self.nombre} {self.apellido or ''}".strip()


class Proveedor(MarcaDeTiempo, Base):
    """Empresa o persona que abastece al comercio."""

    __tablename__ = "proveedores"
    __table_args__ = indices_unicos_particionados(
        "proveedores", "cuit", admite_nulo=True
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    razon_social: Mapped[str] = mapped_column(
        String(160), nullable=False, index=True
    )
    cuit: Mapped[str | None] = mapped_column(
        String(15), nullable=True, index=True
    )
    contacto: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(180), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(90), nullable=True)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_sesion_demo: Mapped[str | None] = _columna_demo()
