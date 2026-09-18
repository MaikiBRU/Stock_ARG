"""Entrada y salida de movimientos de inventario."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models import MotivoBaja, TipoMovimiento

# Tipos que puede pedir una persona. venta y baja los genera el sistema
# por sus propios caminos: dejarlos aca permitiria inventar una venta
# que nunca ocurrio o saltear el registro de la baja.
TIPOS_MANUALES = {
    TipoMovimiento.ENTRADA,
    TipoMovimiento.SALIDA,
    TipoMovimiento.AJUSTE,
    TipoMovimiento.DEVOLUCION,
}


class MovimientoEntrada(BaseModel):
    """Alta manual de un movimiento (RF-D03)."""

    id_producto: int
    tipo: TipoMovimiento
    # Cero solo vale en un ajuste (un estante vacio); lo controla el
    # validador de abajo.
    cantidad: int = Field(ge=0)
    nota: str | None = Field(default=None, max_length=255)

    @field_validator("tipo")
    @classmethod
    def _solo_tipos_manuales(cls, valor: TipoMovimiento) -> TipoMovimiento:
        if valor not in TIPOS_MANUALES:
            admitidos = ", ".join(sorted(t.value for t in TIPOS_MANUALES))
            raise ValueError(
                f"El tipo {valor.value} lo registra el sistema. "
                f"Admitidos: {admitidos}."
            )
        return valor

    @model_validator(mode="after")
    def _cero_solo_en_ajuste(self) -> "MovimientoEntrada":
        if self.cantidad == 0 and self.tipo is not TipoMovimiento.AJUSTE:
            raise ValueError("La cantidad debe ser mayor a cero.")
        return self


class BajaEntrada(BaseModel):
    """Descarte de mercaderia (RF-D06)."""

    id_producto: int
    cantidad: int = Field(gt=0)
    motivo: MotivoBaja
    detalle: str | None = Field(default=None, max_length=255)


class MovimientoSalida(BaseModel):
    """Movimiento tal como lo devuelve la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_producto: int
    tipo: TipoMovimiento
    cantidad: int
    stock_resultante: int
    nota: str | None
    id_venta: int | None
    id_compra: int | None
    id_usuario: int
    fecha_hora: datetime
    # Nombres para mostrar; los completa la ruta.
    producto: str | None = None
    usuario: str | None = None


class ResumenStock(BaseModel):
    """Cuantos productos hay en cada estado (RF-D02)."""

    total: int
    bajo: int
    medio: int
    ok: int
    sin_stock: int
