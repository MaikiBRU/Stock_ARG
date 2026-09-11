"""Compra a proveedor y su detalle.

Una compra confirmada genera movimientos de entrada y sube el stock
(RF-G03). Es el camino inverso de la venta.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MarcaDeTiempo


class Compra(MarcaDeTiempo, Base):
    """Cabecera de una compra a un proveedor."""

    __tablename__ = "compras"
    __table_args__ = (CheckConstraint("total >= 0", name="total_no_negativo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    registrada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    # Numero de remito o factura del proveedor, tal como viene en papel.
    comprobante: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)

    id_proveedor: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id"), nullable=False, index=True
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    items: Mapped[list["CompraItem"]] = relationship(
        back_populates="compra",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CompraItem(Base):
    """Una linea de la compra."""

    __tablename__ = "compra_items"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("costo_unitario >= 0", name="costo_no_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_compra: Mapped[int] = mapped_column(
        ForeignKey("compras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_producto: Mapped[int] = mapped_column(
        ForeignKey("productos.id"), nullable=False, index=True
    )
    nombre_producto: Mapped[str] = mapped_column(String(140), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Cuelga de la sesion ademas de su padre: asi un unico DELETE sobre
    # sesiones_demo limpia el sandbox entero, sin depender de que la
    # rutina de purga borre las tablas en el orden correcto.
    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    compra: Mapped[Compra] = relationship(back_populates="items")
