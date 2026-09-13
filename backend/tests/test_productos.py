"""ABM de productos y categorias, y control de stock (modulos C y D)."""

import pytest

from app.models import MovimientoStock, Producto

CODIGO = "7790895000123"


def _producto(client, cabeceras, **extra):
    """Alta de producto por la API; devuelve el cuerpo de la respuesta."""
    datos = {
        "nombre": "Alfajor triple",
        "precio_venta": "1200.00",
        "precio_costo": "800.00",
        "stock_actual": 40,
        "stock_minimo": 10,
        "stock_inicial": 100,
    }
    datos.update(extra)
    respuesta = client.post("/productos", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _categoria(client, cabeceras, nombre="Golosinas"):
    respuesta = client.post(
        "/categorias", json={"nombre": nombre}, headers=cabeceras
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _movimiento(client, cabeceras, id_producto, tipo="entrada", cantidad=5):
    return client.post(
        "/stock/movimientos",
        json={
            "id_producto": id_producto,
            "tipo": tipo,
            "cantidad": cantidad,
        },
        headers=cabeceras,
    )


# --- permisos por rol (seccion 05) ---------------------------------------


def test_el_vendedor_puede_consultar_productos(client, sesiones):
    _producto(client, sesiones["propietario"])

    respuesta = client.get("/productos", headers=sesiones["vendedor"])

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1


@pytest.mark.parametrize("rol", ["propietario", "encargado"])
def test_la_gestion_puede_dar_de_alta(client, sesiones, rol):
    assert _producto(client, sesiones[rol])["id"]


def test_el_vendedor_no_puede_dar_de_alta(client, sesiones):
    respuesta = client.post(
        "/productos",
        json={"nombre": "Contrabando", "precio_venta": "100.00"},
        headers=sesiones["vendedor"],
    )

    assert respuesta.status_code == 403


def test_el_vendedor_no_puede_editar_ni_borrar(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    editar = client.put(
        f"/productos/{producto['id']}",
        json={"nombre": "Otro", "precio_venta": "1.00"},
        headers=sesiones["vendedor"],
    )
    borrar = client.delete(
        f"/productos/{producto['id']}", headers=sesiones["vendedor"]
    )

    assert editar.status_code == 403
    assert borrar.status_code == 403


def test_sin_sesion_no_se_ve_nada(client):
    assert client.get("/productos").status_code == 401


# --- el costo es informacion del negocio (RF-H06) ------------------------


def test_el_propietario_ve_el_costo_y_el_margen(client, sesiones):
    producto = _producto(client, sesiones["propietario"])

    cuerpo = client.get(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    ).json()

    assert cuerpo["precio_costo"] == "800.00"
    assert cuerpo["margen"] == "50.00"


@pytest.mark.parametrize("rol", ["encargado", "vendedor"])
def test_el_resto_no_ve_el_costo_ni_el_margen(client, sesiones, rol):
    """Quien atiende el mostrador no tiene por que saber la ganancia."""
    producto = _producto(client, sesiones["propietario"])

    cuerpo = client.get(
        f"/productos/{producto['id']}", headers=sesiones[rol]
    ).json()

    assert cuerpo["precio_costo"] is None
    assert cuerpo["margen"] is None


def test_el_costo_tampoco_se_filtra_en_el_listado(client, sesiones):
    _producto(client, sesiones["propietario"])

    cuerpo = client.get("/productos", headers=sesiones["vendedor"]).json()

    assert cuerpo["items"][0]["precio_costo"] is None


# --- codigo de barras (RF-C02) -------------------------------------------


def test_el_codigo_de_barras_no_se_repite(client, sesiones):
    _producto(client, sesiones["propietario"], codigo_barra=CODIGO)

    repetido = client.post(
        "/productos",
        json={
            "nombre": "Otro",
            "precio_venta": "500.00",
            "codigo_barra": CODIGO,
        },
        headers=sesiones["propietario"],
    )

    assert repetido.status_code == 400
    assert "Alfajor triple" in repetido.json()["detail"]


def test_varios_productos_pueden_no_tener_codigo(client, sesiones):
    _producto(client, sesiones["propietario"], nombre="Suelto uno")
    _producto(client, sesiones["propietario"], nombre="Suelto dos")

    cuerpo = client.get("/productos", headers=sesiones["vendedor"]).json()
    assert cuerpo["total"] == 2


def test_se_busca_un_producto_por_su_codigo(client, sesiones):
    _producto(client, sesiones["propietario"], codigo_barra=CODIGO)

    respuesta = client.get(
        f"/productos/codigo/{CODIGO}", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Alfajor triple"


def test_un_codigo_inexistente_devuelve_404(client, sesiones):
    respuesta = client.get(
        "/productos/codigo/0000000000000", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 404


def test_un_producto_dado_de_baja_no_aparece_por_codigo(client, sesiones):
    """El lector del mostrador no debe encontrar lo que ya no se vende."""
    producto = _producto(client, sesiones["propietario"], codigo_barra=CODIGO)
    client.delete(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    )

    respuesta = client.get(
        f"/productos/codigo/{CODIGO}", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 404


# --- busqueda, filtros y paginado (RF-C08, RNF-06) -----------------------


def test_la_busqueda_encuentra_por_nombre_parcial(client, sesiones):
    _producto(client, sesiones["propietario"], nombre="Alfajor triple")
    _producto(client, sesiones["propietario"], nombre="Gaseosa 500")

    cuerpo = client.get(
        "/productos?busqueda=alfa", headers=sesiones["vendedor"]
    ).json()

    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["nombre"] == "Alfajor triple"


def test_la_busqueda_no_distingue_mayusculas(client, sesiones):
    _producto(client, sesiones["propietario"], nombre="Alfajor triple")

    cuerpo = client.get(
        "/productos?busqueda=ALFAJOR", headers=sesiones["vendedor"]
    ).json()

    assert cuerpo["total"] == 1


def test_se_filtra_por_categoria(client, sesiones):
    categoria = _categoria(client, sesiones["propietario"])
    _producto(
        client,
        sesiones["propietario"],
        nombre="Con categoria",
        id_categoria=categoria["id"],
    )
    _producto(client, sesiones["propietario"], nombre="Sin categoria")

    cuerpo = client.get(
        f"/productos?id_categoria={categoria['id']}",
        headers=sesiones["vendedor"],
    ).json()

    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["nombre"] == "Con categoria"


def test_se_filtra_por_bajo_minimo(client, sesiones):
    _producto(
        client,
        sesiones["propietario"],
        nombre="Hay que reponer",
        stock_actual=5,
        stock_minimo=10,
    )
    _producto(
        client,
        sesiones["propietario"],
        nombre="Sobra",
        stock_actual=50,
        stock_minimo=10,
    )

    cuerpo = client.get(
        "/productos?solo_bajo_minimo=true", headers=sesiones["vendedor"]
    ).json()

    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["nombre"] == "Hay que reponer"


def test_el_listado_se_pagina(client, sesiones):
    for numero in range(5):
        _producto(client, sesiones["propietario"], nombre=f"Producto {numero}")

    cuerpo = client.get(
        "/productos?pagina=2&limite=2", headers=sesiones["vendedor"]
    ).json()

    assert cuerpo["total"] == 5
    assert len(cuerpo["items"]) == 2
    assert cuerpo["pagina"] == 2


def test_no_se_puede_pedir_una_pagina_enorme(client, sesiones):
    """Sin tope, un solo pedido se lleva la tabla entera (RNF-06)."""
    respuesta = client.get(
        "/productos?limite=100000", headers=sesiones["vendedor"]
    )

    assert respuesta.status_code == 422


# --- baja logica (RF-C09) ------------------------------------------------


def test_un_producto_sin_historial_se_borra_de_verdad(client, sesiones, db):
    producto = _producto(client, sesiones["propietario"])

    client.delete(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    )

    assert db.get(Producto, producto["id"]) is None


def test_un_producto_con_historial_se_desactiva_y_conserva_su_pasado(
    client, sesiones, db
):
    """Lo que la version de escritorio resolvia borrando las ventas."""
    producto = _producto(client, sesiones["propietario"])
    _movimiento(client, sesiones["propietario"], producto["id"])

    respuesta = client.delete(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 200
    guardado = db.get(Producto, producto["id"])
    assert guardado is not None
    assert guardado.activo is False
    assert db.query(MovimientoStock).count() == 1


def test_un_producto_desactivado_no_sale_en_el_listado(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _movimiento(client, sesiones["propietario"], producto["id"], cantidad=1)
    client.delete(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    )

    visible = client.get("/productos", headers=sesiones["vendedor"]).json()
    con_inactivos = client.get(
        "/productos?incluir_inactivos=true", headers=sesiones["vendedor"]
    ).json()

    assert visible["total"] == 0
    assert con_inactivos["total"] == 1


def test_un_producto_desactivado_se_puede_reactivar(client, sesiones):
    producto = _producto(client, sesiones["propietario"])
    _movimiento(client, sesiones["propietario"], producto["id"], cantidad=1)
    client.delete(
        f"/productos/{producto['id']}", headers=sesiones["propietario"]
    )

    respuesta = client.post(
        f"/productos/{producto['id']}/reactivar",
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is True


# --- validaciones de alta y edicion --------------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("precio_venta", "-1.00"),
        ("stock_actual", -5),
        ("stock_minimo", -1),
        ("nombre", "   "),
    ],
)
def test_se_rechazan_los_valores_imposibles(client, sesiones, campo, valor):
    datos = {"nombre": "Prueba", "precio_venta": "100.00", campo: valor}

    respuesta = client.post(
        "/productos", json=datos, headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 422


def test_no_se_puede_apuntar_a_una_categoria_inexistente(client, sesiones):
    respuesta = client.post(
        "/productos",
        json={
            "nombre": "Prueba",
            "precio_venta": "100.00",
            "id_categoria": 9999,
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 404


def test_sin_stock_inicial_se_toma_el_de_carga(client, sesiones):
    """Es la referencia contra la que se calcula el porcentaje."""
    cuerpo = _producto(
        client,
        sesiones["propietario"],
        stock_actual=30,
        stock_inicial=None,
    )

    assert cuerpo["stock_inicial"] == 30
    assert cuerpo["porcentaje_stock"] == 100


def test_la_edicion_no_puede_tocar_el_stock(client, sesiones, db):
    """El stock se mueve por el modulo D, que deja traza."""
    producto = _producto(client, sesiones["propietario"], stock_actual=40)

    client.put(
        f"/productos/{producto['id']}",
        json={
            "nombre": "Alfajor triple",
            "precio_venta": "1200.00",
            "stock_actual": 9999,
        },
        headers=sesiones["propietario"],
    )

    assert db.get(Producto, producto["id"]).stock_actual == 40


# --- categorias (RF-C03) -------------------------------------------------


def test_el_nombre_de_categoria_no_se_repite(client, sesiones):
    _categoria(client, sesiones["propietario"])

    repetida = client.post(
        "/categorias",
        json={"nombre": "golosinas"},
        headers=sesiones["propietario"],
    )

    assert repetida.status_code == 400


def test_desactivar_una_categoria_no_toca_sus_productos(client, sesiones, db):
    categoria = _categoria(client, sesiones["propietario"])
    producto = _producto(
        client, sesiones["propietario"], id_categoria=categoria["id"]
    )

    client.delete(
        f"/categorias/{categoria['id']}", headers=sesiones["propietario"]
    )

    assert db.get(Producto, producto["id"]).id_categoria == categoria["id"]


def test_el_vendedor_no_administra_categorias(client, sesiones):
    respuesta = client.post(
        "/categorias",
        json={"nombre": "Propia"},
        headers=sesiones["vendedor"],
    )

    assert respuesta.status_code == 403
