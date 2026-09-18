"""Entrada y salida de proveedores, compras y reportes."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import EstadoCompra


def _limpiar(valor: str | None) -> str | None:
    """Recorta espacios y convierte la cadena vacia en nulo."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


class ProveedorEntrada(BaseModel):
    """Alta o edicion de proveedor."""

    razon_social: str = Field(min_length=1, max_length=160)
    cuit: str | None = Field(default=None, max_length=15)
    contacto: str | None = Field(default=None, max_length=120)
    telefono: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    direccion: str | None = Field(default=None, max_length=180)
    localidad: str | None = Field(default=None, max_length=90)
    notas: str | None = Field(default=None, max_length=500)

    @field_validator("razon_social")
    @classmethod
    def _razon_limpia(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("La razon social no puede estar vacia.")
        return limpio

    @field_validator(
        "cuit", "contacto", "telefono", "direccion", "localidad", "notas"
    )
    @classmethod
    def _texto_limpio(cls, valor: str | None) -> str | None:
        return _limpiar(valor)


class ProveedorSalida(BaseModel):
    """Proveedor tal como lo devuelve la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    razon_social: str
    cuit: str | None
    contacto: str | None
    telefono: str | None
    email: str | None
    direccion: str | None
    localidad: str | None
    notas: str | None
    activo: bool


class LineaCompraEntrada(BaseModel):
    """Una linea del remito."""

    # Igual que en la venta: un subtotal enviado se ignoraria en
    # silencio, asi que se rechaza.
    model_config = ConfigDict(extra="forbid")

    id_producto: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=100_000)
    costo_unitario: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CompraEntrada(BaseModel):
    """Remito de compra. El total lo calcula el servidor."""

    model_config = ConfigDict(extra="forbid")

    items: list[LineaCompraEntrada] = Field(min_length=1, max_length=500)
    id_proveedor: int = Field(gt=0)
    fecha: date | None = None
    comprobante: str | None = Field(default=None, max_length=60)
    notas: str | None = Field(default=None, max_length=500)
    # Por defecto la compra actualiza el costo del producto: es el
    # numero que hace que el margen diga algo real.
    actualizar_costo: bool = True


class AnulacionCompraEntrada(BaseModel):
    """Motivo de la anulacion de una compra."""

    motivo: str | None = Field(default=None, max_length=255)


class CompraItemSalida(BaseModel):
    """Una linea de la compra."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_producto: int
    nombre_producto: str
    cantidad: int
    costo_unitario: Decimal
    subtotal: Decimal


class CompraSalida(BaseModel):
    """Compra completa."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    total: Decimal
    comprobante: str | None
    notas: str | None
    id_proveedor: int
    id_usuario: int
    estado: EstadoCompra
    anulada_en: datetime | None
    motivo_anulacion: str | None
    items: list[CompraItemSalida]
    # Nombre para mostrar; lo completa la ruta.
    proveedor: str | None = None


class CompraResumenSalida(BaseModel):
    """Fila del historial de compras."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    total: Decimal
    comprobante: str | None
    estado: EstadoCompra
    id_proveedor: int
    # Nombre para mostrar; lo completa la ruta.
    proveedor: str | None = None


class ResumenProveedorSalida(BaseModel):
    """Cuanto se le compro a un proveedor (RF-G04)."""

    cantidad_compras: int
    total_comprado: Decimal
    ultima_compra: date | None


# --- reportes (modulo H) -------------------------------------------------


class VentasPeriodoSalida(BaseModel):
    """Resumen de ventas del periodo (RF-H01)."""

    desde: date
    hasta: date
    cantidad_ventas: int
    total_facturado: Decimal
    ticket_promedio: Decimal
    sin_datos: bool


class PuntoSerieSalida(BaseModel):
    """Un dia de la serie de ventas."""

    fecha: date
    cantidad_ventas: int
    total: Decimal


class FilaRankingSalida(BaseModel):
    """Un producto del ranking (RF-H02)."""

    id_producto: int
    nombre: str
    unidades: int
    facturado: Decimal


class RankingSalida(BaseModel):
    """Ranking de productos mas vendidos."""

    desde: date
    hasta: date
    ordenado_por: str
    ranking: list[FilaRankingSalida]
    sin_datos: bool


class FilaMedioPagoSalida(BaseModel):
    """Un medio de cobro del corte (RF-H03)."""

    id_medio_pago: int
    nombre: str
    cantidad_ventas: int
    total: Decimal


class FilaCategoriaSalida(BaseModel):
    """Un rubro del corte (RF-H03)."""

    id_categoria: int | None
    nombre: str
    unidades: int
    total: Decimal


class CorteMedioPagoSalida(BaseModel):
    """Ventas por forma de cobro."""

    desde: date
    hasta: date
    detalle: list[FilaMedioPagoSalida]
    sin_datos: bool


class CorteCategoriaSalida(BaseModel):
    """Ventas por rubro."""

    desde: date
    hasta: date
    detalle: list[FilaCategoriaSalida]
    sin_datos: bool


class FilaRentabilidadSalida(BaseModel):
    """Ganancia de un producto (RF-H06)."""

    id_producto: int
    nombre: str
    unidades: int
    ingreso: Decimal
    costo: Decimal
    ganancia: Decimal
    margen_porcentaje: Decimal | None


class RentabilidadSalida(BaseModel):
    """Reporte de rentabilidad. Solo para el propietario."""

    desde: date
    hasta: date
    detalle: list[FilaRentabilidadSalida]
    total_ingreso: Decimal
    total_costo: Decimal
    ganancia: Decimal
    sin_datos: bool
    advertencia: str


class ComprasPeriodoSalida(BaseModel):
    """Cuanto se gasto en mercaderia."""

    desde: date
    hasta: date
    cantidad_compras: int
    total_gastado: Decimal
    sin_datos: bool


class FechaUltimaSalida(BaseModel):
    """Marca de tiempo devuelta por algunos resumenes."""

    ultima: datetime | None
