from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Categoria,
    Cliente,
    MedioPago,
    Producto,
    Rol,
    Usuario,
    Venta,
    VentaItem,
)


def _usuario(db, rol=Rol.VENDEDOR):
    u = Usuario(email=f"{rol.value}@stockarg.test", nombre="Prueba", rol=rol)
    db.add(u)
    db.commit()
    return u


def _producto(db, **kwargs):
    datos = {
        "nombre": "Alfajor triple",
        "precio_venta": Decimal("1200.00"),
        "precio_costo": Decimal("800.00"),
        "stock_actual": 40,
        "stock_inicial": 100,
        "stock_minimo": 10,
    }
    datos.update(kwargs)
    p = Producto(**datos)
    db.add(p)
    db.commit()
    return p


def _medio(db, nombre="Efectivo", es_efectivo=True):
    m = MedioPago(nombre=nombre, es_efectivo=es_efectivo)
    db.add(m)
    db.commit()
    return m


def _linea(producto, cantidad, precio):
    return VentaItem(
        id_producto=producto.id,
        nombre_producto=producto.nombre,
        cantidad=cantidad,
        precio_unitario=Decimal(precio),
        subtotal=Decimal(precio) * cantidad,
    )


# --- estado de stock (RF-D01) -------------------------------------------


@pytest.mark.parametrize(
    ("actual", "inicial", "porcentaje", "estado"),
    [
        (100, 100, 100, "ok"),
        (55, 100, 55, "ok"),
        (54, 100, 54, "medio"),
        (31, 100, 31, "medio"),
        (30, 100, 30, "bajo"),
        (0, 100, 0, "bajo"),
    ],
)
def test_estado_de_stock_respeta_los_umbrales(
    db, actual, inicial, porcentaje, estado
):
    p = _producto(db, stock_actual=actual, stock_inicial=inicial)

    assert p.porcentaje_stock == porcentaje
    assert p.estado_stock == estado


def test_sin_stock_inicial_no_se_reporta_como_bajo(db):
    p = _producto(db, stock_actual=5, stock_inicial=0)

    assert p.porcentaje_stock == 100
    assert p.estado_stock == "ok"


def test_stock_por_encima_del_inicial_se_acota_a_cien(db):
    p = _producto(db, stock_actual=250, stock_inicial=100)

    assert p.porcentaje_stock == 100


def test_bajo_minimo_marca_reposicion(db):
    assert _producto(db, stock_actual=10, stock_minimo=10).bajo_minimo
    assert not _producto(db, stock_actual=11, stock_minimo=10).bajo_minimo


def test_margen_sobre_el_costo(db):
    p = _producto(
        db, precio_venta=Decimal("1500.00"), precio_costo=Decimal("1000.00")
    )

    assert p.margen == Decimal("50.00")


def test_sin_costo_no_hay_margen(db):
    assert _producto(db, precio_costo=Decimal("0.00")).margen is None


# --- integridad declarada en la base ------------------------------------


def test_la_base_rechaza_stock_negativo(db):
    db.add(Producto(nombre="Roto", stock_actual=-1))

    with pytest.raises(IntegrityError):
        db.commit()


def test_la_base_rechaza_precio_negativo(db):
    db.add(Producto(nombre="Roto", precio_venta=Decimal("-1.00")))

    with pytest.raises(IntegrityError):
        db.commit()


def test_la_base_rechaza_cantidad_cero_en_una_linea(db):
    usuario = _usuario(db)
    producto = _producto(db)
    medio = _medio(db)

    venta = Venta(id_usuario=usuario.id, id_medio_pago=medio.id)
    venta.items.append(_linea(producto, 0, "1200.00"))
    db.add(venta)

    with pytest.raises(IntegrityError):
        db.commit()


# --- venta con varios productos (RF-E01) --------------------------------


def test_una_venta_lleva_varios_productos(db):
    usuario = _usuario(db)
    medio = _medio(db)
    cliente = Cliente(nombre="Ana", apellido="Gomez", documento="30111222")
    db.add(cliente)
    db.commit()

    gaseosa = _producto(db, nombre="Gaseosa 500")
    alfajor = _producto(db, nombre="Alfajor")

    venta = Venta(
        id_usuario=usuario.id,
        id_medio_pago=medio.id,
        id_cliente=cliente.id,
        total=Decimal("3300.00"),
        recibido=Decimal("5000.00"),
    )
    venta.items.append(_linea(gaseosa, 1, "900.00"))
    venta.items.append(_linea(alfajor, 2, "1200.00"))
    db.add(venta)
    db.commit()

    guardada = db.get(Venta, venta.id)
    assert len(guardada.items) == 2
    assert guardada.cantidad_articulos == 3
    assert guardada.vuelto == Decimal("1700.00")
    assert guardada.id_cliente == cliente.id


def test_sin_efectivo_no_hay_vuelto(db):
    usuario = _usuario(db)
    medio = _medio(db, "Transferencia", es_efectivo=False)

    venta = Venta(
        id_usuario=usuario.id,
        id_medio_pago=medio.id,
        total=Decimal("900.00"),
    )
    db.add(venta)
    db.commit()

    assert venta.vuelto is None


def test_borrar_una_venta_arrastra_sus_lineas(db):
    usuario = _usuario(db)
    medio = _medio(db)
    producto = _producto(db)

    venta = Venta(id_usuario=usuario.id, id_medio_pago=medio.id)
    venta.items.append(_linea(producto, 1, "1200.00"))
    db.add(venta)
    db.commit()

    db.delete(venta)
    db.commit()

    assert db.query(VentaItem).count() == 0


def test_la_linea_conserva_el_nombre_vendido(db):
    """Renombrar el producto no reescribe los tickets ya emitidos."""
    usuario = _usuario(db)
    medio = _medio(db)
    producto = _producto(db, nombre="Alfajor triple")

    venta = Venta(id_usuario=usuario.id, id_medio_pago=medio.id)
    venta.items.append(_linea(producto, 1, "1200.00"))
    db.add(venta)
    db.commit()

    producto.nombre = "Alfajor triple chocolate"
    db.commit()

    assert venta.items[0].nombre_producto == "Alfajor triple"


# --- roles (seccion 05 de la especificacion) -----------------------------


@pytest.mark.parametrize(
    ("rol", "administra", "gestiona"),
    [
        (Rol.PROPIETARIO, True, True),
        (Rol.ENCARGADO, False, True),
        (Rol.VENDEDOR, False, False),
    ],
)
def test_alcance_de_cada_rol(db, rol, administra, gestiona):
    usuario = _usuario(db, rol)

    assert usuario.puede_administrar is administra
    assert usuario.puede_gestionar is gestiona


def test_el_bloqueo_por_intentos_se_guarda(db):
    usuario = _usuario(db)
    usuario.intentos_fallidos = 5
    usuario.bloqueado_hasta = datetime.now(UTC) + timedelta(minutes=10)
    db.commit()

    guardado = db.get(Usuario, usuario.id)
    assert guardado.intentos_fallidos == 5
    assert guardado.bloqueado_hasta is not None


def test_una_cuenta_de_google_no_necesita_contrasena(db):
    usuario = Usuario(
        email="google@stockarg.test",
        nombre="Con Google",
        google_id="1234567890",
        password_hash=None,
        verificado=True,
    )
    db.add(usuario)
    db.commit()

    assert db.get(Usuario, usuario.id).password_hash is None


def test_la_categoria_se_asocia_al_producto(db):
    categoria = Categoria(nombre="Golosinas")
    db.add(categoria)
    db.commit()
    producto = _producto(db, id_categoria=categoria.id)

    assert db.get(Producto, producto.id).categoria.nombre == "Golosinas"


def test_no_se_puede_cobrar_menos_de_lo_que_costo(db):
    """Una venta no puede guardarse con vuelto negativo."""
    usuario = _usuario(db)
    medio = _medio(db)

    db.add(
        Venta(
            id_usuario=usuario.id,
            id_medio_pago=medio.id,
            total=Decimal("1200.00"),
            recibido=Decimal("1000.00"),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_pagar_justo_es_valido(db):
    usuario = _usuario(db)
    medio = _medio(db)

    venta = Venta(
        id_usuario=usuario.id,
        id_medio_pago=medio.id,
        total=Decimal("1200.00"),
        recibido=Decimal("1200.00"),
    )
    db.add(venta)
    db.commit()

    assert venta.vuelto == Decimal("0.00")
