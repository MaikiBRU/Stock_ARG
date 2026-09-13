"""Aislamiento entre la aplicacion y los sandboxes, en la capa ORM.

Estas pruebas no pasan por las rutas a proposito: fijan el cerrojo que
tiene que aguantar aunque un servicio o una ruta se olviden de filtrar.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import ajustes_vivos
from app.core.security import crear_token
from app.db import particion
from app.models import Categoria, Producto, Rol, SesionDemo, Usuario


def _sesion_demo(db, ident):
    ahora = datetime.now(UTC)
    db.add(
        SesionDemo(
            id=ident,
            creada_en=ahora,
            ultima_actividad=ahora,
            expira_en=ahora + timedelta(minutes=45),
        )
    )
    db.flush()


@pytest.fixture
def poblada(db):
    """Un producto real y uno en cada uno de dos sandboxes."""
    _sesion_demo(db, "sid-a")
    _sesion_demo(db, "sid-b")
    db.add_all(
        [
            Producto(nombre="Real", stock_actual=1),
            Producto(nombre="Demo A", stock_actual=1, id_sesion_demo="sid-a"),
            Producto(nombre="Demo B", stock_actual=1, id_sesion_demo="sid-b"),
        ]
    )
    db.commit()
    ids = {p.nombre: p.id for p in db.scalars(select(Producto))}
    # Fuera del mapa de identidad: si no, Session.get devolveria el
    # objeto en memoria sin consultar y la prueba no probaria nada.
    db.expunge_all()
    yield ids
    particion.liberar(db)


def _nombres(db):
    return sorted(db.scalars(select(Producto.nombre)))


def test_sin_particion_se_ven_todas_las_filas(db, poblada):
    """Los procesos del sistema, como la limpieza, necesitan verlo todo."""
    assert _nombres(db) == ["Demo A", "Demo B", "Real"]


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(None, ["Real"]), ("sid-a", ["Demo A"]), ("sid-b", ["Demo B"])],
)
def test_cada_particion_ve_solo_lo_suyo(db, poblada, valor, esperado):
    particion.fijar(db, valor)

    assert _nombres(db) == esperado
    assert db.scalar(select(func.count(Producto.id))) == 1


def test_alternar_particiones_no_reutiliza_un_valor_anterior(db, poblada):
    """El criterio se cachea como sentencia: el valor tiene que viajar."""
    for valor, nombre in [
        ("sid-a", "Demo A"),
        ("sid-b", "Demo B"),
        ("sid-a", "Demo A"),
        (None, "Real"),
    ]:
        particion.fijar(db, valor)
        assert _nombres(db) == [nombre]


def test_get_de_otra_particion_no_encuentra_nada(db, poblada):
    particion.fijar(db, "sid-a")

    assert db.get(Producto, poblada["Real"]) is None
    assert db.get(Producto, poblada["Demo B"]) is None
    assert db.get(Producto, poblada["Demo A"]) is not None


def test_un_update_masivo_no_cruza_de_particion(db, poblada):
    particion.fijar(db, "sid-a")
    db.execute(update(Producto).values(stock_actual=99))
    db.commit()

    particion.liberar(db)
    db.expunge_all()
    stocks = {p.nombre: p.stock_actual for p in db.scalars(select(Producto))}
    assert stocks == {"Real": 1, "Demo A": 99, "Demo B": 1}


def test_una_relacion_no_trae_una_fila_de_otra_particion(db):
    """Un sandbox que apunta a una categoria real no la ve."""
    _sesion_demo(db, "sid-a")
    real = Categoria(nombre="Real")
    db.add(real)
    db.flush()
    db.add(
        Producto(
            nombre="Demo",
            stock_actual=1,
            id_categoria=real.id,
            id_sesion_demo="sid-a",
        )
    )
    db.commit()
    db.expunge_all()

    particion.fijar(db, "sid-a")
    producto = db.scalars(select(Producto)).one()

    assert producto.categoria is None
    particion.liberar(db)


def test_crear_una_fila_de_la_aplicacion_desde_un_sandbox_aborta(db, poblada):
    particion.fijar(db, "sid-a")
    db.add(Producto(nombre="Colado", stock_actual=1))

    with pytest.raises(particion.FugaDeParticion):
        db.flush()
    db.rollback()


def test_la_aplicacion_no_puede_escribir_en_un_sandbox(db, poblada):
    particion.fijar(db, None)
    db.add(Producto(nombre="Colado", stock_actual=1, id_sesion_demo="sid-a"))

    with pytest.raises(particion.FugaDeParticion):
        db.flush()
    db.rollback()


def test_mover_una_fila_de_particion_aborta(db, poblada):
    particion.fijar(db, "sid-a")
    producto = db.get(Producto, poblada["Demo A"])
    producto.id_sesion_demo = None

    with pytest.raises(particion.FugaDeParticion):
        db.flush()
    db.rollback()


def test_un_token_de_la_aplicacion_no_abre_un_usuario_de_sandbox(client, db):
    """Los ids de usuario son una secuencia: se pueden adivinar."""
    _sesion_demo(db, "sid-a")
    usuario = Usuario(
        email="propietario@demo.stockarg.com.ar",
        nombre="Demo",
        rol=Rol.PROPIETARIO,
        verificado=True,
        activo=True,
        id_sesion_demo="sid-a",
    )
    db.add(usuario)
    db.commit()

    token = crear_token(str(usuario.id), rol="propietario")
    respuesta = client.get(
        "/auth/perfil", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 401


def test_los_parametros_de_una_peticion_no_alcanzan_a_otra(engine):
    """Dos peticiones simultaneas tienen sesiones y parametros propios.

    Con una cache global, el tope de descuento que fija el propietario de
    un sandbox lo leeria un vendedor real que cobra en el mismo momento.
    """
    with Session(engine) as sandbox, Session(engine) as aplicacion:
        ajustes_vivos.fijar(sandbox, {"descuento_max_vendedor": "100"})
        ajustes_vivos.fijar(aplicacion, {})

        assert ajustes_vivos.entero("descuento_max_vendedor", sandbox) == 100
        assert ajustes_vivos.entero("descuento_max_vendedor", aplicacion) == (
            10
        )
