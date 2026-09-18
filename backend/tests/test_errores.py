"""Un error inesperado no se pierde ni cuenta de mas (RF-I05).

El panel de administracion no tiene una pantalla de logs aparte: los
errores de la aplicacion entran en la misma auditoria que el resto, con
entidad "sistema". Asi se ven junto a lo que estaba pasando cuando el
error ocurrio.
"""

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import crear_app
from app.models import Auditoria


@pytest.fixture
def cliente_que_explota(db):
    """Una app igual a la real, con una ruta que falla."""
    app = crear_app()
    app.dependency_overrides[get_db] = lambda: db
    app.state.sesion_de_sistema = lambda: db

    @app.get("/explotar")
    def explotar() -> dict:
        raise RuntimeError("se rompio con el correo ana@stockarg.com.ar")

    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente


def test_un_error_inesperado_responde_500_con_una_referencia(
    cliente_que_explota,
):
    respuesta = cliente_que_explota.get("/explotar")

    assert respuesta.status_code == 500
    detalle = respuesta.json()["detail"]
    assert detalle["codigo"] == "error_no_controlado"
    assert len(detalle["referencia"]) == 16


def test_el_error_queda_en_la_auditoria_como_sistema(cliente_que_explota, db):
    respuesta = cliente_que_explota.get("/explotar")
    referencia = respuesta.json()["detail"]["referencia"]

    linea = db.query(Auditoria).one()

    assert linea.entidad == "sistema"
    assert linea.accion == "error.no_controlado"
    assert linea.id_entidad == referencia
    assert linea.detalle["ruta"] == "/explotar"
    assert linea.detalle["metodo"] == "GET"
    assert linea.detalle["tipo"] == "RuntimeError"


def test_la_auditoria_no_guarda_el_mensaje_del_error(cliente_que_explota, db):
    """El mensaje puede traer datos de la operacion que fallo."""
    cliente_que_explota.get("/explotar")

    linea = db.query(Auditoria).one()

    escrito = str(linea.detalle) + str(linea.id_entidad)
    assert "ana@stockarg.com.ar" not in escrito
    assert "se rompio" not in escrito


def test_el_propietario_ve_los_errores_en_el_panel(
    cliente_que_explota, client, sesiones
):
    cliente_que_explota.get("/explotar")

    pagina = client.get(
        "/auditoria?entidad=sistema", headers=sesiones["propietario"]
    ).json()

    assert pagina["total"] == 1
    assert pagina["items"][0]["accion"] == "error.no_controlado"


def test_una_ruta_que_anda_no_deja_lineas_de_sistema(
    cliente_que_explota, client, sesiones
):
    assert client.get("/salud").status_code == 200

    pagina = client.get(
        "/auditoria?entidad=sistema", headers=sesiones["propietario"]
    ).json()

    assert pagina["total"] == 0
