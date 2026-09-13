"""Usuarios del sistema y sus roles."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MarcaDeTiempo, indices_unicos_particionados


class Rol(StrEnum):
    """Roles previstos, de mayor a menor alcance."""

    PROPIETARIO = "propietario"
    ENCARGADO = "encargado"
    VENDEDOR = "vendedor"


class Usuario(MarcaDeTiempo, Base):
    """Persona autorizada a operar el sistema.

    El hash de contrasena admite nulo: una cuenta creada con Google no
    tiene contrasena hasta que su duena decide ponerle una.
    """

    __tablename__ = "usuarios"
    __table_args__ = indices_unicos_particionados("usuarios", "email")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    google_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rol: Mapped[Rol] = mapped_column(
        Enum(Rol, native_enum=False, length=20),
        nullable=False,
        default=Rol.VENDEDOR,
    )
    verificado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Fuerza bruta (RF-A05): cinco intentos, diez minutos de bloqueo.
    intentos_fallidos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Cierre de sesion (RF-A06). El token lleva esta version; cerrar
    # sesion la incrementa y todo token anterior deja de valer. Se usa
    # un contador y no una marca de tiempo porque el "iat" de un token
    # tiene resolucion de segundos: con relojes no se puede distinguir
    # un token emitido justo antes del cierre de uno emitido justo
    # despues, dentro del mismo segundo.
    version_sesion: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    id_sesion_demo: Mapped[str | None] = mapped_column(
        ForeignKey("sesiones_demo.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    @property
    def puede_administrar(self) -> bool:
        """True si el rol administra usuarios y configuracion."""
        return self.rol is Rol.PROPIETARIO

    @property
    def puede_gestionar(self) -> bool:
        """True si el rol gestiona productos, stock y reportes."""
        return self.rol in (Rol.PROPIETARIO, Rol.ENCARGADO)
