"""Propiedades calculadas sobre objetos que todavia no se guardaron.

Los valores por defecto de una columna los aplica la base en el INSERT.
Un objeto recien construido tiene None en toda columna que no se haya
pasado a mano, y las propiedades calculadas se leen antes de guardar:
la vista previa de una importacion CSV (RF-C10) muestra el resultado sin
escribir una sola fila.

Estas pruebas existen porque la primera version de estas propiedades
fallaba con TypeError en ese estado, y ninguna prueba lo veia: todas
guardaban el objeto antes de leerlo.
"""

from decimal import Decimal

from app.models import Producto, Venta


def test_el_porcentaje_de_stock_no_falla_sin_guardar():
    assert Producto(nombre="Sin guardar").porcentaje_stock == 0


def test_el_estado_de_stock_no_falla_sin_guardar():
    assert Producto(nombre="Sin guardar").estado_stock == "bajo"


def test_el_margen_no_falla_sin_guardar():
    assert Producto(nombre="Sin guardar").margen is None


def test_bajo_minimo_no_falla_sin_guardar():
    assert Producto(nombre="Sin guardar").bajo_minimo is True


def test_el_estado_se_calcula_con_lo_que_ya_tiene_cargado():
    """Una fila de un CSV previsualizada, antes de confirmar la carga."""
    candidato = Producto(nombre="Alfajor", stock_actual=20, stock_inicial=100)

    assert candidato.porcentaje_stock == 20
    assert candidato.estado_stock == "bajo"


def test_el_margen_se_calcula_sin_guardar():
    candidato = Producto(
        nombre="Alfajor",
        precio_venta=Decimal("1500.00"),
        precio_costo=Decimal("1000.00"),
    )

    assert candidato.margen == Decimal("50.00")


def test_el_vuelto_no_falla_sin_total_cargado():
    venta = Venta(id_usuario=1, id_medio_pago=1, recibido=Decimal("5000.00"))

    assert venta.vuelto == Decimal("5000.00")


def test_una_venta_sin_lineas_no_tiene_articulos():
    assert Venta(id_usuario=1, id_medio_pago=1).cantidad_articulos == 0
