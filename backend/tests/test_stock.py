"""Movimientos de inventario, bajas y estado del stock (modulo D)."""

import pytest

from app.models import BajaProducto, MovimientoStock, Producto


def _producto(client, cabeceras, **extra):
    datos = {
        "nombre": "Alfajor triple",
        "precio_venta": "1200.00",
        "stock_actual": 40,
        "stock_minimo": 10,
        "stock_inicial": 100,
    }
    datos.update(extra)
    respuesta = client.post("/productos", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _mover(client, cabeceras, id_producto, tipo, cantidad, nota=None):
    cuerpo = {
        "id_producto": id_producto,
        "tipo": tipo,
        "cantidad": cantidad,
    }
    if nota is not None:
        cuerpo["nota"] = nota
    return client.post("/stock/movimientos", json=cuerpo, headers=cabeceras)


# --- como cada tipo afecta al stock (RF-D03) -----------------------------


@pytest.mark.parametrize(
    ("tipo", "cantidad", "esperado"),
    [
        ("entrada", 10, 50),
        ("devolucion", 5, 45),
        ("salida", 15, 25),
        ("ajuste", 33, 33),
    ],
)
def test_cada_tipo_mueve_el_stock_como_corresponde(
    client, sesiones, db, tipo, cantidad, esperado
):
    """El ajuste fija el valor contado; el resto suma o resta."""
    producto = _producto(client, sesiones["propietario"], stock_actual=40)

    respuesta = _mover(
        client, sesiones["propietario"], producto["id"], tipo, cantidad
    )

    assert respuesta.status_code == 201
    assert db.get(Producto, producto["id"]).stock_actual == esperado
    assert respuesta.json()["stock_resultante"] == esperado


def test_no_se_puede_sacar_mas_de_lo_que_hay(client, sesiones, db):
    producto = _producto(client, sesiones["propietario"], stock_actual=10)

    respuesta = _mover(
        client, sesiones["propietario"], producto["id"], "salida", 11
    )

    assert respuesta.status_code == 400
    assert "insuficiente" in respuesta.json()["detail"].lower()
    assert db.get(Producto, producto["id"]).stock_actual == 10


def test_un_movimiento_rechazado_no_deja_rastro(client, sesiones, db):
    """Ni el stock cambia ni queda una linea de historial a medias."""
    producto = _producto(client, sesiones["propietario"], stock_actual=10)

    _mover(client, sesiones["propietario"], producto["id"], "salida", 99)

    assert db.get(Producto, producto["id"]).stock_actual == 10
    assert db.query(MovimientoStock).count() == 0


def test_la_cantidad_tiene_que_ser_positiva(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    respuesta = _mover(
        client, sesiones["propietario"], producto["id"], "entrada", -5
    )

    assert respuesta.status_code == 422


def test_un_producto_inexistente_devuelve_404(client, sesiones):
    respuesta = _mover(client, sesiones["propietario"], 9999, "entrada", 5)

    assert respuesta.status_code == 404


# --- tipos que no se piden a mano ----------------------------------------


@pytest.mark.parametrize("tipo", ["venta", "baja"])
def test_no_se_puede_inventar_una_venta_ni_una_baja(client, sesiones, tipo):
    """Esos movimientos los genera el sistema por sus propios caminos.

    Admitirlos aca dejaria registrar una venta que nunca ocurrio, o
    descontar mercaderia sin que quede el registro de la baja.
    """
    producto = _producto(client, sesiones["propietario"])

    respuesta = _mover(client, sesiones["propietario"], producto["id"], tipo, 1)

    assert respuesta.status_code == 422


def test_un_tipo_inventado_se_rechaza(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    respuesta = _mover(
        client, sesiones["propietario"], producto["id"], "regalo", 1
    )

    assert respuesta.status_code == 422


# --- trazabilidad (RF-D05, RF-D08) ---------------------------------------


def test_el_movimiento_guarda_quien_y_cuando(client, sesiones, db):
    producto = _producto(client, sesiones["propietario"])

    _mover(client, sesiones["propietario"], producto["id"], "entrada", 5)

    movimiento = db.query(MovimientoStock).one()
    assert movimiento.id_usuario is not None
    assert movimiento.fecha_hora is not None


def test_el_historial_se_lee_sin_recalcular(client, sesiones, db):
    """Cada linea guarda el stock que quedo, no solo la diferencia."""
    producto = _producto(client, sesiones["propietario"], stock_actual=10)

    _mover(client, sesiones["propietario"], producto["id"], "entrada", 5)
    _mover(client, sesiones["propietario"], producto["id"], "salida", 3)

    resultantes = [
        m.stock_resultante
        for m in db.query(MovimientoStock).order_by(MovimientoStock.id).all()
    ]
    assert resultantes == [15, 12]


def test_la_nota_se_conserva(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    respuesta = _mover(
        client,
        sesiones["propietario"],
        producto["id"],
        "ajuste",
        7,
        nota="Recuento de fin de mes",
    )

    assert respuesta.json()["nota"] == "Recuento de fin de mes"


# --- bajas (RF-D06) ------------------------------------------------------


def test_una_baja_descuenta_y_queda_registrada(client, sesiones, db):
    producto = _producto(client, sesiones["propietario"], stock_actual=40)

    respuesta = client.post(
        "/stock/bajas",
        json={
            "id_producto": producto["id"],
            "cantidad": 6,
            "motivo": "vencido",
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 201
    assert db.get(Producto, producto["id"]).stock_actual == 34
    assert db.query(BajaProducto).count() == 1
    assert db.query(MovimientoStock).one().tipo.value == "baja"


def test_no_se_puede_dar_de_baja_mas_de_lo_que_hay(client, sesiones, db):
    producto = _producto(client, sesiones["propietario"], stock_actual=3)

    respuesta = client.post(
        "/stock/bajas",
        json={
            "id_producto": producto["id"],
            "cantidad": 4,
            "motivo": "danado",
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400
    assert db.query(BajaProducto).count() == 0
    assert db.get(Producto, producto["id"]).stock_actual == 3


def test_un_motivo_inventado_se_rechaza(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    respuesta = client.post(
        "/stock/bajas",
        json={
            "id_producto": producto["id"],
            "cantidad": 1,
            "motivo": "se lo comio el perro",
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 422


# --- historial filtrable (RF-D04) ----------------------------------------


def test_el_historial_se_filtra_por_producto(client, sesiones):
    uno = _producto(client, sesiones["propietario"], nombre="Uno")
    dos = _producto(client, sesiones["propietario"], nombre="Dos")
    _mover(client, sesiones["propietario"], uno["id"], "entrada", 1)
    _mover(client, sesiones["propietario"], dos["id"], "entrada", 1)

    cuerpo = client.get(
        f"/stock/movimientos?id_producto={uno['id']}",
        headers=sesiones["vendedor"],
    ).json()

    assert cuerpo["total"] == 1


def test_el_historial_se_filtra_por_tipo(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 5)
    _mover(client, sesiones["propietario"], producto["id"], "salida", 2)

    cuerpo = client.get(
        "/stock/movimientos?tipo=salida", headers=sesiones["vendedor"]
    ).json()

    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["tipo"] == "salida"


def test_el_historial_viene_del_mas_nuevo_al_mas_viejo(client, sesiones):
    producto = _producto(client, sesiones["propietario"], stock_actual=10)
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 1)
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 2)

    items = client.get(
        "/stock/movimientos", headers=sesiones["vendedor"]
    ).json()["items"]

    assert items[0]["cantidad"] == 2


def test_el_historial_se_pagina(client, sesiones):
    producto = _producto(client, sesiones["propietario"], stock_actual=100)
    for _ in range(4):
        _mover(client, sesiones["propietario"], producto["id"], "entrada", 1)

    cuerpo = client.get(
        "/stock/movimientos?limite=2", headers=sesiones["vendedor"]
    ).json()

    assert cuerpo["total"] == 4
    assert len(cuerpo["items"]) == 2


# --- resumen por estado (RF-D01, RF-D02) ---------------------------------


def test_el_resumen_cuenta_los_productos_por_estado(client, sesiones):
    """Mismos umbrales que la version de escritorio: 30 y 54 por ciento."""
    _producto(
        client,
        sesiones["propietario"],
        nombre="Bajo",
        stock_actual=20,
        stock_inicial=100,
    )
    _producto(
        client,
        sesiones["propietario"],
        nombre="Medio",
        stock_actual=40,
        stock_inicial=100,
    )
    _producto(
        client,
        sesiones["propietario"],
        nombre="Ok",
        stock_actual=90,
        stock_inicial=100,
    )

    cuerpo = client.get("/stock/resumen", headers=sesiones["vendedor"]).json()

    assert cuerpo["total"] == 3
    assert cuerpo["bajo"] == 1
    assert cuerpo["medio"] == 1
    assert cuerpo["ok"] == 1


def test_el_resumen_cuenta_los_que_quedaron_sin_stock(client, sesiones):
    producto = _producto(client, sesiones["propietario"], stock_actual=5)
    _mover(client, sesiones["propietario"], producto["id"], "salida", 5)

    cuerpo = client.get("/stock/resumen", headers=sesiones["vendedor"]).json()

    assert cuerpo["sin_stock"] == 1


def test_el_resumen_ignora_los_productos_dados_de_baja(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 1)
    client.delete(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    )

    cuerpo = client.get("/stock/resumen", headers=sesiones["vendedor"]).json()

    assert cuerpo["total"] == 0


# --- permisos (seccion 05) -----------------------------------------------


def test_el_vendedor_consulta_pero_no_mueve_stock(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    consulta = client.get("/stock/movimientos", headers=sesiones["vendedor"])
    movimiento = _mover(
        client, sesiones["vendedor"], producto["id"], "entrada", 5
    )
    baja = client.post(
        "/stock/bajas",
        json={
            "id_producto": producto["id"],
            "cantidad": 1,
            "motivo": "vencido",
        },
        headers=sesiones["vendedor"],
    )

    assert consulta.status_code == 200
    assert movimiento.status_code == 403
    assert baja.status_code == 403


def test_el_encargado_si_puede_mover_stock(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    respuesta = _mover(
        client, sesiones["encargado"], producto["id"], "entrada", 5
    )

    assert respuesta.status_code == 201


def test_sin_sesion_no_se_mueve_nada(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    respuesta = client.post(
        "/stock/movimientos",
        json={
            "id_producto": producto["id"],
            "tipo": "entrada",
            "cantidad": 5,
        },
    )

    assert respuesta.status_code == 401


# --- exportacion (RF-D09) ------------------------------------------------


def test_se_exportan_los_movimientos_a_csv(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 5)

    respuesta = client.get(
        "/stock/movimientos/exportar", headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]
    texto = respuesta.content.decode("utf-8")
    assert "Alfajor triple" in texto
    assert "entrada" in texto


def test_se_exportan_los_movimientos_a_pdf(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 5)

    respuesta = client.get(
        "/stock/movimientos/exportar?formato=pdf",
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF")


def test_la_exportacion_de_movimientos_respeta_el_filtro(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _mover(client, sesiones["propietario"], producto["id"], "entrada", 5)
    _mover(client, sesiones["propietario"], producto["id"], "salida", 2)

    texto = client.get(
        "/stock/movimientos/exportar?tipo=salida",
        headers=sesiones["propietario"],
    ).content.decode("utf-8")

    assert "salida" in texto
    assert "entrada" not in texto


def test_el_vendedor_no_puede_exportar_movimientos(client, sesiones):
    respuesta = client.get(
        "/stock/movimientos/exportar", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 403


def test_exportar_movimientos_sin_datos_no_falla(client, sesiones):
    respuesta = client.get(
        "/stock/movimientos/exportar?formato=pdf",
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF")
