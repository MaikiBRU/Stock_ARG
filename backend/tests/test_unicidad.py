"""Unicidad por particion: la aplicacion y cada sandbox, por separado."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Cliente, Producto, SesionDemo, Usuario


def _usuario(email, nombre, sesion=None):
    return Usuario(email=email, nombre=nombre, id_sesion_demo=sesion)


def _sesion(db, ident):
    ahora = datetime.now(UTC)
    s = SesionDemo(
        id=ident,
        creada_en=ahora,
        ultima_actividad=ahora,
        expira_en=ahora + timedelta(minutes=45),
    )
    db.add(s)
    db.commit()
    return s


def test_la_app_no_admite_dos_veces_el_mismo_email(db):
    db.add(_usuario("ana@stockarg.test", "Ana"))
    db.commit()
    db.add(_usuario("ana@stockarg.test", "Otra Ana"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_dos_sandboxes_pueden_sembrar_el_mismo_email(db):
    _sesion(db, "sesion-a")
    _sesion(db, "sesion-b")

    db.add(_usuario("demo@stockarg.test", "A", "sesion-a"))
    db.add(_usuario("demo@stockarg.test", "B", "sesion-b"))
    db.commit()

    assert db.query(Usuario).count() == 2


def test_un_sandbox_no_admite_dos_veces_el_mismo_email(db):
    _sesion(db, "sesion-a")
    db.add(_usuario("demo@stockarg.test", "A", "sesion-a"))
    db.commit()
    db.add(_usuario("demo@stockarg.test", "B", "sesion-a"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_un_email_de_la_app_no_choca_con_uno_de_demo(db):
    _sesion(db, "sesion-a")
    db.add(_usuario("ana@stockarg.test", "Real"))
    db.add(_usuario("ana@stockarg.test", "Demo", "sesion-a"))
    db.commit()

    assert db.query(Usuario).count() == 2


def test_el_codigo_de_barras_no_se_repite(db):
    db.add(Producto(nombre="Gaseosa", codigo_barra="7790895000123"))
    db.commit()
    db.add(Producto(nombre="Otra", codigo_barra="7790895000123"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_varios_productos_pueden_no_tener_codigo(db):
    db.add(Producto(nombre="Suelto uno", codigo_barra=None))
    db.add(Producto(nombre="Suelto dos", codigo_barra=None))
    db.commit()

    assert db.query(Producto).count() == 2


def test_el_documento_del_cliente_no_se_repite(db):
    db.add(Cliente(nombre="Ana", documento="30111222"))
    db.commit()
    db.add(Cliente(nombre="Otra", documento="30111222"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_varios_clientes_pueden_no_tener_documento(db):
    db.add(Cliente(nombre="Mostrador uno"))
    db.add(Cliente(nombre="Mostrador dos"))
    db.commit()

    assert db.query(Cliente).count() == 2
