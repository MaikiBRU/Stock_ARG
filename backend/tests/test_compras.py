"""Proveedores, compras y reportes (modulos G y H)."""

from datetime import timedelta

import pytest

from app.core import tiempo
from app.models import Compra, MovimientoStock, Producto, Proveedor

CUIT = "30712345678"


# --- ayudantes -----------------------------------------------------------


def _proveedor(client, cabeceras, **extra):
    datos = {"razon_social": "Distribuidora del Centro", "cuit": CUIT}
    datos.update(extra)
    respuesta = client.post("/proveedores", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _producto(client, cabeceras, **extra):
    datos = {
        "nombre": "Alfajor triple",
        "precio_venta": "1200.00",
        "precio_costo": "800.00",
        "stock_actual": 10,
        "stock_inicial": 100,
    }
    datos.update(extra)
    respuesta = client.post("/productos", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _comprar(client, cabeceras, id_proveedor, items, **extra):
    cuerpo = {"id_proveedor": id_proveedor, "items": items}
    cuerpo.update(extra)
    return client.post("/compras", json=cuerpo, headers=cabeceras)


def _medios(client, cabeceras):
    respuesta = client.post("/medios-pago/sembrar", headers=cabeceras)
    return {m["nombre"]: m["id"] for m in respuesta.json()}


def _vender(client, cabeceras, items, id_medio_pago, **extra):
    cuerpo = {"items": items, "id_medio_pago": id_medio_pago}
    cuerpo.update(extra)
    return client.post("/ventas", json=cuerpo, headers=cabeceras)


@pytest.fixture
def deposito(client, sesiones):
    """Un proveedor y un producto listos para comprar."""
    duena = sesiones["propietario"]
    return {
        "proveedor": _proveedor(client, duena),
        "producto": _producto(client, duena),
    }


# --- proveedores (RF-G01, RF-G05) ----------------------------------------


def test_se_da_de_alta_un_proveedor(client, sesiones):
    proveedor = _proveedor(client, sesiones["propietario"])

    assert proveedor["razon_social"] == "Distribuidora del Centro"
    assert proveedor["activo"] is True


def test_el_cuit_no_se_repite(client, sesiones):
    _proveedor(client, sesiones["propietario"])

    repetido = client.post(
        "/proveedores",
        json={"razon_social": "Otra", "cuit": CUIT},
        headers=sesiones["propietario"],
    )

    assert repetido.status_code == 400
    assert "Distribuidora" in repetido.json()["detail"]


def test_varios_proveedores_pueden_no_tener_cuit(client, sesiones):
    duena = sesiones["propietario"]
    _proveedor(client, duena, razon_social="Uno", cuit=None)
    _proveedor(client, duena, razon_social="Dos", cuit=None)

    assert client.get("/proveedores", headers=duena).json()["total"] == 2


def test_se_busca_por_razon_social_o_cuit(client, sesiones):
    duena = sesiones["propietario"]
    _proveedor(client, duena)
    _proveedor(client, duena, razon_social="Mayorista Sur", cuit="30999888777")

    por_nombre = client.get(
        "/proveedores?busqueda=mayorista", headers=duena
    ).json()
    por_cuit = client.get("/proveedores?busqueda=30712", headers=duena).json()

    assert por_nombre["total"] == 1
    assert por_cuit["items"][0]["razon_social"] == "Distribuidora del Centro"


def test_el_vendedor_no_ve_proveedores(client, sesiones):
    """Los proveedores son de la gestion (matriz de permisos)."""
    respuesta = client.get("/proveedores", headers=sesiones["vendedor"])

    assert respuesta.status_code == 403


def test_un_proveedor_sin_historial_se_borra(client, sesiones, db):
    proveedor = _proveedor(client, sesiones["propietario"])

    client.delete(
        f"/proveedores/{proveedor['id']}", headers=sesiones["propietario"]
    )

    assert db.get(Proveedor, proveedor["id"]) is None


def test_un_proveedor_con_productos_se_desactiva(client, sesiones, db):
    """Borrarlo dejaria los productos apuntando a un id inexistente."""
    duena = sesiones["propietario"]
    proveedor = _proveedor(client, duena)
    _producto(client, duena, id_proveedor=proveedor["id"])

    client.delete(f"/proveedores/{proveedor['id']}", headers=duena)

    guardado = db.get(Proveedor, proveedor["id"])
    assert guardado is not None
    assert guardado.activo is False


def test_se_listan_los_productos_que_provee(client, sesiones, deposito):
    """RF-G02."""
    duena = sesiones["propietario"]
    _producto(
        client,
        duena,
        nombre="Gaseosa 500",
        id_proveedor=deposito["proveedor"]["id"],
    )

    cuerpo = client.get(
        f"/proveedores/{deposito['proveedor']['id']}/productos",
        headers=duena,
    ).json()

    assert len(cuerpo) == 1
    assert cuerpo[0]["nombre"] == "Gaseosa 500"


def test_el_encargado_no_ve_el_costo_de_los_productos_del_proveedor(
    client, sesiones, deposito
):
    _producto(
        client,
        sesiones["propietario"],
        nombre="Gaseosa 500",
        id_proveedor=deposito["proveedor"]["id"],
    )

    cuerpo = client.get(
        f"/proveedores/{deposito['proveedor']['id']}/productos",
        headers=sesiones["encargado"],
    ).json()

    assert cuerpo[0]["precio_costo"] is None


# --- compras (RF-G03) ----------------------------------------------------


def test_la_compra_suma_stock(client, sesiones, deposito, db):
    respuesta = _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 24,
                "costo_unitario": "700.00",
            }
        ],
    )

    assert respuesta.status_code == 201
    assert db.get(Producto, deposito["producto"]["id"]).stock_actual == 34


def test_el_total_de_la_compra_lo_calcula_el_servidor(
    client, sesiones, deposito
):
    respuesta = _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 10,
                "costo_unitario": "750.50",
            }
        ],
    )

    assert respuesta.json()["total"] == "7505.00"


def test_mandar_un_total_en_la_compra_se_rechaza(client, sesiones, deposito):
    """Mismo criterio que en la venta."""
    respuesta = _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 1,
                "costo_unitario": "700.00",
            }
        ],
        total="1.00",
    )

    assert respuesta.status_code == 422


def test_la_compra_deja_un_movimiento_de_entrada(
    client, sesiones, deposito, db
):
    _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 5,
                "costo_unitario": "700.00",
            }
        ],
    )

    movimiento = db.query(MovimientoStock).one()
    assert movimiento.tipo.value == "entrada"
    assert movimiento.id_compra is not None


def test_la_compra_actualiza_el_costo_del_producto(
    client, sesiones, deposito, db
):
    """Es el numero que hace que el margen diga algo real."""
    _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 5,
                "costo_unitario": "950.00",
            }
        ],
    )

    guardado = db.get(Producto, deposito["producto"]["id"])
    assert str(guardado.precio_costo) == "950.00"


def test_se_puede_pedir_que_no_actualice_el_costo(
    client, sesiones, deposito, db
):
    _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 5,
                "costo_unitario": "950.00",
            }
        ],
        actualizar_costo=False,
    )

    guardado = db.get(Producto, deposito["producto"]["id"])
    assert str(guardado.precio_costo) == "800.00"


def test_el_mismo_producto_repetido_promedia_el_costo(
    client, sesiones, deposito
):
    """Quedarse con uno de los dos daria un costo que no se pago."""
    respuesta = _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 10,
                "costo_unitario": "600.00",
            },
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 10,
                "costo_unitario": "800.00",
            },
        ],
    )

    cuerpo = respuesta.json()
    assert len(cuerpo["items"]) == 1
    assert cuerpo["items"][0]["cantidad"] == 20
    assert cuerpo["items"][0]["costo_unitario"] == "700.00"


def test_una_compra_con_fecha_futura_se_rechaza(client, sesiones, deposito):
    """Descuadraria cualquier reporte por periodo."""
    manana = (tiempo.hoy() + timedelta(days=1)).isoformat()

    respuesta = _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 1,
                "costo_unitario": "700.00",
            }
        ],
        fecha=manana,
    )

    assert respuesta.status_code == 400
    assert "futura" in respuesta.json()["detail"].lower()


def test_un_proveedor_dado_de_baja_no_recibe_compras(
    client, sesiones, deposito
):
    duena = sesiones["propietario"]
    _producto(client, duena, id_proveedor=deposito["proveedor"]["id"])
    client.delete(f"/proveedores/{deposito['proveedor']['id']}", headers=duena)

    respuesta = _comprar(
        client,
        duena,
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 1,
                "costo_unitario": "700.00",
            }
        ],
    )

    assert respuesta.status_code == 400


def test_una_compra_rechazada_no_deja_nada_escrito(
    client, sesiones, deposito, db
):
    _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [{"id_producto": 9999, "cantidad": 1, "costo_unitario": "700.00"}],
    )

    assert db.query(Compra).count() == 0
    assert db.query(MovimientoStock).count() == 0
    assert db.get(Producto, deposito["producto"]["id"]).stock_actual == 10


def test_un_costo_negativo_se_rechaza(client, sesiones, deposito):
    respuesta = _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 1,
                "costo_unitario": "-1.00",
            }
        ],
    )

    assert respuesta.status_code == 422


def test_una_compra_sin_lineas_se_rechaza(client, sesiones, deposito):
    respuesta = _comprar(
        client, sesiones["propietario"], deposito["proveedor"]["id"], []
    )

    assert respuesta.status_code == 422


def test_el_vendedor_no_puede_comprar(client, sesiones, deposito):
    respuesta = _comprar(
        client,
        sesiones["vendedor"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 1,
                "costo_unitario": "700.00",
            }
        ],
    )

    assert respuesta.status_code == 403


def test_el_resumen_por_proveedor_suma_lo_comprado(client, sesiones, deposito):
    """RF-G04."""
    duena = sesiones["propietario"]
    for _ in range(2):
        _comprar(
            client,
            duena,
            deposito["proveedor"]["id"],
            [
                {
                    "id_producto": deposito["producto"]["id"],
                    "cantidad": 10,
                    "costo_unitario": "700.00",
                }
            ],
        )

    cuerpo = client.get(
        f"/proveedores/{deposito['proveedor']['id']}/compras", headers=duena
    ).json()

    assert cuerpo["cantidad_compras"] == 2
    assert cuerpo["total_comprado"] == "14000.00"


# --- reportes (modulo H) -------------------------------------------------


@pytest.fixture
def con_ventas(client, sesiones, deposito):
    """Dos ventas cobradas y una anulada, para los reportes."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = deposito["producto"]

    for _ in range(2):
        _vender(
            client,
            duena,
            [{"id_producto": producto["id"], "cantidad": 2}],
            medios["Efectivo"],
        )

    anulada = _vender(
        client,
        duena,
        [{"id_producto": producto["id"], "cantidad": 1}],
        medios["Transferencia"],
    ).json()
    client.post(f"/ventas/{anulada['id']}/anular", json={}, headers=duena)

    return {"medios": medios, "producto": producto}


def test_el_reporte_de_ventas_suma_lo_cobrado(client, sesiones, con_ventas):
    """RF-H01."""
    cuerpo = client.get(
        "/reportes/ventas?periodo=hoy", headers=sesiones["propietario"]
    ).json()

    assert cuerpo["cantidad_ventas"] == 2
    assert cuerpo["total_facturado"] == "4800.00"
    assert cuerpo["ticket_promedio"] == "2400.00"
    assert cuerpo["sin_datos"] is False


def test_las_ventas_anuladas_no_entran_en_el_reporte(
    client, sesiones, con_ventas
):
    """Dirian que se vendio algo que se dio marcha atras."""
    cuerpo = client.get(
        "/reportes/ventas?periodo=hoy", headers=sesiones["propietario"]
    ).json()

    # Tres ventas hechas, una anulada: solo dos cuentan.
    assert cuerpo["cantidad_ventas"] == 2


def test_sin_operaciones_el_reporte_lo_dice(client, sesiones):
    """RF-H07: no se muestran ceros que parecen un dia flojo."""
    cuerpo = client.get(
        "/reportes/ventas?periodo=hoy", headers=sesiones["propietario"]
    ).json()

    assert cuerpo["sin_datos"] is True
    assert cuerpo["cantidad_ventas"] == 0


def test_el_ranking_ordena_por_unidades(client, sesiones, con_ventas):
    """RF-H02."""
    cuerpo = client.get(
        "/reportes/mas-vendidos?periodo=hoy",
        headers=sesiones["propietario"],
    ).json()

    assert cuerpo["ranking"][0]["unidades"] == 4
    assert cuerpo["ordenado_por"] == "unidades"


def test_el_ranking_puede_ordenar_por_facturacion(client, sesiones, con_ventas):
    cuerpo = client.get(
        "/reportes/mas-vendidos?periodo=hoy&ordenar_por=facturacion",
        headers=sesiones["propietario"],
    ).json()

    assert cuerpo["ranking"][0]["facturado"] == "4800.00"


def test_un_orden_inventado_se_rechaza(client, sesiones):
    respuesta = client.get(
        "/reportes/mas-vendidos?ordenar_por=magia",
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 422


def test_el_corte_por_medio_de_pago(client, sesiones, con_ventas):
    """RF-H03."""
    cuerpo = client.get(
        "/reportes/medios-pago?periodo=hoy",
        headers=sesiones["propietario"],
    ).json()

    assert len(cuerpo["detalle"]) == 1
    assert cuerpo["detalle"][0]["nombre"] == "Efectivo"
    assert cuerpo["detalle"][0]["total"] == "4800.00"


def test_el_corte_por_categoria_agrupa_los_sin_rubro(
    client, sesiones, con_ventas
):
    """Dejarlos afuera daria un total menor al real."""
    cuerpo = client.get(
        "/reportes/categorias?periodo=hoy",
        headers=sesiones["propietario"],
    ).json()

    assert cuerpo["detalle"][0]["nombre"] == "Sin categoria"
    assert cuerpo["detalle"][0]["unidades"] == 4


def test_la_serie_completa_los_dias_sin_ventas(client, sesiones, con_ventas):
    """Sin los huecos en cero, el grafico inventa una pendiente."""
    serie = client.get(
        "/reportes/ventas/serie?periodo=semana",
        headers=sesiones["propietario"],
    ).json()

    assert len(serie) == 7
    assert sum(p["cantidad_ventas"] for p in serie) == 2


def test_un_rango_invertido_se_rechaza(client, sesiones):
    respuesta = client.get(
        "/reportes/ventas?desde=2026-12-31&hasta=2026-01-01",
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400


def test_el_reporte_de_compras_suma_lo_gastado(client, sesiones, deposito):
    _comprar(
        client,
        sesiones["propietario"],
        deposito["proveedor"]["id"],
        [
            {
                "id_producto": deposito["producto"]["id"],
                "cantidad": 10,
                "costo_unitario": "700.00",
            }
        ],
    )

    cuerpo = client.get(
        "/reportes/compras?periodo=hoy", headers=sesiones["propietario"]
    ).json()

    assert cuerpo["cantidad_compras"] == 1
    assert cuerpo["total_gastado"] == "7000.00"


# --- rentabilidad: solo el propietario (RF-H06) --------------------------


def test_la_rentabilidad_calcula_la_ganancia(client, sesiones, con_ventas):
    cuerpo = client.get(
        "/reportes/rentabilidad?periodo=hoy",
        headers=sesiones["propietario"],
    ).json()

    fila = cuerpo["detalle"][0]
    assert fila["ingreso"] == "4800.00"
    assert fila["costo"] == "3200.00"
    assert fila["ganancia"] == "1600.00"
    assert cuerpo["ganancia"] == "1600.00"


def test_la_rentabilidad_avisa_de_que_costo_usa(client, sesiones, con_ventas):
    """El costo es el de hoy, no el del dia de la venta."""
    cuerpo = client.get(
        "/reportes/rentabilidad?periodo=hoy",
        headers=sesiones["propietario"],
    ).json()

    assert "costo" in cuerpo["advertencia"].lower()


@pytest.mark.parametrize("rol", ["encargado", "vendedor"])
def test_solo_el_propietario_ve_la_rentabilidad(client, sesiones, rol):
    respuesta = client.get("/reportes/rentabilidad", headers=sesiones[rol])

    assert respuesta.status_code == 403


def test_el_vendedor_no_ve_ningun_reporte(client, sesiones):
    """Los reportes son de la gestion (matriz de permisos)."""
    for ruta in ("ventas", "mas-vendidos", "medios-pago", "categorias"):
        respuesta = client.get(
            f"/reportes/{ruta}", headers=sesiones["vendedor"]
        )
        assert respuesta.status_code == 403, ruta


# --- exportacion de reportes (RF-H08) ------------------------------------


@pytest.mark.parametrize(
    "reporte", ["mas-vendidos", "medios-pago", "categorias"]
)
def test_los_reportes_se_exportan_a_csv(client, sesiones, con_ventas, reporte):
    respuesta = client.get(
        f"/reportes/exportar?reporte={reporte}&periodo=hoy",
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]


def test_los_reportes_se_exportan_a_pdf(client, sesiones, con_ventas):
    respuesta = client.get(
        "/reportes/exportar?reporte=mas-vendidos&formato=pdf&periodo=hoy",
        headers=sesiones["propietario"],
    )

    assert respuesta.content.startswith(b"%PDF")


def test_no_se_puede_exportar_la_rentabilidad_por_esa_ruta(
    client, sesiones, con_ventas
):
    """El permiso no puede depender de un parametro de consulta."""
    respuesta = client.get(
        "/reportes/exportar?reporte=rentabilidad",
        headers=sesiones["encargado"],
    )

    assert respuesta.status_code == 422


def test_el_vendedor_no_puede_exportar_reportes(client, sesiones):
    respuesta = client.get(
        "/reportes/exportar?reporte=mas-vendidos",
        headers=sesiones["vendedor"],
    )

    assert respuesta.status_code == 403


# --- importacion y exportacion de contactos (RF-F05, RF-G05) -------------


def _subir(client, cabeceras, ruta, contenido: bytes):
    return client.post(
        ruta,
        files={"archivo": ("lista.csv", contenido, "text/csv")},
        headers=cabeceras,
    )


def test_se_importan_proveedores_desde_csv(client, sesiones, db):
    contenido = (
        b"razon_social;cuit;telefono;localidad\n"
        b"Distribuidora Norte;30111111111;3411234567;Rosario\n"
        b"Mayorista Sur;30222222222;3417654321;Funes"
    )

    respuesta = _subir(
        client, sesiones["propietario"], "/proveedores/importar", contenido
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["a_crear"] == 2
    assert db.query(Proveedor).count() == 2


def test_la_vista_previa_de_proveedores_no_guarda_nada(client, sesiones, db):
    contenido = b"razon_social;cuit\nDistribuidora Norte;30111111111"

    respuesta = _subir(
        client,
        sesiones["propietario"],
        "/proveedores/importar/previsualizar",
        contenido,
    )

    assert respuesta.json()["aplicada"] is False
    assert db.query(Proveedor).count() == 0


def test_reimportar_un_cuit_existente_lo_actualiza(client, sesiones, db):
    _proveedor(client, sesiones["propietario"])

    cuerpo = _subir(
        client,
        sesiones["propietario"],
        "/proveedores/importar",
        f"razon_social;cuit;telefono\nRazon nueva;{CUIT};3410000000".encode(),
    ).json()

    assert cuerpo["a_actualizar"] == 1
    assert db.query(Proveedor).count() == 1
    assert db.query(Proveedor).one().razon_social == "Razon nueva"


def test_una_fila_sin_razon_social_es_un_error(client, sesiones):
    contenido = b"razon_social;cuit\n;30111111111\nValida;30222222222"

    cuerpo = _subir(
        client, sesiones["propietario"], "/proveedores/importar", contenido
    ).json()

    assert cuerpo["con_error"] == 1
    assert cuerpo["a_crear"] == 1


def test_dos_filas_con_el_mismo_cuit_se_reportan(client, sesiones, db):
    contenido = b"razon_social;cuit\nUna;30111111111\nOtra;30111111111"

    cuerpo = _subir(
        client, sesiones["propietario"], "/proveedores/importar", contenido
    ).json()

    assert cuerpo["con_error"] == 1
    assert db.query(Proveedor).count() == 1


def test_un_correo_mal_formado_en_el_csv_es_un_error_de_fila(client, sesiones):
    contenido = b"razon_social;email\nUna;no-es-correo"

    cuerpo = _subir(
        client, sesiones["propietario"], "/proveedores/importar", contenido
    ).json()

    assert cuerpo["con_error"] == 1


def test_se_avisa_si_falta_la_columna_obligatoria(client, sesiones):
    respuesta = _subir(
        client,
        sesiones["propietario"],
        "/proveedores/importar",
        b"cuit;telefono\n30111111111;3411234567",
    )

    assert respuesta.status_code == 400
    assert "razon_social" in respuesta.json()["detail"]


def test_se_importan_clientes_desde_csv(client, sesiones, db):
    from app.models import Cliente

    contenido = (
        b"nombre;apellido;documento;telefono\n"
        b"Ana;Gomez;30111222;3411234567\n"
        b"Beto;Diaz;30333444;3417654321"
    )

    respuesta = _subir(
        client, sesiones["propietario"], "/clientes/importar", contenido
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["a_crear"] == 2
    assert db.query(Cliente).count() == 2


def test_reimportar_un_documento_existente_actualiza_al_cliente(
    client, sesiones, db
):
    from app.models import Cliente

    client.post(
        "/clientes",
        json={"nombre": "Ana", "documento": "30111222"},
        headers=sesiones["propietario"],
    )

    cuerpo = _subir(
        client,
        sesiones["propietario"],
        "/clientes/importar",
        b"nombre;documento;localidad\nAna Maria;30111222;Rosario",
    ).json()

    assert cuerpo["a_actualizar"] == 1
    assert db.query(Cliente).count() == 1
    assert db.query(Cliente).one().nombre == "Ana Maria"


def test_los_proveedores_se_exportan(client, sesiones):
    _proveedor(client, sesiones["propietario"])

    csv = client.get("/proveedores/exportar", headers=sesiones["propietario"])
    pdf = client.get(
        "/proveedores/exportar?formato=pdf", headers=sesiones["propietario"]
    )

    assert "Distribuidora del Centro" in csv.content.decode("utf-8")
    assert pdf.content.startswith(b"%PDF")


def test_los_clientes_se_exportan(client, sesiones):
    client.post(
        "/clientes",
        json={"nombre": "Ana", "apellido": "Gomez"},
        headers=sesiones["propietario"],
    )

    csv = client.get("/clientes/exportar", headers=sesiones["propietario"])
    pdf = client.get(
        "/clientes/exportar?formato=pdf", headers=sesiones["propietario"]
    )

    assert "Gomez" in csv.content.decode("utf-8")
    assert pdf.content.startswith(b"%PDF")


def test_la_exportacion_de_contactos_respeta_el_filtro(client, sesiones):
    duena = sesiones["propietario"]
    _proveedor(client, duena)
    _proveedor(client, duena, razon_social="Mayorista Sur", cuit="30999888777")

    texto = client.get(
        "/proveedores/exportar?busqueda=mayorista", headers=duena
    ).content.decode("utf-8")

    assert "Mayorista Sur" in texto
    assert "Distribuidora del Centro" not in texto


def test_el_vendedor_no_importa_ni_exporta_contactos(client, sesiones):
    exportar_proveedores = client.get(
        "/proveedores/exportar", headers=sesiones["vendedor"]
    )
    exportar_clientes = client.get(
        "/clientes/exportar", headers=sesiones["vendedor"]
    )
    importar = _subir(
        client,
        sesiones["vendedor"],
        "/clientes/importar",
        b"nombre\nAna",
    )

    assert exportar_proveedores.status_code == 403
    assert exportar_clientes.status_code == 403
    assert importar.status_code == 403


def test_las_rutas_de_contactos_respetan_el_orden_de_declaracion():
    """Regresion: "/exportar" tapado por la ruta variable."""
    from app.api.routes.clientes import router as clientes
    from app.api.routes.proveedores import router as proveedores

    rutas_clientes = [r.path for r in clientes.routes]
    rutas_proveedores = [r.path for r in proveedores.routes]

    assert rutas_clientes.index("/clientes/exportar") < rutas_clientes.index(
        "/clientes/{id_cliente}"
    )
    assert rutas_proveedores.index(
        "/proveedores/exportar"
    ) < rutas_proveedores.index("/proveedores/{id_proveedor}")
