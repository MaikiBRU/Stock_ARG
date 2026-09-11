"""Trazabilidad del inventario: movimientos y bajas."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TipoMovimiento(StrEnum):
    """Origen de un cambio de stock."""

    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"
    VENTA = "venta"
    BAJA = "baja"
    DEVOLUCION = "devolucion"


class MotivoBaja(StrEnum):
    """Razon por la que se descarta mercaderia."""

    VENCIDO = "vencido"
    DANADO = "danado"
    OTRO = "otro"


class MovimientoStock(Base):
    """Registro inmutable de un cambio de stock.

    Guarda el stock resultante ademas de la cantidad, de modo que el
    historial se lee sin recalcular la serie entera (RF-D05).
    """

    __tablename__ = "movimientos_stock"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint(
            "stock_resultante >= 0", name="stock_resultante_no_negativo"
        ),
        Index("ix_movimientos_producto_fecha", "id_producto", "fecha_hora"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_producto: Mapped[int] = mapped_column(
        ForeignKey("productos.id"), nullable=False
    )
    tipo: Mapped[TipoMovimiento] = mapped_column(
        Enum(TipoMovimiento, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_resultante: Mapped[int] = mapped_column(Integer, nullable=False)
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Referencia a la venta o compra que lo origino, cuando la hay.
    id_venta: Mapped[int | None] = mapped_column(
        ForeignKey("ventas.id", ondelete="SET NULL"), nullable=True
    )
    id_compra: Mapped[int | None] = mapped_column(
        ForeignKey("compras.id", ondelete="SET NULL"), nullable=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    # Cuelga de la sesion ademas de su padre: asi un unico DELETE sobre
    # sesiones_demo limpia el sandbox entero, sin depender de que la
    # rutina de purga borre las tablas en el orden correcto.
    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


class BajaProducto(Base):
    """Mercaderia descartada por vencimiento, dano u otro motivo."""

    __tablename__ = "bajas_producto"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_producto: Mapped[int] = mapped_column(
        ForeignKey("productos.id"), nullable=False, index=True
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[MotivoBaja] = mapped_column(
        Enum(MotivoBaja, native_enum=False, length=20), nullable=False
    )
    detalle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    # Cuelga de la sesion ademas de su padre: asi un unico DELETE sobre
    # sesiones_demo limpia el sandbox entero, sin depender de que la
    # rutina de purga borre las tablas en el orden correcto.
    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
