"""Contratos de la demo publica (modulo J)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import Rol
from app.schemas.auth import UsuarioSalida


class SesionDemoSalida(BaseModel):
    """Token de un sandbox y la persona con la que se entra."""

    access_token: str
    token_type: str = "bearer"
    expira_en: datetime
    usuario: UsuarioSalida
    roles: list[Rol]


class RolDemoEntrada(BaseModel):
    """Rol con el que se quiere recorrer la demo."""

    model_config = ConfigDict(extra="forbid")

    rol: Rol


class CupoSalida(BaseModel):
    """Cuanto se uso de un cupo y cuanto hay."""

    usados: int
    maximo: int


class EstadoDemoSalida(BaseModel):
    """Lo que necesita la franja de modo demo (RF-J10)."""

    expira_en: datetime
    vence_por_inactividad_en: datetime
    segundos_restantes: int
    rol: Rol
    cupos: dict[str, CupoSalida]


class LimpiezaSalida(BaseModel):
    """Resultado de una pasada de limpieza."""

    eliminadas: int
