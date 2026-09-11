"""Venta y su detalle.

Aca esta la diferencia estructural con la version de escritorio: alla la
tabla de ventas es plana y una venta equivale a un producto. Una venta
real lleva varios articulos, un total y un medio de pago, asi que se
separa en cabecera y detalle.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MarcaDeTiempo, sin_nulo


class EstadoVenta(StrEnum):
    """Situacion de una venta."""

    REGISTRADA = "registrada"
    ANULADA = "anulada"


class Venta(MarcaDeTiempo, Base):
    """Cabecera de una operacion de venta."""

    __tablename__ = "ventas"
    __table_args__ = (
        CheckConstraint("total >= 0", name="total_no_negativo"),
        CheckConstraint("descuento >= 0", name="descuento_no_negativo"),
        # El vuelto se deriva de recibido menos total. Sin esta
        # regla, una venta podria guardarse con menos dinero del
        # que costo y el vuelto saldria negativo.
        CheckConstraint(
            "recibido IS NULL OR recibido >= total",
            name="recibido_cubre_el_total",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    # Importe entregado por el cliente, solo con pago en efectivo. El
    # vuelto se deriva de este valor y del total (RF-E08).
    recibido: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False, index=True
    )
    id_medio_pago: Mapped[int] = mapped_column(
        ForeignKey("medios_pago.id"), nullable=False, index=True
    )
    # El cliente es opcional: en un kiosco la mayoria de las ventas son
    # a mostrador y nadie se identifica.
    id_cliente: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id"), nullable=True, index=True
    )

    estado: Mapped[EstadoVenta] = mapped_column(
        Enum(EstadoVenta, native_enum=False, length=20),
        nullable=False,
        default=EstadoVenta.REGISTRADA,
        index=True,
    )
    anulada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    id_usuario_anulacion: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    motivo_anulacion: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    items: Mapped[list["VentaItem"]] = relationship(
        back_populates="venta",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def vuelto(self) -> Decimal | None:
        """Diferencia entre lo recibido y el total."""
        if self.recibido is None:
            return None
        return self.recibido - sin_nulo(self.total, Decimal("0.00"))

    @property
    def cantidad_articulos(self) -> int:
        """Unidades totales incluidas en la venta."""
        return sum(item.cantidad for item in self.items)


class VentaItem(Base):
    """Una linea de la venta: producto, cantidad y precio."""

    __tablename__ = "venta_items"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint(
            "precio_unitario >= 0", name="precio_unitario_no_negativo"
        ),
        CheckConstraint("subtotal >= 0", name="subtotal_no_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_venta: Mapped[int] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_producto: Mapped[int] = mapped_column(
        ForeignKey("productos.id"), nullable=False, index=True
    )

    # El nombre se copia al registrar: si el producto se renombra o se
    # da de baja, el ticket sigue diciendo lo que se vendio ese dia.
    nombre_producto: Mapped[str] = mapped_column(String(140), nullable=False)

    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
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

    venta: Mapped[Venta] = relationship(back_populates="items")
