"""Producto y su estado de stock."""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    object_session,
    relationship,
)

from app.core import ajustes_vivos
from app.db.base import (
    Base,
    MarcaDeTiempo,
    indices_unicos_particionados,
    sin_nulo,
)
from app.models.catalogo import Categoria, Proveedor


class Producto(MarcaDeTiempo, Base):
    """Articulo del inventario.

    La clave primaria es interna. El codigo de barras es lo que ve y
    teclea el usuario, es opcional, y es unico solo cuando esta
    informado: varios productos sin codigo conviven sin colisionar.
    """

    __tablename__ = "productos"
    __table_args__ = (
        CheckConstraint("precio_venta >= 0", name="precio_venta_no_negativo"),
        CheckConstraint("precio_costo >= 0", name="precio_costo_no_negativo"),
        CheckConstraint("stock_actual >= 0", name="stock_no_negativo"),
        CheckConstraint("stock_minimo >= 0", name="stock_minimo_no_negativo"),
        CheckConstraint("stock_inicial >= 0", name="stock_inicial_no_negativo"),
        # RF-C02: unico cuando esta informado, para que varios
        # productos sin codigo convivan sin colisionar.
        *indices_unicos_particionados(
            "productos", "codigo_barra", admite_nulo=True
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_barra: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)

    precio_venta: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    # Alimenta el reporte de rentabilidad (RF-H06), que solo ve el
    # propietario.
    precio_costo: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    stock_actual: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    stock_minimo: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Referencia contra la que se calcula el porcentaje del panel de
    # stock, tal como lo hace la version de escritorio.
    stock_inicial: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    fecha_vencimiento: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True
    )

    id_categoria: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    id_proveedor: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True
    )

    # Baja logica (RF-C09): un producto con historial nunca se borra.
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    categoria: Mapped[Categoria | None] = relationship(lazy="joined")
    proveedor: Mapped[Proveedor | None] = relationship(lazy="joined")

    @property
    def porcentaje_stock(self) -> int:
        """Stock actual como porcentaje del inicial, acotado a 100.

        Sin stock inicial de referencia no hay porcentaje que calcular:
        se informa 100 para que el producto no aparezca en rojo solo por
        no tener el dato cargado.
        """
        actual = sin_nulo(self.stock_actual, 0)
        inicial = sin_nulo(self.stock_inicial, 0)
        if inicial <= 0:
            return 100 if actual > 0 else 0
        return min(100, round(actual * 100 / inicial))

    @property
    def estado_stock(self) -> str:
        """Nivel de stock: "bajo", "medio" u "ok" (RF-D01)."""
        porcentaje = self.porcentaje_stock
        sesion = object_session(self)
        if porcentaje <= ajustes_vivos.entero("stock_umbral_bajo", sesion):
            return "bajo"
        if porcentaje <= ajustes_vivos.entero("stock_umbral_medio", sesion):
            return "medio"
        return "ok"

    @property
    def bajo_minimo(self) -> bool:
        """True cuando conviene reponer (RF-B03)."""
        return sin_nulo(self.stock_actual, 0) <= sin_nulo(self.stock_minimo, 0)

    @property
    def margen(self) -> Decimal | None:
        """Margen sobre el costo, en porcentaje."""
        costo = sin_nulo(self.precio_costo, Decimal("0.00"))
        if costo <= 0:
            return None
        venta = sin_nulo(self.precio_venta, Decimal("0.00"))
        return ((venta - costo) / costo * 100).quantize(Decimal("0.01"))
