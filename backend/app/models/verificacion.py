"""Codigos de un solo uso: verificar el correo y recuperar la clave."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TipoCodigo(StrEnum):
    """Para que sirve un codigo emitido."""

    VERIFICACION = "verificacion"
    RECUPERACION = "recuperacion"


class CodigoUnico(Base):
    """Codigo emitido a una direccion de correo.

    Se guarda la huella, no el codigo: quien lea la base no puede usarla
    para entrar a una cuenta ajena. El correo tambien viaja hasheado
    cuando se busca, pero se conserva en claro porque hace falta para
    reenviar y para limpiar los vencidos.
    """

    __tablename__ = "codigos_unicos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    codigo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tipo: Mapped[TipoCodigo] = mapped_column(
        Enum(TipoCodigo, native_enum=False, length=20), nullable=False
    )
    expira_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # Un solo uso: se marca al consumirlo y no se borra, para que un
    # segundo intento con el mismo codigo se distinga de uno inexistente.
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def esta_vigente(self, ahora: datetime | None = None) -> bool:
        """True si todavia se puede canjear."""
        if self.usado:
            return False
        momento = ahora or datetime.now(UTC)
        vence = self.expira_en
        if vence.tzinfo is None:
            # SQLite devuelve la fecha sin zona; se asume UTC, que es
            # como se guardo.
            vence = vence.replace(tzinfo=UTC)
        return vence > momento
