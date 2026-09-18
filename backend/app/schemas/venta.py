"""Entrada y salida del punto de venta y de clientes."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import EstadoVenta

MAX_LINEAS = 200


def _limpiar(valor: str | None) -> str | None:
    """Recorta espacios y convierte la cadena vacia en nulo."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


class LineaEntrada(BaseModel):
    """Una linea del pedido de venta."""

    # Prohibir campos extra tambien aca: un "subtotal" enviado se
    # ignoraria en silencio y quien lo mando creeria que se respeto.
    model_config = ConfigDict(extra="forbid")

    id_producto: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=100_000)
    # Opcional: sin precio se usa el de lista del producto.
    precio_unitario: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    descuento: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2
    )


class VentaEntrada(BaseModel):
    """Pedido de venta.

    No admite un campo "total": el total lo calcula el servidor a partir
    de las lineas. Prohibir los campos extra hace que enviarlo devuelva
    un error visible, en lugar de descartarse sin aviso y dejar a quien
    integra creyendo que su importe se respeto.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[LineaEntrada] = Field(min_length=1, max_length=MAX_LINEAS)
    id_medio_pago: int = Field(gt=0)
    id_cliente: int | None = None
    recibido: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    descuento: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2
    )


class AnulacionEntrada(BaseModel):
    """Motivo de una anulacion."""

    motivo: str | None = Field(default=None, max_length=255)


class VentaItemSalida(BaseModel):
    """Una linea del ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_producto: int
    nombre_producto: str
    cantidad: int
    precio_unitario: Decimal
    descuento: Decimal
    subtotal: Decimal


class VentaSalida(BaseModel):
    """Ticket completo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_hora: datetime
    total: Decimal
    descuento: Decimal
    recibido: Decimal | None
    vuelto: Decimal | None
    cantidad_articulos: int
    estado: EstadoVenta
    id_usuario: int
    id_medio_pago: int
    id_cliente: int | None
    anulada_en: datetime | None
    motivo_anulacion: str | None
    items: list[VentaItemSalida]
    # Nombres para mostrar; los completa la ruta, no vienen del modelo.
    medio_pago: str | None = None
    vendedor: str | None = None
    cliente: str | None = None


class VentaResumenSalida(BaseModel):
    """Fila del historial, sin el detalle de las lineas."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_hora: datetime
    total: Decimal
    estado: EstadoVenta
    id_usuario: int
    id_medio_pago: int
    id_cliente: int | None
    cantidad_articulos: int
    # Nombres para mostrar; los completa la ruta, no vienen del modelo.
    medio_pago: str | None = None
    vendedor: str | None = None
    cliente: str | None = None


class MedioPagoEntrada(BaseModel):
    """Alta de medio de cobro."""

    nombre: str = Field(min_length=1, max_length=50)
    es_efectivo: bool = False

    @field_validator("nombre")
    @classmethod
    def _nombre_limpio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacio.")
        return limpio


class MedioPagoSalida(BaseModel):
    """Medio de cobro tal como lo devuelve la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    es_efectivo: bool
    activo: bool


class ClienteEntrada(BaseModel):
    """Alta o edicion de cliente."""

    nombre: str = Field(min_length=1, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)
    documento: str | None = Field(default=None, max_length=20)
    cuit: str | None = Field(default=None, max_length=15)
    telefono: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    direccion: str | None = Field(default=None, max_length=180)
    localidad: str | None = Field(default=None, max_length=90)
    notas: str | None = Field(default=None, max_length=500)

    @field_validator("nombre")
    @classmethod
    def _nombre_limpio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacio.")
        return limpio

    @field_validator(
        "apellido",
        "documento",
        "cuit",
        "telefono",
        "direccion",
        "localidad",
        "notas",
    )
    @classmethod
    def _texto_limpio(cls, valor: str | None) -> str | None:
        return _limpiar(valor)


class ClienteSalida(BaseModel):
    """Cliente tal como lo devuelve la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str | None
    nombre_completo: str
    documento: str | None
    cuit: str | None
    telefono: str | None
    email: str | None
    direccion: str | None
    localidad: str | None
    notas: str | None
    activo: bool


class ResumenComprasSalida(BaseModel):
    """Cuanto compro un cliente (RF-F03)."""

    cantidad_compras: int
    total_comprado: Decimal
    ultima_compra: datetime | None
