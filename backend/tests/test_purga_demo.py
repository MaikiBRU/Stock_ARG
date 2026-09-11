"""Borrado de un sandbox: no puede dejar filas huerfanas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    MedioPago,
    MovimientoStock,
    Producto,
    SesionDemo,
    TipoMovimiento,
    Usuario,
    Venta,
    VentaItem,
)


def _sandbox_poblado(db, ident="sesion-a"):
    """Crea una sesion demo con un producto vendido y su movimiento."""
    ahora = datetime.now(UTC)
    db.add(
        SesionDemo(
            id=ident,
            creada_en=ahora,
            ultima_actividad=ahora,
            expira_en=ahora + timedelta(minutes=45),
        )
    )
    db.commit()

    usuario = Usuario(
        email="demo@stockarg.com.ar", nombre="Demo", id_sesion_demo=ident
    )
    medio = MedioPago(nombre="Efectivo", es_efectivo=True, id_sesion_demo=ident)
    producto = Producto(nombre="Alfajor", stock_actual=9, id_sesion_demo=ident)
    db.add_all([usuario, medio, producto])
    db.commit()

    venta = Venta(
        id_usuario=usuario.id,
        id_medio_pago=medio.id,
        total=Decimal("1200.00"),
        id_sesion_demo=ident,
    )
    venta.items.append(
        VentaItem(
            id_producto=producto.id,
            nombre_producto=producto.nombre,
            cantidad=1,
            precio_unitario=Decimal("1200.00"),
            subtotal=Decimal("1200.00"),
            id_sesion_demo=ident,
        )
    )
    db.add(venta)
    db.commit()

    db.add(
        MovimientoStock(
            id_producto=producto.id,
            tipo=TipoMovimiento.VENTA,
            cantidad=1,
            stock_resultante=9,
            id_usuario=usuario.id,
            id_venta=venta.id,
            id_sesion_demo=ident,
        )
    )
    db.commit()
    return ident


def test_borrar_el_sandbox_no_deja_nada_atras(db):
    """Un solo DELETE sobre la sesion tiene que limpiar todo.

    Si las tablas hijas no cuelgan de la sesion, este borrado falla por
    violacion de clave foranea o deja filas sin duena. Cualquiera de las
    dos cosas convierte la limpieza periodica en una bomba de tiempo.
    """
    _sandbox_poblado(db)

    db.query(SesionDemo).filter_by(id="sesion-a").delete()
    db.commit()

    assert db.query(SesionDemo).count() == 0
    assert db.query(Usuario).count() == 0
    assert db.query(Producto).count() == 0
    assert db.query(Venta).count() == 0
    assert db.query(VentaItem).count() == 0
    assert db.query(MovimientoStock).count() == 0


def test_borrar_un_sandbox_no_toca_a_otro(db):
    _sandbox_poblado(db, "sesion-a")
    _sandbox_poblado(db, "sesion-b")

    db.query(SesionDemo).filter_by(id="sesion-a").delete()
    db.commit()

    assert db.query(SesionDemo).count() == 1
    assert db.query(Producto).count() == 1
    assert db.query(MovimientoStock).count() == 1


def test_borrar_un_sandbox_no_toca_los_datos_de_la_app(db):
    _sandbox_poblado(db, "sesion-a")
    db.add(Producto(nombre="Producto real", stock_actual=5))
    db.commit()

    db.query(SesionDemo).filter_by(id="sesion-a").delete()
    db.commit()

    restantes = db.query(Producto).all()
    assert len(restantes) == 1
    assert restantes[0].nombre == "Producto real"
    assert restantes[0].id_sesion_demo is None


def test_una_fila_sin_marca_de_sesion_sobrevive_al_purgado(db):
    """Fija el contrato que tiene que cumplir la capa de servicios.

    La columna de particion no se hereda sola: si el codigo que crea un
    movimiento dentro de un sandbox no la copia, la fila queda sin duena
    y la limpieza no se la lleva. Esta prueba existe para que ese
    descuido se vea como un cambio de comportamiento y no en produccion.
    """
    _sandbox_poblado(db, "sesion-a")
    producto = db.query(Producto).filter_by(id_sesion_demo="sesion-a").one()
    usuario = db.query(Usuario).filter_by(id_sesion_demo="sesion-a").one()
    db.add(
        MovimientoStock(
            id_producto=producto.id,
            tipo=TipoMovimiento.AJUSTE,
            cantidad=1,
            stock_resultante=10,
            id_usuario=usuario.id,
            id_sesion_demo=None,
        )
    )
    db.commit()

    with pytest.raises(IntegrityError):
        db.query(SesionDemo).filter_by(id="sesion-a").delete()
        db.commit()
