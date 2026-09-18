"""Entrada y salida de los endpoints de cuentas."""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Rol

LARGO_MINIMO_CONTRASENA = 8
# Igual que en el hash: bcrypt no mira mas alla de 72 bytes.
LARGO_MAXIMO_CONTRASENA = 72


def _validar_fortaleza(valor: str) -> str:
    """Exige una contrasena que no se adivine en dos intentos."""
    if len(valor) < LARGO_MINIMO_CONTRASENA:
        raise ValueError(
            f"La contrasena debe tener al menos "
            f"{LARGO_MINIMO_CONTRASENA} caracteres."
        )
    if len(valor.encode("utf-8")) > LARGO_MAXIMO_CONTRASENA:
        raise ValueError(
            f"La contrasena no puede superar los "
            f"{LARGO_MAXIMO_CONTRASENA} bytes."
        )
    if not re.search(r"[A-Za-z]", valor):
        raise ValueError("La contrasena debe incluir al menos una letra.")
    if not re.search(r"\d", valor):
        raise ValueError("La contrasena debe incluir al menos un numero.")
    return valor


class RegistroEntrada(BaseModel):
    """Alta de una cuenta nueva."""

    email: EmailStr
    nombre: str = Field(min_length=2, max_length=120)
    contrasena: str

    @field_validator("contrasena")
    @classmethod
    def _fortaleza(cls, valor: str) -> str:
        return _validar_fortaleza(valor)

    @field_validator("nombre")
    @classmethod
    def _sin_espacios_sobrantes(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres.")
        return limpio


class VerificacionEntrada(BaseModel):
    """Canje del codigo enviado por correo."""

    email: EmailStr
    codigo: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ReenvioEntrada(BaseModel):
    """Pedido de un codigo nuevo."""

    email: EmailStr


class LoginEntrada(BaseModel):
    """Credenciales de ingreso."""

    email: EmailStr
    contrasena: str = Field(min_length=1, max_length=200)


class RecuperacionEntrada(BaseModel):
    """Pedido de restablecimiento de contrasena."""

    email: EmailStr


class RestablecerEntrada(BaseModel):
    """Fijado de una contrasena nueva con el token del correo."""

    token: str = Field(min_length=20, max_length=200)
    contrasena: str

    @field_validator("contrasena")
    @classmethod
    def _fortaleza(cls, valor: str) -> str:
        return _validar_fortaleza(valor)


class CambioContrasenaEntrada(BaseModel):
    """Cambio de contrasena desde el perfil."""

    contrasena_actual: str = Field(min_length=1, max_length=200)
    contrasena_nueva: str

    @field_validator("contrasena_nueva")
    @classmethod
    def _fortaleza(cls, valor: str) -> str:
        return _validar_fortaleza(valor)


class PerfilEntrada(BaseModel):
    """Edicion de los datos propios."""

    nombre: str = Field(min_length=2, max_length=120)

    @field_validator("nombre")
    @classmethod
    def _sin_espacios_sobrantes(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres.")
        return limpio


class UsuarioSalida(BaseModel):
    """Datos de un usuario que la API si puede devolver.

    No incluye password_hash, google_id, intentos ni bloqueo: nada de eso
    le sirve al frontend y todo eso ayuda a quien quiera atacar la cuenta.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nombre: str
    rol: Rol
    activo: bool


class TokenSalida(BaseModel):
    """Respuesta de un ingreso correcto."""

    access_token: str
    token_type: str = "bearer"
    expira_en_minutos: int
    usuario: UsuarioSalida
    # Quien entro con Google todavia no tiene contrasena. La pantalla lo
    # usa para ofrecerle ponerle una (RF-A03).
    sin_contrasena: bool = False


class GoogleEntrada(BaseModel):
    """Token de identidad que devuelve Google en el navegador."""

    model_config = ConfigDict(extra="forbid")

    credential: str = Field(min_length=1, max_length=4096)


class MensajeSalida(BaseModel):
    """Respuesta sin datos, solo con el resultado."""

    mensaje: str
