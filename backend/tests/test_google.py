"""Ingreso con Google (RF-A03).

Google firma el token de identidad y su libreria verifica firma, emisor,
destinatario y vencimiento. Estas pruebas cubren lo que decide la
aplicacion: a que cuenta entra, cuando la crea y cuando dice que no.
"""

import pytest
from google.oauth2 import id_token as id_token_de_google

from app.core.config import get_settings
from app.core.security import hash_contrasena
from app.models import Rol, Usuario
from app.services.limites import limitador

CLIENTE = "123456789.apps.googleusercontent.com"
PERFIL = {
    "iss": "https://accounts.google.com",
    "sub": "1234567890",
    "email": "ana@stockarg.com.ar",
    "email_verified": True,
    "name": "Ana Gomez",
}


@pytest.fixture(autouse=True)
def _limites_limpios():
    limitador.reiniciar()
    yield
    limitador.reiniciar()


@pytest.fixture
def google_configurado(monkeypatch):
    """Con el identificador de cliente cargado, la ruta responde."""
    monkeypatch.setattr(get_settings(), "google_client_id", CLIENTE)


@pytest.fixture
def credencial_valida(monkeypatch, google_configurado):
    """Google valida el token y devuelve este perfil."""

    def _verificar(credencial, peticion, cliente, **extra):
        assert cliente == CLIENTE
        return dict(PERFIL)

    monkeypatch.setattr(id_token_de_google, "verify_oauth2_token", _verificar)


def _entrar(client, credencial="token-de-google"):
    return client.post("/auth/google", json={"credential": credencial})


def test_sin_configurar_google_el_ingreso_no_esta_disponible(client):
    respuesta = _entrar(client)

    assert respuesta.status_code == 503


def test_la_primera_cuenta_por_google_queda_como_propietaria(
    client, db, credencial_valida
):
    respuesta = _entrar(client)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario"]["email"] == "ana@stockarg.com.ar"
    assert cuerpo["usuario"]["rol"] == "propietario"
    # La pantalla usa esto para ofrecerle ponerse una contrasena.
    assert cuerpo["sin_contrasena"] is True

    usuario = db.query(Usuario).one()
    assert usuario.verificado is True
    assert usuario.password_hash is None
    assert usuario.google_id == PERFIL["sub"]


def test_el_token_que_devuelve_sirve_para_la_aplicacion(
    client, credencial_valida
):
    token = _entrar(client).json()["access_token"]

    perfil = client.get(
        "/auth/perfil", headers={"Authorization": f"Bearer {token}"}
    )

    assert perfil.status_code == 200
    assert perfil.json()["email"] == "ana@stockarg.com.ar"


def test_entrar_dos_veces_no_duplica_la_cuenta(client, db, credencial_valida):
    _entrar(client)
    _entrar(client)

    assert db.query(Usuario).count() == 1


def test_una_cuenta_con_contrasena_se_vincula_en_lugar_de_duplicarse(
    client, db, credencial_valida
):
    """Dos cuentas para la misma persona parten su historial al medio."""
    db.add(
        Usuario(
            email="ana@stockarg.com.ar",
            nombre="Ana",
            password_hash=hash_contrasena("Kiosco2026"),
            rol=Rol.ENCARGADO,
            verificado=True,
            activo=True,
        )
    )
    db.commit()

    respuesta = _entrar(client)

    assert respuesta.status_code == 200
    assert respuesta.json()["sin_contrasena"] is False
    # Conserva su rol: entrar con Google no promueve a nadie.
    assert respuesta.json()["usuario"]["rol"] == "encargado"
    usuario = db.query(Usuario).one()
    assert usuario.google_id == PERFIL["sub"]


def test_una_cuenta_sin_verificar_queda_verificada(
    client, db, credencial_valida
):
    db.add(
        Usuario(
            email="ana@stockarg.com.ar",
            nombre="Ana",
            password_hash=hash_contrasena("Kiosco2026"),
            rol=Rol.VENDEDOR,
            verificado=False,
            activo=True,
        )
    )
    db.commit()

    assert _entrar(client).status_code == 200
    assert db.query(Usuario).one().verificado is True


def test_una_cuenta_deshabilitada_no_entra_por_google(
    client, db, credencial_valida
):
    db.add(
        Usuario(
            email="ana@stockarg.com.ar",
            nombre="Ana",
            rol=Rol.VENDEDOR,
            google_id=PERFIL["sub"],
            verificado=True,
            activo=False,
        )
    )
    db.commit()

    assert _entrar(client).status_code == 401


def test_otra_cuenta_de_google_con_el_mismo_correo_no_toma_la_cuenta(
    client, db, credencial_valida
):
    db.add(
        Usuario(
            email="ana@stockarg.com.ar",
            nombre="Ana",
            rol=Rol.PROPIETARIO,
            google_id="otro-identificador",
            verificado=True,
            activo=True,
        )
    )
    db.commit()

    respuesta = _entrar(client)

    assert respuesta.status_code == 401
    assert db.query(Usuario).one().google_id == "otro-identificador"


def test_una_credencial_que_google_rechaza_no_entra(
    client, monkeypatch, google_configurado
):
    def _rechazar(*_args, **_kwargs):
        raise ValueError("Token expired")

    monkeypatch.setattr(id_token_de_google, "verify_oauth2_token", _rechazar)

    assert _entrar(client).status_code == 401


def test_un_correo_sin_verificar_en_google_no_entra(
    client, db, monkeypatch, google_configurado
):
    """Una cuenta de Google puede tener un correo que nadie confirmo."""

    def _sin_verificar(*_args, **_kwargs):
        return {**PERFIL, "email_verified": False}

    monkeypatch.setattr(
        id_token_de_google, "verify_oauth2_token", _sin_verificar
    )

    assert _entrar(client).status_code == 401
    assert db.query(Usuario).count() == 0


def test_un_emisor_que_no_es_google_no_entra(
    client, db, monkeypatch, google_configurado
):
    def _otro_emisor(*_args, **_kwargs):
        return {**PERFIL, "iss": "https://ejemplo.invalido"}

    monkeypatch.setattr(id_token_de_google, "verify_oauth2_token", _otro_emisor)

    assert _entrar(client).status_code == 401
    assert db.query(Usuario).count() == 0


def test_el_cuerpo_no_admite_campos_de_mas(client, credencial_valida):
    respuesta = client.post(
        "/auth/google",
        json={"credential": "token-de-google", "rol": "propietario"},
    )

    assert respuesta.status_code == 422


def test_el_ingreso_con_google_tiene_limite_por_ip(
    client, monkeypatch, credencial_valida
):
    monkeypatch.setattr(get_settings(), "login_max_intentos_por_ip", 2)

    for _ in range(2):
        assert _entrar(client).status_code == 200

    assert _entrar(client).status_code == 429
