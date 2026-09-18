"""Demo publica: sandboxes anonimos, aislados y temporales (modulo J)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select

from app.core import tiempo
from app.core.config import get_settings
from app.core.security import crear_token, hash_opaco
from app.models import (
    MovimientoStock,
    Producto,
    SesionDemo,
    Usuario,
    Venta,
)
from app.services import demo_semilla
from app.services.limites import limitador

PRODUCTO = {
    "nombre": "Invento del visitante",
    "precio_venta": "10.00",
    "precio_costo": "5.00",
}


@pytest.fixture(autouse=True)
def _limites_limpios():
    """El limitador vive en el proceso: no se arrastra entre pruebas."""
    limitador.reiniciar()
    yield
    limitador.reiniciar()


def _cabecera(token):
    return {"Authorization": f"Bearer {token}"}


def _nueva_demo(client, ip="203.0.113.1"):
    respuesta = client.post("/demo/sesion", headers={"X-Forwarded-For": ip})
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    return cuerpo, _cabecera(cuerpo["access_token"])


def _sid(token):
    return jwt.decode(token, options={"verify_signature": False})["sid"]


def _filas(db, modelo, sid):
    return db.scalar(
        select(func.count())
        .select_from(modelo)
        .where(modelo.id_sesion_demo == sid)
    )


def _items(client, cabecera):
    return client.get("/productos?limite=100", headers=cabecera).json()["items"]


# --- alta y semilla (RF-J01, RF-J02) -------------------------------------


def test_crear_la_demo_no_pide_credenciales_y_da_un_token_de_demo(client):
    cuerpo, _ = _nueva_demo(client)

    carga = jwt.decode(
        cuerpo["access_token"],
        get_settings().secret_key,
        algorithms=["HS256"],
    )
    assert carga["typ"] == "demo"
    assert carga["sub"] == f"demo:{carga['sid']}"
    assert cuerpo["usuario"]["rol"] == "propietario"
    assert set(cuerpo["roles"]) == {"propietario", "encargado", "vendedor"}


def test_el_sandbox_nace_con_un_kiosco_verosimil(client):
    _, cabecera = _nueva_demo(client)

    productos = client.get("/productos?limite=100", headers=cabecera).json()
    assert productos["total"] >= 30
    assert all(float(p["precio_venta"]) > 0 for p in productos["items"])
    assert len(client.get("/categorias", headers=cabecera).json()) >= 5
    assert client.get("/proveedores", headers=cabecera).json()["total"] >= 5
    assert client.get("/clientes", headers=cabecera).json()["total"] >= 10
    assert client.get("/compras", headers=cabecera).json()["total"] >= 3
    assert client.get("/ventas", headers=cabecera).json()["total"] >= 60

    hoy = tiempo.hoy()
    tres_semanas = client.get(
        f"/reportes/ventas?desde={hoy - timedelta(days=20)}&hasta={hoy}",
        headers=cabecera,
    ).json()
    assert tres_semanas["cantidad_ventas"] >= 60

    panel = client.get("/panel", headers=cabecera)
    assert panel.status_code == 200
    # Hay algo para mostrar en cada alerta del panel.
    assert panel.json()["bajo_minimo"]
    assert panel.json()["proximos_a_vencer"]
    assert panel.json()["vencidos"]


def test_el_stock_de_la_semilla_cuadra_con_sus_movimientos(client, db):
    """Todo entra por compras y sale por ventas: nada aparece de la nada."""
    cuerpo, _ = _nueva_demo(client)
    sid = _sid(cuerpo["access_token"])

    for producto in db.scalars(
        select(Producto).where(Producto.id_sesion_demo == sid)
    ):
        ultimo = db.scalars(
            select(MovimientoStock)
            .where(MovimientoStock.id_producto == producto.id)
            .order_by(MovimientoStock.id.desc())
        ).first()
        assert ultimo is not None
        assert ultimo.stock_resultante == producto.stock_actual


def test_ninguna_venta_de_la_semilla_queda_en_el_futuro(client, db):
    cuerpo, _ = _nueva_demo(client)
    sid = _sid(cuerpo["access_token"])

    ultima = db.scalar(
        select(func.max(Venta.fecha_hora)).where(Venta.id_sesion_demo == sid)
    )
    assert ultima.replace(tzinfo=UTC) <= datetime.now(UTC)


def test_dos_visitantes_no_ven_los_mismos_numeros(client):
    _, cabecera_a = _nueva_demo(client, "203.0.113.1")
    _, cabecera_b = _nueva_demo(client, "203.0.113.2")

    codigos_a = {p["codigo_barra"] for p in _items(client, cabecera_a)}
    codigos_b = {p["codigo_barra"] for p in _items(client, cabecera_b)}

    assert codigos_a != codigos_b


def test_una_falla_al_sembrar_no_deja_un_sandbox_a_medias(
    client, db, monkeypatch
):
    """La falla llega despues de escribir usuarios, productos y ventas."""

    def _romper(*_args, **_kwargs):
        raise RuntimeError("semilla rota")

    monkeypatch.setattr(demo_semilla, "_anular_una_venta", _romper)

    with pytest.raises(RuntimeError):
        client.post("/demo/sesion")

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(SesionDemo)) == 0
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert db.scalar(select(func.count()).select_from(Venta)) == 0


# --- aislamiento (RF-J03, RF-J04) ----------------------------------------


def test_un_sandbox_no_alcanza_los_registros_de_otro(client):
    _, cabecera_a = _nueva_demo(client, "203.0.113.1")
    _, cabecera_b = _nueva_demo(client, "203.0.113.2")

    ids_a = {p["id"] for p in _items(client, cabecera_a)}
    ids_b = {p["id"] for p in _items(client, cabecera_b)}
    assert ids_a.isdisjoint(ids_b)

    ajeno = min(ids_a)
    # 404 y no 403: la respuesta no confirma que el registro existe.
    ruta = f"/productos/{ajeno}"
    assert client.get(ruta, headers=cabecera_b).status_code == 404
    assert (
        client.put(ruta, json=PRODUCTO, headers=cabecera_b).status_code == 404
    )
    assert client.delete(ruta, headers=cabecera_b).status_code == 404


def test_la_demo_y_la_aplicacion_no_se_ven(client, sesiones):
    real = client.post(
        "/productos",
        json={**PRODUCTO, "nombre": "Producto real"},
        headers=sesiones["propietario"],
    )
    assert real.status_code == 201
    id_real = real.json()["id"]

    _, cabecera = _nueva_demo(client)

    assert "Producto real" not in [
        p["nombre"] for p in _items(client, cabecera)
    ]
    assert (
        client.get(f"/productos/{id_real}", headers=cabecera).status_code == 404
    )

    aplicacion = _items(client, sesiones["propietario"])
    assert [p["nombre"] for p in aplicacion] == ["Producto real"]
    ventas = client.get("/ventas", headers=sesiones["propietario"]).json()
    assert ventas["total"] == 0


def test_la_auditoria_de_la_demo_y_la_de_la_aplicacion_no_se_mezclan(
    client, sesiones
):
    alta = {
        "email": "nueva@stockarg.com.ar",
        "nombre": "Nueva",
        "contrasena": "Kiosco2026",
        "rol": "vendedor",
    }
    propietario = sesiones["propietario"]
    assert (
        client.post("/usuarios", json=alta, headers=propietario).status_code
        == 201
    )
    _, cabecera = _nueva_demo(client)

    assert client.get("/auditoria", headers=cabecera).json()["total"] == 0

    assert (
        client.post("/usuarios", json=alta, headers=cabecera).status_code == 201
    )
    assert client.get("/auditoria", headers=cabecera).json()["total"] == 1
    assert client.get("/auditoria", headers=propietario).json()["total"] == 1


def test_la_configuracion_de_la_demo_no_alcanza_a_la_aplicacion(
    client, sesiones
):
    _, cabecera = _nueva_demo(client)

    guardada = client.put(
        "/configuracion",
        json={"cambios": {"descuento_max_vendedor": "100"}},
        headers=cabecera,
    )
    assert guardada.status_code == 200

    aplicacion = client.get("/configuracion", headers=sesiones["propietario"])
    assert aplicacion.json()["valores"]["descuento_max_vendedor"] != "100"


# --- vigencia (RF-J05) ---------------------------------------------------


def test_una_sesion_vencida_deja_de_servir_en_el_acto(client, db):
    cuerpo, cabecera = _nueva_demo(client)
    sesion = db.get(SesionDemo, _sid(cuerpo["access_token"]))
    sesion.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert client.get("/productos", headers=cabecera).status_code == 401


def test_una_sesion_inactiva_deja_de_servir(client, db):
    cuerpo, cabecera = _nueva_demo(client)
    sesion = db.get(SesionDemo, _sid(cuerpo["access_token"]))
    inactividad = get_settings().demo_idle_timeout_minutes
    sesion.ultima_actividad = datetime.now(UTC) - timedelta(
        minutes=inactividad, seconds=1
    )
    db.commit()

    assert client.get("/productos", headers=cabecera).status_code == 401


def test_usar_la_demo_la_mantiene_viva(client, db):
    cuerpo, cabecera = _nueva_demo(client)
    sesion = db.get(SesionDemo, _sid(cuerpo["access_token"]))
    hace_un_rato = datetime.now(UTC) - timedelta(minutes=5)
    sesion.ultima_actividad = hace_un_rato
    db.commit()

    assert client.get("/productos", headers=cabecera).status_code == 200

    db.refresh(sesion)
    assert sesion.ultima_actividad.replace(tzinfo=UTC) > hace_un_rato


def test_tokens_invalidos_reciben_todos_la_misma_respuesta(client, db):
    """Probar tokens no revela si una sesion existio."""
    vencida, _ = _nueva_demo(client, "203.0.113.1")
    sesion_vencida = db.get(SesionDemo, _sid(vencida["access_token"]))
    sesion_vencida.expira_en = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    viva, _ = _nueva_demo(client, "203.0.113.2")
    sid = _sid(viva["access_token"])

    candidatos = [
        vencida["access_token"],
        crear_token(
            "demo:inventada", tipo="demo", sid="inventada", rol="propietario"
        ),
        crear_token(f"demo:{sid}", tipo="demo", sid=sid, rol="rey"),
        crear_token("demo:otra", tipo="demo", sid=sid, rol="propietario"),
        jwt.encode(
            {
                "sub": f"demo:{sid}",
                "typ": "demo",
                "sid": sid,
                "rol": "propietario",
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            "otra-clave-que-no-es-la-de-la-aplicacion",
            algorithm="HS256",
        ),
    ]
    respuestas = [
        client.get("/productos", headers=_cabecera(token))
        for token in candidatos
    ]

    assert {r.status_code for r in respuestas} == {401}
    assert len({r.text for r in respuestas}) == 1


def test_cerrar_sesion_en_la_demo_invalida_el_token(client):
    _, cabecera = _nueva_demo(client)

    assert client.post("/auth/logout", headers=cabecera).status_code == 200
    assert client.get("/productos", headers=cabecera).status_code == 401


# --- roles ---------------------------------------------------------------


def test_se_puede_recorrer_la_demo_con_cada_rol(client):
    _, cabecera = _nueva_demo(client)

    respuesta = client.post(
        "/demo/sesion/rol", json={"rol": "vendedor"}, headers=cabecera
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["usuario"]["rol"] == "vendedor"
    vendedor = _cabecera(respuesta.json()["access_token"])

    rentabilidad = "/reportes/rentabilidad"
    assert client.get(rentabilidad, headers=vendedor).status_code == 403
    assert client.get(rentabilidad, headers=cabecera).status_code == 200
    visto = client.get("/productos?limite=1", headers=vendedor).json()
    assert visto["items"][0]["precio_costo"] is None


def test_cambiar_de_rol_no_acepta_campos_de_mas(client):
    _, cabecera = _nueva_demo(client)

    respuesta = client.post(
        "/demo/sesion/rol",
        json={"rol": "vendedor", "id_usuario": 1},
        headers=cabecera,
    )

    assert respuesta.status_code == 422


def test_la_demo_no_cambia_contrasenas(client):
    _, cabecera = _nueva_demo(client)

    respuesta = client.put(
        "/auth/contrasena",
        json={
            "contrasena_actual": "Algo12345",
            "contrasena_nueva": "Otra12345",
        },
        headers=cabecera,
    )

    assert respuesta.status_code == 403


def test_el_estado_de_la_demo_es_solo_para_la_demo(client, sesiones):
    respuesta = client.get("/demo/sesion", headers=sesiones["propietario"])

    assert respuesta.status_code == 404


def test_el_estado_de_la_demo_informa_tiempo_y_cupos(client):
    _, cabecera = _nueva_demo(client)

    estado = client.get("/demo/sesion", headers=cabecera).json()

    ttl = get_settings().demo_session_ttl_minutes * 60
    assert 0 < estado["segundos_restantes"] <= ttl
    assert estado["rol"] == "propietario"
    assert estado["cupos"]["productos"]["usados"] >= 30
    assert estado["cupos"]["exportaciones"]["usados"] == 0


# --- cupos (RF-J06) ------------------------------------------------------


def test_el_cupo_de_exportaciones_corta_con_429(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_max_exportaciones", 2)
    _, cabecera = _nueva_demo(client)

    assert (
        client.get("/productos/exportar", headers=cabecera).status_code == 200
    )
    assert client.get("/ventas/exportar", headers=cabecera).status_code == 200
    tercera = client.get("/clientes/exportar", headers=cabecera)

    assert tercera.status_code == 429
    assert tercera.json()["detail"]["codigo"] == "cupo_agotado"
    assert tercera.json()["detail"]["recurso"] == "exportaciones"


def test_el_cupo_de_la_demo_no_alcanza_a_la_aplicacion(
    client, sesiones, monkeypatch
):
    monkeypatch.setattr(get_settings(), "demo_max_exportaciones", 1)

    for _ in range(3):
        respuesta = client.get(
            "/productos/exportar", headers=sesiones["propietario"]
        )
        assert respuesta.status_code == 200


def test_previsualizar_una_importacion_cuenta_para_el_cupo(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_max_importaciones", 1)
    _, cabecera = _nueva_demo(client)
    archivo = {"archivo": ("p.csv", b"nombre;precio_venta\nAlfajor;100\n")}
    ruta = "/productos/importar/previsualizar"

    primera = client.post(ruta, files=archivo, headers=cabecera)
    segunda = client.post(ruta, files=archivo, headers=cabecera)

    assert primera.status_code != 429
    assert segunda.status_code == 429


def test_el_tope_de_filas_corta_cualquier_alta(client, monkeypatch):
    _, cabecera = _nueva_demo(client)
    ya_hay = client.get("/productos?limite=1", headers=cabecera).json()["total"]
    monkeypatch.setattr(get_settings(), "demo_max_productos", ya_hay)

    respuesta = client.post("/productos", json=PRODUCTO, headers=cabecera)

    assert respuesta.status_code == 429
    assert respuesta.json()["detail"]["recurso"] == "productos"
    # La peticion rechazada no dejo nada escrito.
    despues = client.get("/productos?limite=1", headers=cabecera).json()
    assert despues["total"] == ya_hay


# --- abuso (RF-J07) ------------------------------------------------------


def test_limite_de_demos_por_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_rate_limit_per_hour", 2)

    for _ in range(2):
        _nueva_demo(client, "203.0.113.9")
    excedida = client.post(
        "/demo/sesion", headers={"X-Forwarded-For": "203.0.113.9"}
    )

    assert excedida.status_code == 429
    _nueva_demo(client, "203.0.113.10")


def test_la_ip_se_guarda_hasheada(client, db):
    cuerpo, _ = _nueva_demo(client, "203.0.113.20")

    sesion = db.get(SesionDemo, _sid(cuerpo["access_token"]))

    assert sesion.ip_hash == hash_opaco("203.0.113.20")
    assert "203.0.113.20" not in sesion.ip_hash


def test_tope_global_de_sesiones_activas(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_max_active_sessions", 1)
    primera, _ = _nueva_demo(client, "203.0.113.1")

    llena = client.post(
        "/demo/sesion", headers={"X-Forwarded-For": "203.0.113.2"}
    )
    assert llena.status_code == 503

    # Una sesion vencida no ocupa lugar aunque sus filas sigan ahi.
    sesion = db.get(SesionDemo, _sid(primera["access_token"]))
    sesion.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    _nueva_demo(client, "203.0.113.3")


# --- reinicio y fin (RF-J08) ---------------------------------------------


def test_reiniciar_vuelve_a_cero_sin_cambiar_de_token(client):
    _, cabecera = _nueva_demo(client)
    assert (
        client.post("/productos", json=PRODUCTO, headers=cabecera).status_code
        == 201
    )

    reinicio = client.post("/demo/sesion/reiniciar", headers=cabecera)
    assert reinicio.status_code == 200

    nombres = [p["nombre"] for p in _items(client, cabecera)]
    assert "Invento del visitante" not in nombres
    assert len(nombres) >= 30


def test_reiniciar_no_estira_el_vencimiento_ni_devuelve_cupos(client, db):
    cuerpo, cabecera = _nueva_demo(client)
    sid = _sid(cuerpo["access_token"])
    assert (
        client.get("/productos/exportar", headers=cabecera).status_code == 200
    )
    db.expire_all()
    antes = db.get(SesionDemo, sid).expira_en

    client.post("/demo/sesion/reiniciar", headers=cabecera)

    db.expire_all()
    despues = db.get(SesionDemo, sid)
    assert despues.expira_en == antes
    assert despues.exportaciones == 1


def test_reiniciar_tiene_un_limite(client, monkeypatch):
    from app.api.routes import demo as rutas

    monkeypatch.setattr(rutas, "MAX_REINICIOS_POR_HORA", 1)
    _, cabecera = _nueva_demo(client)
    ruta = "/demo/sesion/reiniciar"

    assert client.post(ruta, headers=cabecera).status_code == 200
    assert client.post(ruta, headers=cabecera).status_code == 429


def test_terminar_borra_todo_y_corta_el_token(client, db):
    cuerpo, cabecera = _nueva_demo(client)
    sid = _sid(cuerpo["access_token"])

    terminada = client.post("/demo/sesion/terminar", headers=cabecera)
    assert terminada.status_code == 200

    db.expire_all()
    assert db.get(SesionDemo, sid) is None
    for modelo in (Usuario, Producto, Venta, MovimientoStock):
        assert _filas(db, modelo, sid) == 0
    assert client.get("/productos", headers=cabecera).status_code == 401


# --- limpieza (RF-J09) ---------------------------------------------------


def test_la_limpieza_manual_no_existe_sin_token_configurado(client):
    respuesta = client.post(
        "/demo/mantenimiento/limpieza",
        headers={"X-Demo-Mantenimiento-Token": "cualquiera"},
    )

    assert respuesta.status_code == 404


def test_la_limpieza_borra_solo_lo_vencido(client, db, sesiones, monkeypatch):
    clave = "t" * 40
    monkeypatch.setattr(get_settings(), "demo_maintenance_token", clave)
    viva, cabecera_viva = _nueva_demo(client, "203.0.113.1")
    vencida, _ = _nueva_demo(client, "203.0.113.2")
    sid_vencida = _sid(vencida["access_token"])
    sesion = db.get(SesionDemo, sid_vencida)
    sesion.expira_en = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    real = client.post(
        "/productos",
        json={**PRODUCTO, "nombre": "Producto real"},
        headers=sesiones["propietario"],
    )
    assert real.status_code == 201
    ruta = "/demo/mantenimiento/limpieza"

    equivocada = client.post(
        ruta, headers={"X-Demo-Mantenimiento-Token": "x" * 40}
    )
    assert equivocada.status_code == 404

    primera = client.post(ruta, headers={"X-Demo-Mantenimiento-Token": clave})
    segunda = client.post(ruta, headers={"X-Demo-Mantenimiento-Token": clave})

    assert primera.json() == {"eliminadas": 1}
    assert segunda.json() == {"eliminadas": 0}
    db.expire_all()
    assert _filas(db, Producto, sid_vencida) == 0
    assert db.get(SesionDemo, _sid(viva["access_token"])) is not None
    assert client.get("/productos", headers=cabecera_viva).status_code == 200
    aplicacion = client.get("/productos", headers=sesiones["propietario"])
    assert aplicacion.json()["total"] == 1


def test_la_limpieza_no_se_rompe_con_una_cabecera_rara(client, monkeypatch):
    """Un caracter no ASCII no puede convertir el rechazo en un 500."""
    monkeypatch.setattr(get_settings(), "demo_maintenance_token", "t" * 40)

    respuesta = client.post(
        "/demo/mantenimiento/limpieza",
        headers={"X-Demo-Mantenimiento-Token": "ñ".encode("latin-1") * 40},
    )

    assert respuesta.status_code == 404


def test_toda_exportacion_o_importacion_consume_cupo():
    """Una ruta nueva que exporte o importe no puede olvidarse del cupo.

    Recorre todos los modulos de rutas, asi que tambien alcanza a los que
    se agreguen despues.
    """
    import importlib
    import pkgutil

    import app.api.routes as paquete
    from app.api import deps

    cupos = {deps.cupo_de_exportacion, deps.cupo_de_importacion}
    marcas = ("exportar", "importar", "comprobante")
    revisadas = []
    for modulo in pkgutil.iter_modules(paquete.__path__):
        rutas = importlib.import_module(f"{paquete.__name__}.{modulo.name}")
        router = getattr(rutas, "router", None)
        for ruta in router.routes if router else ():
            if not any(marca in ruta.path for marca in marcas):
                continue
            revisadas.append(ruta.path)
            llamadas = {
                dependencia.dependency for dependencia in ruta.dependencies
            }
            assert llamadas & cupos, f"{ruta.path} no consume cupo de la demo"

    assert len(revisadas) >= 13


# --- interruptor (RF-J11) ------------------------------------------------


def test_apagar_la_demo_la_hace_desaparecer(client, monkeypatch):
    _, cabecera = _nueva_demo(client)
    monkeypatch.setattr(get_settings(), "demo_enabled", False)

    assert client.post("/demo/sesion").status_code == 404
    assert client.get("/demo/sesion", headers=cabecera).status_code == 404
    assert client.get("/productos", headers=cabecera).status_code == 401
