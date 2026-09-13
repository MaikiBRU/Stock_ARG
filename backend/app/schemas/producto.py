"""Entrada y salida de productos y categorias."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _limpiar(valor: str | None) -> str | None:
    """Recorta espacios y convierte la cadena vacia en nulo."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


class CategoriaEntrada(BaseModel):
    """Alta o edicion de una categoria."""

    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def _nombre_limpio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacio.")
        return limpio

    @field_validator("descripcion")
    @classmethod
    def _descripcion_limpia(cls, valor: str | None) -> str | None:
        return _limpiar(valor)


class CategoriaSalida(BaseModel):
    """Categoria tal como la devuelve la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    activo: bool


class ProductoEntrada(BaseModel):
    """Alta o edicion de un producto."""

    nombre: str = Field(min_length=1, max_length=140)
    codigo_barra: str | None = Field(default=None, max_length=50)
    descripcion: str | None = Field(default=None, max_length=500)
    precio_venta: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    precio_costo: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2
    )
    stock_actual: int = Field(default=0, ge=0)
    stock_minimo: int = Field(default=0, ge=0)
    stock_inicial: int | None = Field(default=None, ge=0)
    fecha_vencimiento: date | None = None
    id_categoria: int | None = None
    id_proveedor: int | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre_limpio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacio.")
        return limpio

    @field_validator("codigo_barra", "descripcion")
    @classmethod
    def _texto_limpio(cls, valor: str | None) -> str | None:
        return _limpiar(valor)


class ProductoSalida(BaseModel):
    """Producto tal como lo devuelve la API.

    El precio de costo y el margen viajan aparte: se completan solo para
    quien tiene permiso de verlos (RF-H06).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    codigo_barra: str | None
    descripcion: str | None
    precio_venta: Decimal
    precio_costo: Decimal | None = None
    margen: Decimal | None = None
    stock_actual: int
    stock_minimo: int
    stock_inicial: int
    porcentaje_stock: int
    estado_stock: str
    bajo_minimo: bool
    fecha_vencimiento: date | None
    id_categoria: int | None
    id_proveedor: int | None
    activo: bool
    categoria: CategoriaSalida | None = None


class FilaImportadaSalida(BaseModel):
    """Que paso, o pasaria, con una fila del archivo (RF-C10)."""

    numero: int
    accion: str
    nombre: str | None
    codigo_barra: str | None
    errores: list[str]


class ImportacionSalida(BaseModel):
    """Resultado de previsualizar o aplicar una importacion."""

    aplicada: bool
    a_crear: int
    a_actualizar: int
    con_error: int
    filas: list[FilaImportadaSalida]
