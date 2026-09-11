"""Registro de auditoria de las operaciones sensibles (RF-I04)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Auditoria(Base):
    """Quien hizo que, sobre que, y cuando.

    El detalle va en JSON porque cada accion guarda cosas distintas.
    Nunca debe contener contrasenas ni tokens.
    """

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Se copia el correo por si la cuenta se elimina mas adelante: la
    # linea de auditoria tiene que seguir diciendo quien fue.
    email_usuario: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    accion: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entidad: Mapped[str] = mapped_column(String(40), nullable=False)
    id_entidad: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
