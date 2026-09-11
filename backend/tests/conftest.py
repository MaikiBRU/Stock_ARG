"""Configuracion comun de las pruebas.

La suite corre sin contenedores ni base externa (RNF-10): SQLite en
memoria, y la aplicacion real por encima.
"""

import os

os.environ.setdefault("SECRET_KEY", "clave-de-prueba-suficientemente-larga")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import crear_app  # noqa: E402
from app.models import *  # noqa: E402,F401,F403


@pytest.fixture
def engine():
    """Base SQLite en memoria, compartida por toda la prueba."""
    motor = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignora las claves foraneas salvo que se pidan explicitamente.
    # Sin esto la suite daria por buenos borrados que PostgreSQL rechaza.
    @event.listens_for(motor, "connect")
    def _activar_fk(conexion, _registro):
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(motor)
    yield motor
    Base.metadata.drop_all(motor)
    motor.dispose()


@pytest.fixture
def db(engine):
    """Sesion contra la base de la prueba."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = Session()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def client(db):
    """Cliente HTTP con la base de la prueba inyectada."""
    app = crear_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
