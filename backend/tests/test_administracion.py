"""Panel, administracion y anulacion de compras (modulos B e I)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core import tiempo
from app.models import Auditoria, Compra, EstadoCompra, Producto, Usuario

CLAVE = "Kiosco2026"


# --- ayudantes -----------------------------------------------------------


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


def _medios(client, cabeceras):
    respuesta = client.post("/medios-pago/sembrar", headers=cabeceras)
    return {m["nombre"]: m["id"] for m in respuesta.json()}


def _vender(client, cabeceras, id_producto, id_medio, cantidad=1):
    return client.post(
        "/ventas",
        json={
            "items": [{"id_producto": id_producto, "cantidad": cantidad}],
            "id_medio_pago": id_medio,
        },
        headers=cabeceras,
    )


def _proveedor(client, cabeceras):
    respuesta = client.post(
        "/proveedores",
        json={"razon_social": "Distribuidora del Centro"},
        headers=cabeceras,
    )
    return respuesta.json()


def _comprar(client, cabeceras, id_proveedor, id_producto, cantidad=10):
    return client.post(
        "/compras",
        json={
            "id_proveedor": id_proveedor,
            "items": [
                {
                    "id_producto": id_producto,
                    "cantidad": cantidad,
                    "costo_unitario": "700.00",
                }
            ],
        },
        headers=cabeceras,
    )


# --- panel principal (modulo B) ------------------------------------------


def test_el_panel_trae_las_ventas_del_dia(client, sesiones):
    """RF-B01, RF-B02."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = _producto(client, duena)
    _vender(client, duena, producto["id"], medios["Efectivo"], cantidad=2)

    cuerpo = client.get("/panel", headers=duena).json()

    assert cuerpo["ventas_del_dia"]["cantidad_ventas"] == 1
    assert cuerpo["ventas_del_dia"]["total_facturado"] == "2400.00"
    assert cuerpo["medios_de_pago"][0]["nombre"] == "Efectivo"


def test_el_panel_lista_lo_que_hay_que_reponer(client, sesiones):
    """RF-B03."""
    duena = sesiones["propietario"]
    _producto(client, duena, nombre="Faltante", stock_actual=2, stock_minimo=10)
    _producto(client, duena, nombre="Sobra", stock_actual=50, stock_minimo=10)

    cuerpo = client.get("/panel", headers=duena).json()

    assert len(cuerpo["bajo_minimo"]) == 1
    assert cuerpo["bajo_minimo"][0]["nombre"] == "Faltante"


def test_el_panel_avisa_de_los_proximos_a_vencer(client, sesiones):
    """RF-B04. Los ya vencidos van en su propia lista."""
    duena = sesiones["propietario"]
    hoy = tiempo.hoy()
    _producto(
        client,
        duena,
        nombre="Vence pronto",
        fecha_vencimiento=(hoy + timedelta(days=10)).isoformat(),
    )
    _producto(
        client,
        duena,
        nombre="Vence lejos",
        fecha_vencimiento=(hoy + timedelta(days=200)).isoformat(),
    )

    cuerpo = client.get("/panel", headers=duena).json()

    nombres = [p["nombre"] for p in cuerpo["proximos_a_vencer"]]
    assert nombres == ["Vence pronto"]


def test_el_panel_separa_los_vencidos_con_stock(client, sesiones):
    """RF-B05. Sin stock no hay nada que dar de baja."""
    duena = sesiones["propietario"]
    ayer = (tiempo.hoy() - timedelta(days=1)).isoformat()
    _producto(
        client,
        duena,
        nombre="Vencido con stock",
        fecha_vencimiento=ayer,
        stock_actual=5,
    )
    _producto(
        client,
        duena,
        nombre="Vencido sin stock",
        fecha_vencimiento=ayer,
        stock_actual=0,
    )

    cuerpo = client.get("/panel", headers=duena).json()

    nombres = [p["nombre"] for p in cuerpo["vencidos"]]
    assert nombres == ["Vencido con stock"]
    assert not cuerpo["proximos_a_vencer"]


def test_el_panel_trae_el_top_del_mes_y_la_serie(client, sesiones):
    """RF-B06, RF-B07."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = _producto(client, duena)
    _vender(client, duena, producto["id"], medios["Efectivo"], cantidad=3)

    cuerpo = client.get("/panel", headers=duena).json()

    assert cuerpo["mas_vendidos_del_mes"][0]["unidades"] == 3
    assert len(cuerpo["serie_ventas"]) == 30


def test_el_panel_sin_movimiento_lo_dice(client, sesiones):
    """RF-B08: ceros sin explicar parecen un dia flojo."""
    cuerpo = client.get("/panel", headers=sesiones["propietario"]).json()

    assert cuerpo["ventas_del_dia"]["sin_datos"] is True
    assert cuerpo["bajo_minimo"] == []
    assert cuerpo["mas_vendidos_del_mes"] == []


def test_solo_el_propietario_ve_la_ganancia_en_el_panel(client, sesiones):
    duena = client.get("/panel", headers=sesiones["propietario"]).json()
    encargado = client.get("/panel", headers=sesiones["encargado"]).json()

    assert duena["rentabilidad_del_mes"] is not None
    assert encargado["rentabilidad_del_mes"] is None


def test_el_encargado_no_ve_el_costo_en_las_alertas(client, sesiones):
    _producto(client, sesiones["propietario"], stock_actual=1, stock_minimo=10)

    cuerpo = client.get("/panel", headers=sesiones["encargado"]).json()

    assert cuerpo["bajo_minimo"][0]["precio_costo"] is None


def test_el_vendedor_no_ve_el_panel(client, sesiones):
    respuesta = client.get("/panel", headers=sesiones["vendedor"])

    assert respuesta.status_code == 403


# --- usuarios (RF-I01 a RF-I03) ------------------------------------------


def test_el_propietario_da_de_alta_un_usuario(client, sesiones, db):
    respuesta = client.post(
        "/usuarios",
        json={
            "email": "nuevo@stockarg.com.ar",
            "nombre": "Nuevo",
            "contrasena": CLAVE,
            "rol": "encargado",
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["rol"] == "encargado"
    creado = db.query(Usuario).filter_by(email="nuevo@stockarg.com.ar").one()
    assert creado.verificado is True


def test_el_usuario_creado_puede_ingresar(client, sesiones):
    client.post(
        "/usuarios",
        json={
            "email": "nuevo@stockarg.com.ar",
            "nombre": "Nuevo",
            "contrasena": CLAVE,
        },
        headers=sesiones["propietario"],
    )

    respuesta = client.post(
        "/auth/login",
        json={"email": "nuevo@stockarg.com.ar", "contrasena": CLAVE},
    )

    assert respuesta.status_code == 200


def test_no_se_repite_el_correo(client, sesiones):
    respuesta = client.post(
        "/usuarios",
        json={
            "email": "propietario@stockarg.com.ar",
            "nombre": "Otro",
            "contrasena": CLAVE,
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400


def test_se_rechaza_una_contrasena_debil(client, sesiones):
    respuesta = client.post(
        "/usuarios",
        json={
            "email": "nuevo@stockarg.com.ar",
            "nombre": "Nuevo",
            "contrasena": "corta",
        },
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 422


def test_se_cambia_el_rol_de_un_usuario(client, sesiones, db):
    vendedor = db.query(Usuario).filter_by(rol="vendedor").one()

    respuesta = client.put(
        f"/usuarios/{vendedor.id}/rol",
        json={"rol": "encargado"},
        headers=sesiones["propietario"],
    )

    assert respuesta.json()["rol"] == "encargado"


def test_no_se_puede_degradar_al_unico_propietario(client, sesiones, db):
    """RF-I03: sin propietario, nadie puede administrar nada."""
    duena = db.query(Usuario).filter_by(rol="propietario").one()

    respuesta = client.put(
        f"/usuarios/{duena.id}/rol",
        json={"rol": "vendedor"},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400
    assert "propietario" in respuesta.json()["detail"].lower()


def test_nadie_puede_darse_de_baja_a_si_mismo(client, sesiones, db):
    """Cerraria su propia sesion y podria dejar el sistema sin duena."""
    duena = db.query(Usuario).filter_by(rol="propietario").one()

    respuesta = client.delete(
        f"/usuarios/{duena.id}", headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 400


def test_dar_de_baja_conserva_las_operaciones(client, sesiones, db):
    """RF-I02: sus ventas siguen diciendo quien las hizo."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = _producto(client, duena)
    vendedor = db.query(Usuario).filter_by(rol="vendedor").one()
    _vender(client, sesiones["vendedor"], producto["id"], medios["Efectivo"])

    client.delete(f"/usuarios/{vendedor.id}", headers=duena)

    assert db.get(Usuario, vendedor.id).activo is False
    assert client.get("/ventas", headers=duena).json()["total"] == 1


def test_una_cuenta_dada_de_baja_no_ingresa(client, sesiones, db):
    vendedor = db.query(Usuario).filter_by(rol="vendedor").one()
    client.delete(f"/usuarios/{vendedor.id}", headers=sesiones["propietario"])

    respuesta = client.post(
        "/auth/login",
        json={"email": vendedor.email, "contrasena": CLAVE},
    )

    assert respuesta.status_code == 401


def test_habilitar_le_saca_el_bloqueo_por_intentos(client, sesiones, db):
    """Rehabilitar sin destrabar no serviria de nada."""
    vendedor = db.query(Usuario).filter_by(rol="vendedor").one()
    vendedor.activo = False
    vendedor.intentos_fallidos = 5
    vendedor.bloqueado_hasta = datetime.now(UTC) + timedelta(minutes=10)
    db.commit()

    client.post(
        f"/usuarios/{vendedor.id}/habilitar",
        headers=sesiones["propietario"],
    )

    guardado = db.get(Usuario, vendedor.id)
    assert guardado.activo is True
    assert guardado.bloqueado_hasta is None
    assert guardado.intentos_fallidos == 0


@pytest.mark.parametrize("rol", ["encargado", "vendedor"])
def test_solo_el_propietario_administra_usuarios(client, sesiones, rol):
    listar = client.get("/usuarios", headers=sesiones[rol])
    crear = client.post(
        "/usuarios",
        json={
            "email": "x@stockarg.com.ar",
            "nombre": "X",
            "contrasena": CLAVE,
        },
        headers=sesiones[rol],
    )

    assert listar.status_code == 403
    assert crear.status_code == 403


def test_el_listado_de_usuarios_no_expone_el_hash(client, sesiones):
    texto = str(client.get("/usuarios", headers=sesiones["propietario"]).json())

    assert "password" not in texto
    assert "$2b$" not in texto


# --- auditoria (RF-I04) --------------------------------------------------


def test_el_alta_de_usuario_queda_auditada(client, sesiones, db):
    client.post(
        "/usuarios",
        json={
            "email": "nuevo@stockarg.com.ar",
            "nombre": "Nuevo",
            "contrasena": CLAVE,
        },
        headers=sesiones["propietario"],
    )

    linea = db.query(Auditoria).filter_by(accion="usuario.crear").one()
    assert linea.entidad == "usuario"
    assert linea.email_usuario == "propietario@stockarg.com.ar"


def test_la_auditoria_nunca_guarda_una_contrasena(client, sesiones, db):
    """Filtrar en el servicio y no en cada llamada es lo que lo asegura."""
    client.post(
        "/usuarios",
        json={
            "email": "nuevo@stockarg.com.ar",
            "nombre": "Nuevo",
            "contrasena": CLAVE,
        },
        headers=sesiones["propietario"],
    )

    for linea in db.query(Auditoria).all():
        assert CLAVE not in str(linea.detalle or {})
        assert "contrasena" not in str(linea.detalle or {})


def test_la_auditoria_se_filtra_por_accion(client, sesiones):
    duena = sesiones["propietario"]
    client.post(
        "/usuarios",
        json={
            "email": "nuevo@stockarg.com.ar",
            "nombre": "Nuevo",
            "contrasena": CLAVE,
        },
        headers=duena,
    )
    client.put(
        "/configuracion",
        json={"cambios": {"nombre_comercio": "Kiosco Aaron"}},
        headers=duena,
    )

    cuerpo = client.get("/auditoria?accion=usuario.crear", headers=duena).json()

    assert cuerpo["total"] == 1


def test_solo_el_propietario_ve_la_auditoria(client, sesiones):
    respuesta = client.get("/auditoria", headers=sesiones["encargado"])

    assert respuesta.status_code == 403


# --- configuracion (RF-I06) ----------------------------------------------


def test_la_configuracion_trae_los_valores_de_partida(client, sesiones):
    cuerpo = client.get(
        "/configuracion", headers=sesiones["propietario"]
    ).json()

    assert cuerpo["valores"]["stock_umbral_bajo"] == "30"
    assert cuerpo["valores"]["stock_umbral_medio"] == "54"


def test_se_guarda_un_parametro(client, sesiones):
    respuesta = client.put(
        "/configuracion",
        json={"cambios": {"nombre_comercio": "Kiosco Aaron"}},
        headers=sesiones["propietario"],
    )

    assert respuesta.json()["valores"]["nombre_comercio"] == "Kiosco Aaron"


def test_una_clave_inventada_se_rechaza(client, sesiones):
    """Si no, la tabla se llena de claves que nadie lee."""
    respuesta = client.put(
        "/configuracion",
        json={"cambios": {"color_favorito": "azul"}},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400


def test_un_valor_fuera_de_rango_se_rechaza(client, sesiones):
    respuesta = client.put(
        "/configuracion",
        json={"cambios": {"dias_aviso_vencimiento": "9999"}},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400


def test_no_se_pueden_invertir_los_umbrales(client, sesiones):
    """Por separado cada uno es valido; la pareja no."""
    respuesta = client.put(
        "/configuracion",
        json={"cambios": {"stock_umbral_bajo": "80"}},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 400
    assert "umbral" in respuesta.json()["detail"].lower()


def test_el_encargado_lee_pero_no_cambia_la_configuracion(client, sesiones):
    leer = client.get("/configuracion", headers=sesiones["encargado"])
    escribir = client.put(
        "/configuracion",
        json={"cambios": {"nombre_comercio": "Otro"}},
        headers=sesiones["encargado"],
    )

    assert leer.status_code == 200
    assert escribir.status_code == 403


# --- anulacion de compras ------------------------------------------------


def test_anular_una_compra_descuenta_lo_que_entro(client, sesiones, db):
    duena = sesiones["propietario"]
    producto = _producto(client, duena, stock_actual=10)
    proveedor = _proveedor(client, duena)
    compra = _comprar(
        client, duena, proveedor["id"], producto["id"], cantidad=20
    ).json()
    assert db.get(Producto, producto["id"]).stock_actual == 30

    respuesta = client.post(
        f"/compras/{compra['id']}/anular",
        json={"motivo": "Remito cargado dos veces"},
        headers=duena,
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "anulada"
    assert db.get(Producto, producto["id"]).stock_actual == 10


def test_no_se_anula_dos_veces(client, sesiones, db):
    duena = sesiones["propietario"]
    producto = _producto(client, duena)
    proveedor = _proveedor(client, duena)
    compra = _comprar(client, duena, proveedor["id"], producto["id"]).json()
    client.post(f"/compras/{compra['id']}/anular", json={}, headers=duena)

    segunda = client.post(
        f"/compras/{compra['id']}/anular", json={}, headers=duena
    )

    assert segunda.status_code == 400
    assert db.get(Producto, producto["id"]).stock_actual == 40


def test_no_se_anula_si_la_mercaderia_ya_se_vendio(client, sesiones, db):
    """Descontar de menos dejaria el inventario mintiendo."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = _producto(client, duena, stock_actual=0)
    proveedor = _proveedor(client, duena)
    compra = _comprar(
        client, duena, proveedor["id"], producto["id"], cantidad=5
    ).json()
    _vender(client, duena, producto["id"], medios["Efectivo"], cantidad=4)

    respuesta = client.post(
        f"/compras/{compra['id']}/anular", json={}, headers=duena
    )

    assert respuesta.status_code == 400
    assert "stock" in respuesta.json()["detail"].lower()
    assert db.get(Compra, compra["id"]).estado is EstadoCompra.REGISTRADA


def test_la_compra_anulada_no_cuenta_en_el_gasto(client, sesiones):
    duena = sesiones["propietario"]
    producto = _producto(client, duena)
    proveedor = _proveedor(client, duena)
    compra = _comprar(client, duena, proveedor["id"], producto["id"]).json()
    client.post(f"/compras/{compra['id']}/anular", json={}, headers=duena)

    cuerpo = client.get("/reportes/compras?periodo=hoy", headers=duena).json()

    assert cuerpo["cantidad_compras"] == 0
    assert cuerpo["total_gastado"] == "0.00"


def test_la_compra_anulada_no_cuenta_en_el_resumen_del_proveedor(
    client, sesiones
):
    duena = sesiones["propietario"]
    producto = _producto(client, duena)
    proveedor = _proveedor(client, duena)
    compra = _comprar(client, duena, proveedor["id"], producto["id"]).json()
    client.post(f"/compras/{compra['id']}/anular", json={}, headers=duena)

    cuerpo = client.get(
        f"/proveedores/{proveedor['id']}/compras", headers=duena
    ).json()

    assert cuerpo["cantidad_compras"] == 0


def test_el_vendedor_no_puede_anular_una_compra(client, sesiones):
    duena = sesiones["propietario"]
    producto = _producto(client, duena)
    proveedor = _proveedor(client, duena)
    compra = _comprar(client, duena, proveedor["id"], producto["id"]).json()

    respuesta = client.post(
        f"/compras/{compra['id']}/anular",
        json={},
        headers=sesiones["vendedor"],
    )

    assert respuesta.status_code == 403


# --- la configuracion tiene efecto real ----------------------------------


def test_cambiar_el_umbral_cambia_el_estado_de_stock(client, sesiones):
    """El defecto que esta prueba fija.

    Antes, guardar un umbral respondia 200 y el panel seguia calculando
    con el valor del entorno: dos fuentes de verdad para el mismo numero.
    """
    duena = sesiones["propietario"]
    # 20 de 100 es 20%: con el umbral por defecto en 30, es "bajo".
    producto = _producto(client, duena, stock_actual=20, stock_inicial=100)
    antes = client.get(f"/productos/{producto['id']}", headers=duena).json()
    assert antes["estado_stock"] == "bajo"

    client.put(
        "/configuracion",
        json={"cambios": {"stock_umbral_bajo": "10"}},
        headers=duena,
    )

    despues = client.get(f"/productos/{producto['id']}", headers=duena).json()
    assert despues["estado_stock"] == "medio"


def test_cambiar_el_umbral_cambia_el_resumen_de_stock(client, sesiones):
    duena = sesiones["propietario"]
    _producto(client, duena, stock_actual=20, stock_inicial=100)

    client.put(
        "/configuracion",
        json={"cambios": {"stock_umbral_bajo": "10"}},
        headers=duena,
    )

    cuerpo = client.get("/stock/resumen", headers=duena).json()
    assert cuerpo["bajo"] == 0
    assert cuerpo["medio"] == 1


def test_cambiar_la_ventana_de_vencimiento_cambia_el_panel(client, sesiones):
    """RF-B04 con la ventana configurada, no la del entorno."""
    duena = sesiones["propietario"]
    hoy = tiempo.hoy()
    _producto(
        client,
        duena,
        nombre="Vence en 60 dias",
        fecha_vencimiento=(hoy + timedelta(days=60)).isoformat(),
    )
    antes = client.get("/panel", headers=duena).json()
    assert antes["proximos_a_vencer"] == []

    client.put(
        "/configuracion",
        json={"cambios": {"dias_aviso_vencimiento": "90"}},
        headers=duena,
    )

    despues = client.get("/panel", headers=duena).json()
    assert len(despues["proximos_a_vencer"]) == 1
    assert despues["dias_aviso_vencimiento"] == 90


def test_cambiar_el_tope_cambia_lo_que_puede_descontar_un_vendedor(
    client, sesiones
):
    """El tope de caja tambien sale de la configuracion."""
    duena = sesiones["propietario"]
    medios = _medios(client, duena)
    producto = _producto(client, duena)

    # 300 de 1200 es 25%: por encima del tope por defecto del 10%.
    def _vender_con_descuento():
        return client.post(
            "/ventas",
            json={
                "items": [{"id_producto": producto["id"], "cantidad": 1}],
                "id_medio_pago": medios["Efectivo"],
                "descuento": "300.00",
            },
            headers=sesiones["vendedor"],
        )

    assert _vender_con_descuento().status_code == 400

    client.put(
        "/configuracion",
        json={"cambios": {"descuento_max_vendedor": "30"}},
        headers=duena,
    )

    assert _vender_con_descuento().status_code == 201


def test_un_valor_guardado_ilegible_no_tumba_el_calculo(client, sesiones, db):
    """La base puede tener basura de una version anterior."""
    from app.models import Configuracion

    duena = sesiones["propietario"]
    producto = _producto(client, duena, stock_actual=20, stock_inicial=100)
    db.add(Configuracion(clave="stock_umbral_bajo", valor="no-es-un-numero"))
    db.commit()

    respuesta = client.get(f"/productos/{producto['id']}", headers=duena)

    # Cae al respaldo del entorno en lugar de estallar.
    assert respuesta.status_code == 200
    assert respuesta.json()["estado_stock"] == "bajo"
