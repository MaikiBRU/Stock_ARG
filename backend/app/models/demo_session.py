"""Sesion de la demo publica (modulo J)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SesionDemo(Base):
    """Sandbox anonimo y temporal de un visitante del portfolio.

    La clave primaria es un token generado con el modulo secrets, no una
    secuencia: no se puede enumerar probando numeros consecutivos.
    """

    __tablename__ = "sesiones_demo"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ultima_actividad: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expira_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # La direccion se guarda hasheada con la clave de la aplicacion: se
    # puede contar cuantas sesiones abrio un visitante sin conservar de
    # quien era la conexion.
    ip_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    # Cupos de acciones (RF-J06). Sobreviven al reinicio del sandbox: si
    # no, reiniciar serviria para esquivarlos.
    importaciones: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    exportaciones: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
