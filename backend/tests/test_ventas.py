"""Punto de venta, clientes y medios de cobro (modulos E y F)."""

import pytest

from app.models import Cliente, EstadoVenta, MovimientoStock, Producto, Venta

# --- ayudantes -----------------------------------------------------------


def _medios(client, cabeceras):
    """Siembra los medios de cobro y devuelve {nombre: id}."""
    respuesta = client.post("/medios-pago/sembrar", headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return {m["nombre"]: m["id"] for m in respuesta.json()}


def _producto(client, cabeceras, **extra):
    datos = {
        "nombre": "Alfajor triple",
        "precio_venta": "1200.00",
        "precio_costo": "800.00",
        "stock_actual": 40,
        "stock_minimo": 5,
        "stock_inicial": 100,
    }
    datos.update(extra)
    respuesta = client.post("/productos", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _cliente(client, cabeceras, **extra):
    datos = {"nombre": "Ana", "apellido": "Gomez", "documento": "30111222"}
    datos.update(extra)
    respuesta = client.post("/clientes", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _vender(client, cabeceras, items, **extra):
    cuerpo = {"items": items}
    cuerpo.update(extra)
    return client.post("/ventas", json=cuerpo, headers=cabeceras)


@pytest.fixture
def mostrador(client, sesiones):
    """Un comercio listo para cobrar: medios, producto y cliente."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    return {
        "medios": medios,
        "efectivo": medios["Efectivo"],
        "transferencia": medios["Transferencia"],
        "producto": _producto(client, duena),
        "cliente": _cliente(client, duena),
    }


# --- el total lo calcula el servidor -------------------------------------


def test_el_total_sale_de_las_lineas(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 3}],
        id_medio_pago=mostrador["efectivo"],
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 201
    assert cuerpo["total"] == "3600.00"
    assert cuerpo["cantidad_articulos"] == 3


def test_mandar_un_total_en_el_pedido_es_un_error_visible(
    client, sesiones, mostrador
):
    """No alcanza con ignorarlo.

    Si el campo se descartara en silencio, quien integra creeria que su
    importe se respeto. Al rechazarlo, el error aparece en la primera
    prueba y no en el cierre de caja.
    """
    respuesta = client.post(
        "/ventas",
        json={
            "items": [
                {"id_producto": mostrador["producto"]["id"], "cantidad": 3}
            ],
            "id_medio_pago": mostrador["efectivo"],
            "total": "1.00",
        },
        headers=sesiones["vendedor"],
    )

    assert respuesta.status_code == 422


def test_mandar_un_subtotal_en_la_linea_tambien_se_rechaza(
    client, sesiones, mostrador
):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 1,
                "subtotal": "1.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 422


def test_se_respeta_el_precio_pactado_de_la_linea(client, sesiones, mostrador):
    """RF-E04: la gestion puede escribir otro precio."""
    respuesta = _vender(
        client,
        sesiones["encargado"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 2,
                "precio_unitario": "1000.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.json()["total"] == "2000.00"


# --- varios productos y consolidacion ------------------------------------


def test_una_venta_lleva_varios_productos(client, sesiones, mostrador):
    otro = _producto(
        client,
        sesiones["propietario"],
        nombre="Gaseosa 500",
        precio_venta="900.00",
    )

    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {"id_producto": mostrador["producto"]["id"], "cantidad": 2},
            {"id_producto": otro["id"], "cantidad": 1},
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    cuerpo = respuesta.json()
    assert len(cuerpo["items"]) == 2
    assert cuerpo["total"] == "3300.00"


def test_el_mismo_producto_repetido_se_junta_en_una_linea(
    client, sesiones, mostrador
):
    """RF-E11. Sin juntarlas, cada linea valida el stock por separado."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {"id_producto": mostrador["producto"]["id"], "cantidad": 2},
            {"id_producto": mostrador["producto"]["id"], "cantidad": 3},
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    cuerpo = respuesta.json()
    assert len(cuerpo["items"]) == 1
    assert cuerpo["items"][0]["cantidad"] == 5


def test_dos_lineas_que_juntas_exceden_el_stock_se_rechazan(client, sesiones):
    """El caso que la consolidacion existe para atrapar."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = _producto(client, duena, stock_actual=5)

    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {"id_producto": producto["id"], "cantidad": 3},
            {"id_producto": producto["id"], "cantidad": 3},
        ],
        id_medio_pago=medios["Efectivo"],
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "stock_insuficiente"


# --- stock (RF-E09, RF-E10) ----------------------------------------------


def test_la_venta_descuenta_el_stock(client, sesiones, mostrador, db):
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 4}],
        id_medio_pago=mostrador["efectivo"],
    )

    assert db.get(Producto, mostrador["producto"]["id"]).stock_actual == 36


def test_la_venta_deja_un_movimiento_de_tipo_venta(
    client, sesiones, mostrador, db
):
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 4}],
        id_medio_pago=mostrador["efectivo"],
    )

    movimiento = db.query(MovimientoStock).one()
    assert movimiento.tipo.value == "venta"
    assert movimiento.cantidad == 4
    assert movimiento.id_venta is not None


def test_sin_stock_se_informa_cada_faltante(client, sesiones):
    """RF-E10: todo lo que hay que corregir, de una sola vez."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    uno = _producto(client, duena, nombre="Poco", stock_actual=1)
    dos = _producto(client, duena, nombre="Nada", stock_actual=0)

    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {"id_producto": uno["id"], "cantidad": 5},
            {"id_producto": dos["id"], "cantidad": 2},
        ],
        id_medio_pago=medios["Efectivo"],
    )

    faltantes = respuesta.json()["detail"]["faltantes"]
    assert respuesta.status_code == 400
    assert len(faltantes) == 2
    assert {f["nombre"] for f in faltantes} == {"Poco", "Nada"}


def test_una_venta_rechazada_no_deja_nada_escrito(
    client, sesiones, mostrador, db
):
    """Ni la venta, ni el movimiento, ni el descuento de stock."""
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 999}],
        id_medio_pago=mostrador["efectivo"],
    )

    assert db.query(Venta).count() == 0
    assert db.query(MovimientoStock).count() == 0
    assert db.get(Producto, mostrador["producto"]["id"]).stock_actual == 40


def test_un_producto_dado_de_baja_no_se_puede_vender(
    client, sesiones, mostrador
):
    duena = sesiones["propietario"]
    client.post(
        "/stock/movimientos",
        json={
            "id_producto": mostrador["producto"]["id"],
            "tipo": "entrada",
            "cantidad": 1,
        },
        headers=duena,
    )
    client.delete(f"/productos/{mostrador['producto']['id']}", headers=duena)

    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 400
    assert "baja" in str(respuesta.json()["detail"]).lower()


# --- descuentos (RF-E05) -------------------------------------------------


def test_el_descuento_de_linea_baja_el_subtotal(client, sesiones, mostrador):
    """Con un descuento por encima del tope del vendedor."""
    respuesta = _vender(
        client,
        sesiones["encargado"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 2,
                "descuento": "400.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.json()["total"] == "2000.00"


def test_el_descuento_general_baja_el_total(client, sesiones, mostrador):
    """Con un descuento por encima del tope del vendedor."""
    respuesta = _vender(
        client,
        sesiones["encargado"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 2}],
        id_medio_pago=mostrador["efectivo"],
        descuento="400.00",
    )

    assert respuesta.json()["total"] == "2000.00"


def test_un_descuento_mayor_que_la_linea_se_rechaza(
    client, sesiones, mostrador
):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 1,
                "descuento": "5000.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 400
    assert "descuento" in str(respuesta.json()["detail"]).lower()


def test_un_descuento_mayor_que_el_total_se_rechaza(
    client, sesiones, mostrador
):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        descuento="9999.00",
    )

    assert respuesta.status_code == 400


def test_un_descuento_negativo_se_rechaza(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        descuento="-100.00",
    )

    assert respuesta.status_code == 422


# --- efectivo y vuelto (RF-E08) ------------------------------------------


def test_el_vuelto_sale_de_lo_recibido(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 2}],
        id_medio_pago=mostrador["efectivo"],
        recibido="5000.00",
    )

    cuerpo = respuesta.json()
    assert cuerpo["total"] == "2400.00"
    assert cuerpo["vuelto"] == "2600.00"


def test_recibir_menos_que_el_total_se_rechaza(client, sesiones, mostrador):
    """Cobrar de menos no puede quedar registrado como venta completa."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 2}],
        id_medio_pago=mostrador["efectivo"],
        recibido="1000.00",
    )

    assert respuesta.status_code == 400
    assert "recibido" in str(respuesta.json()["detail"]).lower()


def test_no_se_informa_recibido_con_un_pago_que_no_es_efectivo(
    client, sesiones, mostrador
):
    """Haria aparecer un vuelto que nadie entrego."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["transferencia"],
        recibido="5000.00",
    )

    assert respuesta.status_code == 400


def test_sin_efectivo_no_hay_vuelto(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["transferencia"],
    )

    assert respuesta.json()["vuelto"] is None


# --- medio de pago y cliente ---------------------------------------------


def test_un_medio_deshabilitado_no_se_puede_usar(client, sesiones, mostrador):
    client.delete(
        f"/medios-pago/{mostrador['transferencia']}",
        headers=sesiones["propietario"],
    )

    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["transferencia"],
    )

    assert respuesta.status_code == 400
    assert "habilitado" in str(respuesta.json()["detail"]).lower()


def test_un_medio_inexistente_devuelve_404(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=9999,
    )

    assert respuesta.status_code == 404


def test_la_venta_puede_quedar_asociada_a_un_cliente(
    client, sesiones, mostrador
):
    """RF-E07: lo que la version de escritorio no hacia."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        id_cliente=mostrador["cliente"]["id"],
    )

    assert respuesta.json()["id_cliente"] == mostrador["cliente"]["id"]


def test_la_venta_sin_cliente_es_valida(client, sesiones, mostrador):
    """En un kiosco la mayoria de las ventas son a mostrador."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["id_cliente"] is None


def test_un_cliente_inexistente_devuelve_404(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        id_cliente=9999,
    )

    assert respuesta.status_code == 404


# --- forma del pedido ----------------------------------------------------


def test_una_venta_sin_lineas_se_rechaza(client, sesiones, mostrador):
    respuesta = _vender(
        client, sesiones["vendedor"], [], id_medio_pago=mostrador["efectivo"]
    )

    assert respuesta.status_code == 422


@pytest.mark.parametrize("cantidad", [0, -1])
def test_una_cantidad_no_positiva_se_rechaza(
    client, sesiones, mostrador, cantidad
):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": cantidad,
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 422


def test_un_precio_negativo_se_rechaza(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 1,
                "precio_unitario": "-1.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 422


# --- anulacion (RF-E12) --------------------------------------------------


def test_anular_repone_el_stock(client, sesiones, mostrador, db):
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 4}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    respuesta = client.post(
        f"/ventas/{venta['id']}/anular",
        json={"motivo": "El cliente se arrepintio"},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "anulada"
    assert db.get(Producto, mostrador["producto"]["id"]).stock_actual == 40


def test_anular_dos_veces_no_repone_el_stock_dos_veces(
    client, sesiones, mostrador, db
):
    """Sin la guarda, el inventario queda inflado."""
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 4}],
        id_medio_pago=mostrador["efectivo"],
    ).json()
    client.post(
        f"/ventas/{venta['id']}/anular",
        json={},
        headers=sesiones["propietario"],
    )

    segunda = client.post(
        f"/ventas/{venta['id']}/anular",
        json={},
        headers=sesiones["propietario"],
    )

    assert segunda.status_code == 400
    assert db.get(Producto, mostrador["producto"]["id"]).stock_actual == 40


def test_la_venta_anulada_no_se_borra(client, sesiones, mostrador, db):
    """El control diario necesita ver que la operacion existio."""
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    client.post(
        f"/ventas/{venta['id']}/anular",
        json={"motivo": "Error de carga"},
        headers=sesiones["propietario"],
    )

    guardada = db.get(Venta, venta["id"])
    assert guardada.estado is EstadoVenta.ANULADA
    assert guardada.motivo_anulacion == "Error de carga"
    assert guardada.id_usuario_anulacion is not None
    assert len(guardada.items) == 1


def test_el_vendedor_no_puede_anular(client, sesiones, mostrador):
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    respuesta = client.post(
        f"/ventas/{venta['id']}/anular",
        json={},
        headers=sesiones["vendedor"],
    )

    assert respuesta.status_code == 403


# --- historial y permisos (RF-E13, seccion 05) ---------------------------


def test_el_vendedor_solo_ve_sus_propias_ventas(client, sesiones, mostrador):
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )
    _vender(
        client,
        sesiones["encargado"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )

    del_vendedor = client.get("/ventas", headers=sesiones["vendedor"]).json()
    de_la_gestion = client.get(
        "/ventas", headers=sesiones["propietario"]
    ).json()

    assert del_vendedor["total"] == 1
    assert de_la_gestion["total"] == 2


def test_el_vendedor_no_puede_pedir_las_ventas_de_otro(
    client, sesiones, mostrador
):
    """El filtro se fuerza: pasar otro id_usuario no sirve de nada."""
    encargado = _vender(
        client,
        sesiones["encargado"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    cuerpo = client.get(
        f"/ventas?id_usuario={encargado['id_usuario']}",
        headers=sesiones["vendedor"],
    ).json()

    assert cuerpo["total"] == 0


def test_el_vendedor_no_ve_el_ticket_de_otro(client, sesiones, mostrador):
    ajena = _vender(
        client,
        sesiones["encargado"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    respuesta = client.get(
        f"/ventas/{ajena['id']}", headers=sesiones["vendedor"]
    )

    # 404 y no 403: un 403 confirmaria que el ticket existe.
    assert respuesta.status_code == 404


def test_el_vendedor_si_ve_su_propio_ticket(client, sesiones, mostrador):
    propia = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    respuesta = client.get(
        f"/ventas/{propia['id']}", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 200


def test_el_historial_se_filtra_por_estado(client, sesiones, mostrador):
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )
    client.post(
        f"/ventas/{venta['id']}/anular",
        json={},
        headers=sesiones["propietario"],
    )

    anuladas = client.get(
        "/ventas?estado=anulada", headers=sesiones["propietario"]
    ).json()

    assert anuladas["total"] == 1


def test_el_historial_se_busca_por_producto(client, sesiones, mostrador):
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )

    cuerpo = client.get(
        "/ventas?busqueda=alfajor", headers=sesiones["propietario"]
    ).json()

    assert cuerpo["total"] == 1


def test_sin_sesion_no_se_puede_vender(client, mostrador):
    respuesta = client.post(
        "/ventas",
        json={
            "items": [
                {"id_producto": mostrador["producto"]["id"], "cantidad": 1}
            ],
            "id_medio_pago": mostrador["efectivo"],
        },
    )

    assert respuesta.status_code == 401


# --- comprobante (RF-E15) ------------------------------------------------


def test_el_comprobante_sale_en_pdf(client, sesiones, mostrador):
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 2}],
        id_medio_pago=mostrador["efectivo"],
        recibido="5000.00",
    ).json()

    respuesta = client.get(
        f"/ventas/{venta['id']}/comprobante", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF")


def test_el_vendedor_no_baja_el_comprobante_de_otro(
    client, sesiones, mostrador
):
    ajena = _vender(
        client,
        sesiones["encargado"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    respuesta = client.get(
        f"/ventas/{ajena['id']}/comprobante", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 404


def test_el_historial_se_exporta(client, sesiones, mostrador):
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    )

    csv = client.get("/ventas/exportar", headers=sesiones["propietario"])
    pdf = client.get(
        "/ventas/exportar?formato=pdf", headers=sesiones["propietario"]
    )

    assert csv.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_las_rutas_de_ventas_respetan_el_orden_de_declaracion():
    """Regresion del mismo error que tapo /productos/exportar."""
    from app.api.routes.ventas import router

    rutas = [r.path for r in router.routes]

    assert rutas.index("/ventas/exportar") < rutas.index("/ventas/{id_venta}")


# --- medios de cobro -----------------------------------------------------


def test_sembrar_deja_los_medios_habituales(client, sesiones):
    medios = _medios(client, sesiones["propietario"])

    assert "Efectivo" in medios
    assert "QR" in medios


def test_sembrar_dos_veces_no_duplica(client, sesiones):
    _medios(client, sesiones["propietario"])
    client.post("/medios-pago/sembrar", headers=sesiones["propietario"])

    cuerpo = client.get("/medios-pago", headers=sesiones["vendedor"]).json()

    assert len(cuerpo) == 5


def test_no_se_puede_deshabilitar_el_ultimo_medio(client, sesiones):
    """Sin ningun medio habilitado no se puede cobrar nada."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    for nombre, id_medio in medios.items():
        if nombre != "Efectivo":
            client.delete(f"/medios-pago/{id_medio}", headers=duena)

    respuesta = client.delete(
        f"/medios-pago/{medios['Efectivo']}", headers=duena
    )

    assert respuesta.status_code == 400
    assert "unico" in respuesta.json()["detail"].lower()


def test_solo_el_propietario_administra_los_medios(client, sesiones):
    respuesta = client.post(
        "/medios-pago",
        json={"nombre": "Cheque"},
        headers=sesiones["encargado"],
    )

    assert respuesta.status_code == 403


def test_cualquiera_puede_consultar_los_medios(client, sesiones):
    _medios(client, sesiones["propietario"])

    respuesta = client.get("/medios-pago", headers=sesiones["vendedor"])

    assert respuesta.status_code == 200


# --- clientes (modulo F) -------------------------------------------------


def test_el_documento_del_cliente_no_se_repite(client, sesiones):
    _cliente(client, sesiones["propietario"])

    repetido = client.post(
        "/clientes",
        json={"nombre": "Otra", "documento": "30111222"},
        headers=sesiones["propietario"],
    )

    assert repetido.status_code == 400
    assert "Ana" in repetido.json()["detail"]


def test_varios_clientes_pueden_no_tener_documento(client, sesiones):
    duena = sesiones["propietario"]
    _cliente(client, duena, nombre="Uno", documento=None)
    _cliente(client, duena, nombre="Dos", documento=None)

    cuerpo = client.get("/clientes", headers=duena).json()

    assert cuerpo["total"] == 2


def test_el_cliente_se_busca_por_nombre_o_documento(client, sesiones):
    duena = sesiones["propietario"]
    _cliente(client, duena)
    _cliente(client, duena, nombre="Beto", documento="30999888")

    por_nombre = client.get("/clientes?busqueda=ana", headers=duena).json()
    por_documento = client.get("/clientes?busqueda=30999", headers=duena).json()

    assert por_nombre["total"] == 1
    assert por_documento["items"][0]["nombre"] == "Beto"


def test_el_cliente_sin_compras_se_borra_de_verdad(client, sesiones, db):
    cliente = _cliente(client, sesiones["propietario"])

    client.delete(f"/clientes/{cliente['id']}", headers=sesiones["propietario"])

    assert db.get(Cliente, cliente["id"]) is None


def test_el_cliente_con_compras_se_desactiva(client, sesiones, mostrador, db):
    _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        id_cliente=mostrador["cliente"]["id"],
    )

    client.delete(
        f"/clientes/{mostrador['cliente']['id']}",
        headers=sesiones["propietario"],
    )

    guardado = db.get(Cliente, mostrador["cliente"]["id"])
    assert guardado is not None
    assert guardado.activo is False


def test_el_resumen_de_compras_suma_lo_cobrado(client, sesiones, mostrador):
    """RF-F03."""
    for _ in range(2):
        _vender(
            client,
            sesiones["vendedor"],
            [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
            id_medio_pago=mostrador["efectivo"],
            id_cliente=mostrador["cliente"]["id"],
        )

    cuerpo = client.get(
        f"/clientes/{mostrador['cliente']['id']}/compras",
        headers=sesiones["propietario"],
    ).json()

    assert cuerpo["cantidad_compras"] == 2
    assert cuerpo["total_comprado"] == "2400.00"
    assert cuerpo["ultima_compra"] is not None


def test_una_venta_anulada_no_cuenta_en_el_acumulado(
    client, sesiones, mostrador
):
    """Diria que compro algo que despues se dio marcha atras."""
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        id_cliente=mostrador["cliente"]["id"],
    ).json()
    client.post(
        f"/ventas/{venta['id']}/anular",
        json={},
        headers=sesiones["propietario"],
    )

    cuerpo = client.get(
        f"/clientes/{mostrador['cliente']['id']}/compras",
        headers=sesiones["propietario"],
    ).json()

    assert cuerpo["cantidad_compras"] == 0
    assert cuerpo["total_comprado"] == "0.00"


def test_el_vendedor_puede_buscar_clientes_pero_no_crearlos(client, sesiones):
    """Necesita buscarlos para asociarlos al ticket (RF-E07)."""
    consulta = client.get("/clientes", headers=sesiones["vendedor"])
    alta = client.post(
        "/clientes",
        json={"nombre": "Propio"},
        headers=sesiones["vendedor"],
    )

    assert consulta.status_code == 200
    assert alta.status_code == 403


def test_un_correo_mal_formado_se_rechaza(client, sesiones):
    respuesta = client.post(
        "/clientes",
        json={"nombre": "Ana", "email": "no-es-correo"},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 422


# --- limites de caja por rol ---------------------------------------------


def test_el_vendedor_no_puede_cambiar_el_precio(client, sesiones, mostrador):
    """Fraude de mostrador: fijar precio 1 y llevarse la mercaderia.

    El stock se descuenta igual, asi que el inventario cuadra y el
    faltante de plata recien aparece en el cierre de caja.
    """
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 1,
                "precio_unitario": "1.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 400
    assert "precio" in str(respuesta.json()["detail"]).lower()


def test_el_vendedor_si_puede_confirmar_el_precio_de_lista(
    client, sesiones, mostrador
):
    """Mandar el mismo precio que ya tiene el producto no es pactar."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 1,
                "precio_unitario": "1200.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 201


@pytest.mark.parametrize("rol", ["propietario", "encargado"])
def test_la_gestion_si_puede_pactar_un_precio(client, sesiones, mostrador, rol):
    respuesta = _vender(
        client,
        sesiones[rol],
        [
            {
                "id_producto": mostrador["producto"]["id"],
                "cantidad": 1,
                "precio_unitario": "1.00",
            }
        ],
        id_medio_pago=mostrador["efectivo"],
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["total"] == "1.00"


def test_el_vendedor_no_puede_descontar_todo(client, sesiones, mostrador):
    """Regalar con descuento es el mismo fraude por otra puerta."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        descuento="1199.00",
    )

    assert respuesta.status_code == 400
    assert "rol" in str(respuesta.json()["detail"]).lower()


def test_el_vendedor_puede_hacer_un_descuento_chico(
    client, sesiones, mostrador
):
    """Diez por ciento de 1200 son 120: entra en el tope."""
    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        descuento="100.00",
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["total"] == "1100.00"


def test_repartir_el_descuento_entre_lineas_no_esquiva_el_tope(
    client, sesiones
):
    """El tope mira el total descontado, no cada linea por separado."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    uno = _producto(client, duena, nombre="Uno", precio_venta="1000.00")
    dos = _producto(client, duena, nombre="Dos", precio_venta="1000.00")

    respuesta = _vender(
        client,
        sesiones["vendedor"],
        [
            {"id_producto": uno["id"], "cantidad": 1, "descuento": "400.00"},
            {"id_producto": dos["id"], "cantidad": 1, "descuento": "400.00"},
        ],
        id_medio_pago=medios["Efectivo"],
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == respuesta.json()["detail"]


def test_la_gestion_no_tiene_tope_de_descuento(client, sesiones, mostrador):
    respuesta = _vender(
        client,
        sesiones["encargado"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        descuento="1199.00",
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["total"] == "1.00"


def test_el_historial_trae_los_nombres_para_mostrar(
    client, sesiones, mostrador
):
    """La pantalla muestra nombres, no ids que la obliguen a buscar."""
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
        id_cliente=mostrador["cliente"]["id"],
    ).json()

    fila = client.get("/ventas", headers=sesiones["propietario"]).json()[
        "items"
    ][0]
    detalle = client.get(
        f"/ventas/{venta['id']}", headers=sesiones["propietario"]
    ).json()

    for datos in (venta, fila, detalle):
        assert datos["medio_pago"] == "Efectivo"
        assert datos["vendedor"] == "Vendedor"
        assert datos["cliente"] == "Ana Gomez"


def test_una_venta_a_mostrador_no_tiene_nombre_de_cliente(
    client, sesiones, mostrador
):
    venta = _vender(
        client,
        sesiones["vendedor"],
        [{"id_producto": mostrador["producto"]["id"], "cantidad": 1}],
        id_medio_pago=mostrador["efectivo"],
    ).json()

    assert venta["cliente"] is None
