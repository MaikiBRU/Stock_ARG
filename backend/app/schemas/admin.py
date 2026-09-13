"""Entrada y salida del panel y de la administracion."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Rol
from app.schemas.auth import UsuarioSalida, _validar_fortaleza
from app.schemas.compra import (
    FilaMedioPagoSalida,
    FilaRankingSalida,
    PuntoSerieSalida,
    VentasPeriodoSalida,
)
from app.schemas.producto import ProductoSalida
from app.schemas.stock import ResumenStock


class PanelSalida(BaseModel):
    """Todo lo que muestra el panel principal (RF-B01 a RF-B08)."""

    fecha: date
    ventas_del_dia: VentasPeriodoSalida
    medios_de_pago: list[FilaMedioPagoSalida]
    resumen_stock: ResumenStock
    bajo_minimo: list[ProductoSalida]
    proximos_a_vencer: list[ProductoSalida]
    vencidos: list[ProductoSalida]
    mas_vendidos_del_mes: list[FilaRankingSalida]
    serie_ventas: list[PuntoSerieSalida]
    dias_aviso_vencimiento: int
    # Solo se completa para quien puede ver los costos.
    rentabilidad_del_mes: Decimal | None = None


class UsuarioNuevoEntrada(BaseModel):
    """Alta de usuario desde la administracion (RF-I01)."""

    email: EmailStr
    nombre: str = Field(min_length=2, max_length=120)
    contrasena: str
    rol: Rol = Rol.VENDEDOR

    @field_validator("contrasena")
    @classmethod
    def _fortaleza(cls, valor: str) -> str:
        return _validar_fortaleza(valor)

    @field_validator("nombre")
    @classmethod
    def _nombre_limpio(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres.")
        return limpio


class RolEntrada(BaseModel):
    """Cambio de rol."""

    rol: Rol


class UsuarioAdminSalida(UsuarioSalida):
    """Usuario con los datos que solo ve la administracion."""

    model_config = ConfigDict(from_attributes=True)

    verificado: bool
    bloqueado: bool = False


class AuditoriaSalida(BaseModel):
    """Una linea del registro de auditoria (RF-I04)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_usuario: int | None
    email_usuario: str | None
    accion: str
    entidad: str
    id_entidad: str | None
    detalle: dict[str, Any] | None
    ip: str | None
    fecha_hora: datetime


class ConfiguracionEntrada(BaseModel):
    """Cambios a la configuracion del comercio (RF-I06)."""

    cambios: dict[str, str] = Field(min_length=1)


class ConfiguracionSalida(BaseModel):
    """Configuracion vigente."""

    valores: dict[str, str]
