"""Motor de base de datos y dependencia de sesion."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

# pool_pre_ping evita entregar una conexion que el servidor ya cerro,
# que es lo que pasa cuando la instancia queda inactiva de noche.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """Entrega una sesion y la cierra al terminar la peticion."""
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
