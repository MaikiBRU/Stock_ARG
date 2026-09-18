"""Configuracion comun de las pruebas.

La suite corre sin contenedores ni base externa (RNF-10): SQLite en
memoria, y la aplicacion real por encima.
"""

import os

os.environ.setdefault("SECRET_KEY", "clave-de-prueba-suficientemente-larga")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "development")
# Sin bucle de limpieza en segundo plano: las pruebas la llaman directo.
os.environ.setdefault("DEMO_CLEANUP_INTERVAL_SECONDS", "0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import ajustes_vivos  # noqa: E402
from app.db import particion  # noqa: E402
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

    def _db_de_la_prueba():
        # En produccion cada peticion abre su sesion. Aca se comparte la
        # de la prueba, asi que se le quita lo que la peticion le dejo
        # para que las verificaciones posteriores vean todas las filas.
        try:
            yield db
        finally:
            # Una peticion que se corta a mitad de un flush deja filas
            # pendientes. En produccion las descarta el cierre de la
            # sesion; aca la sesion sigue viva y hay que hacerlo a mano.
            if db.new or db.dirty or db.deleted or not db.is_active:
                db.rollback()
            particion.liberar(db)
            db.info.pop(ajustes_vivos.CLAVE_EN_SESION, None)

    app.dependency_overrides[get_db] = _db_de_la_prueba
    # Los errores no controlados se anotan con una sesion propia: aca
    # tiene que ser una sobre la misma base de la prueba.
    app.state.sesion_de_sistema = sessionmaker(
        bind=db.get_bind(), expire_on_commit=False
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sesiones(db):
    """Crea un usuario por rol y devuelve sus cabeceras de sesion.

    Evita repetir el alta completa con verificacion en cada prueba que
    solo necesita estar autenticada con determinado rol.
    """
    from app.core.security import crear_token, hash_contrasena
    from app.models import Rol, Usuario

    cabeceras = {}
    for rol in Rol:
        usuario = Usuario(
            email=f"{rol.value}@stockarg.com.ar",
            nombre=rol.value.capitalize(),
            password_hash=hash_contrasena("Kiosco2026"),
            rol=rol,
            verificado=True,
            activo=True,
        )
        db.add(usuario)
        db.flush()
        token = crear_token(str(usuario.id), rol=rol.value)
        cabeceras[rol.value] = {"Authorization": f"Bearer {token}"}
    db.commit()
    return cabeceras
