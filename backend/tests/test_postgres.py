"""Lo que solo PostgreSQL puede confirmar.

La suite corre en SQLite para no depender de contenedores (RNF-10), pero
hay garantias que SQLite no puede dar: los indices unicos parciales, el
borrado en cascada de verdad, el bloqueo de filas que evita vender dos
veces el mismo articulo y las fechas con zona. Produccion corre sobre
PostgreSQL, asi que eso se prueba donde vale.

Se saltean si no hay una base a mano. Para correrlas: levantar la base
con "docker compose up -d db", exportar DATABASE_URL_PRUEBAS con la URL
de esa base y correr "pytest -m postgres".
"""

import os
import threading
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core import tiempo
from app.db import particion
from app.db.base import Base
from app.models import (
    MedioPago,
    MovimientoStock,
    Producto,
    Rol,
    SesionDemo,
    Usuario,
    Venta,
)
from app.services import reportes
from app.services import ventas as servicio_ventas

URL = os.environ.get("DATABASE_URL_PRUEBAS")
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not URL, reason="Sin DATABASE_URL_PRUEBAS no hay PostgreSQL a mano."
    ),
]


@pytest.fixture(scope="module")
def motor():
    """Esquema creado con los modelos, igual que en la suite de SQLite."""
    motor = create_engine(URL, future=True)
    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)
    yield motor
    Base.metadata.drop_all(motor)
    motor.dispose()


@pytest.fixture
def db(motor):
    """Sesion limpia: cada caso arranca con las tablas vacias."""
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)
    with fabrica() as sesion:
        yield sesion
        sesion.rollback()

    tablas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with motor.begin() as conexion:
        conexion.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))


def _sesion_demo(db, ident):
    ahora = tiempo.ahora()
    db.add(
        SesionDemo(
            id=ident,
            creada_en=ahora,
            ultima_actividad=ahora,
            expira_en=ahora + timedelta(minutes=45),
        )
    )
    db.commit()


def _comercio(db, *, stock=1, id_sesion_demo=None):
    """Un usuario, un medio de cobro y un producto con stock."""
    usuario = Usuario(
        email="propietario@stockarg.com.ar",
        nombre="Propietaria",
        rol=Rol.PROPIETARIO,
        verificado=True,
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    medio = MedioPago(
        nombre="Efectivo", es_efectivo=True, id_sesion_demo=id_sesion_demo
    )
    producto = Producto(
        nombre="Alfajor",
        precio_venta=Decimal("1000.00"),
        precio_costo=Decimal("600.00"),
        stock_actual=stock,
        stock_inicial=stock,
        id_sesion_demo=id_sesion_demo,
    )
    db.add_all([usuario, medio, producto])
    db.commit()
    return usuario.id, medio.id, producto.id


# --- indices unicos parciales --------------------------------------------


def test_dos_sandboxes_pueden_tener_el_mismo_codigo_de_barras(db):
    """Sin indices parciales, el segundo visitante no podria sembrarse."""
    _sesion_demo(db, "sid-a")
    _sesion_demo(db, "sid-b")

    for ident in ("sid-a", "sid-b"):
        db.add(
            Producto(
                nombre="Alfajor",
                codigo_barra="2000000001",
                precio_venta=Decimal("1000.00"),
                id_sesion_demo=ident,
            )
        )
    db.commit()

    assert db.scalar(select(func.count()).select_from(Producto)) == 2


def test_la_aplicacion_sigue_sin_admitir_dos_codigos_iguales(db):
    db.add(
        Producto(
            nombre="Alfajor",
            codigo_barra="2000000001",
            precio_venta=Decimal("1000.00"),
        )
    )
    db.commit()

    db.add(
        Producto(
            nombre="Otro",
            codigo_barra="2000000001",
            precio_venta=Decimal("900.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_dos_sandboxes_pueden_tener_el_mismo_correo(db):
    _sesion_demo(db, "sid-a")
    _sesion_demo(db, "sid-b")

    for ident in ("sid-a", "sid-b"):
        db.add(
            Usuario(
                email="propietario@demo.stockarg.com.ar",
                nombre="Demo",
                rol=Rol.PROPIETARIO,
                id_sesion_demo=ident,
            )
        )
    db.commit()

    assert db.scalar(select(func.count()).select_from(Usuario)) == 2


# --- borrado en cascada ---------------------------------------------------


def test_borrar_la_sesion_arrastra_todas_sus_filas(db):
    """En SQLite la cascada depende de un PRAGMA; aca es del motor."""
    _sesion_demo(db, "sid-a")
    _comercio(db, id_sesion_demo="sid-a")
    db.add(Producto(nombre="De la aplicacion", precio_venta=Decimal("10.00")))
    db.commit()

    db.execute(text("DELETE FROM sesiones_demo WHERE id = 'sid-a'"))
    db.commit()

    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    restantes = db.scalars(select(Producto)).all()
    assert [p.nombre for p in restantes] == ["De la aplicacion"]


# --- bloqueo de filas (RNF-07) -------------------------------------------


def test_dos_cajas_no_venden_dos_veces_el_ultimo_articulo(db, motor):
    """El bloqueo de fila es lo unico que evita vender stock que no hay.

    Las dos ventas arrancan a la vez sobre el mismo producto, que tiene
    una sola unidad. En SQLite esto no prueba nada, porque escribe de a
    una operacion por vez.
    """
    id_usuario, id_medio, id_producto = _comercio(db, stock=1)
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)
    partida = threading.Barrier(2)
    resultados: list[str] = []
    candado = threading.Lock()

    def vender():
        with fabrica() as sesion:
            usuario = sesion.get(Usuario, id_usuario)
            partida.wait(timeout=10)
            try:
                servicio_ventas.registrar(
                    sesion,
                    lineas=[
                        servicio_ventas.LineaPedida(
                            id_producto=id_producto, cantidad=1
                        )
                    ],
                    id_medio_pago=id_medio,
                    usuario=usuario,
                )
                sesion.commit()
                resultado = "vendida"
            except servicio_ventas.StockInsuficiente:
                sesion.rollback()
                resultado = "sin stock"
            with candado:
                resultados.append(resultado)

    hilos = [threading.Thread(target=vender) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert sorted(resultados) == ["sin stock", "vendida"]
    db.expire_all()
    assert db.get(Producto, id_producto).stock_actual == 0
    assert db.scalar(select(func.count()).select_from(Venta)) == 1
    assert db.scalar(select(func.count()).select_from(MovimientoStock)) == 1


# --- fechas con zona (RNF-15) --------------------------------------------


def test_la_venta_de_las_once_de_la_noche_entra_en_el_dia_del_comercio(db):
    """Con timestamptz, la conversion la hace el motor y no el ORM."""
    id_usuario, id_medio, _ = _comercio(db)
    hoy = tiempo.hoy()
    db.add(
        Venta(
            fecha_hora=datetime.combine(
                hoy, time(23, 30), tzinfo=ZONA
            ).astimezone(UTC),
            id_usuario=id_usuario,
            id_medio_pago=id_medio,
            total=Decimal("1000.00"),
            descuento=Decimal("0.00"),
        )
    )
    db.commit()

    datos = reportes.ventas_por_periodo(db, periodo="hoy")
    serie = {
        punto["fecha"]: punto["cantidad_ventas"]
        for punto in reportes.serie_diaria(db, periodo="semana")
    }

    assert datos["cantidad_ventas"] == 1
    assert serie[hoy] == 1


# --- aislamiento por particion (RF-J03) ----------------------------------


def test_el_cerrojo_de_particion_tambien_filtra_en_postgres(db):
    _sesion_demo(db, "sid-a")
    _comercio(db, id_sesion_demo="sid-a")
    db.add(Producto(nombre="De la aplicacion", precio_venta=Decimal("10.00")))
    db.commit()
    db.expunge_all()

    particion.fijar(db, "sid-a")
    del_sandbox = db.scalars(select(Producto.nombre)).all()
    particion.fijar(db, None)
    de_la_aplicacion = db.scalars(select(Producto.nombre)).all()
    particion.liberar(db)

    assert list(del_sandbox) == ["Alfajor"]
    assert list(de_la_aplicacion) == ["De la aplicacion"]


def test_escribir_fuera_de_la_particion_aborta_en_postgres(db):
    _sesion_demo(db, "sid-a")
    particion.fijar(db, "sid-a")

    db.add(Producto(nombre="Colado", precio_venta=Decimal("10.00")))
    with pytest.raises(particion.FugaDeParticion):
        db.flush()

    db.rollback()
    particion.liberar(db)
