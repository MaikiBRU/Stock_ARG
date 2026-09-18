"""La sesion viaja en una cookie que la pagina no puede leer.

Guardar el token en localStorage significa entregarlo entero al primer
XSS. La cookie es HttpOnly, asi que el JavaScript de la pagina no la ve,
y el token por cabecera se sigue aceptando para todo lo que no sea un
navegador.
"""

import pytest

from app.api import cookies
from app.core.config import get_settings
from app.core.security import crear_token, hash_contrasena
from app.models import Rol, Usuario
from app.services.limites import limitador

CLAVE = "Kiosco2026"


@pytest.fixture(autouse=True)
def _limites_limpios():
    limitador.reiniciar()
    yield
    limitador.reiniciar()


def _cuenta(db, email="ana@stockarg.com.ar", rol=Rol.PROPIETARIO):
    usuario = Usuario(
        email=email,
        nombre="Ana",
        password_hash=hash_contrasena(CLAVE),
        rol=rol,
        verificado=True,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    return usuario


def _ingresar(client, email="ana@stockarg.com.ar"):
    return client.post(
        "/auth/login", json={"email": email, "contrasena": CLAVE}
    )


def test_al_ingresar_queda_la_cookie_de_sesion(client, db):
    _cuenta(db)

    respuesta = _ingresar(client)

    galleta = respuesta.headers["set-cookie"]
    assert cookies.NOMBRE in galleta
    assert "HttpOnly" in galleta
    assert "SameSite=lax" in galleta
    assert client.cookies[cookies.NOMBRE] == respuesta.json()["access_token"]


def test_la_cookie_sola_alcanza_para_entrar(client, db):
    _cuenta(db)
    _ingresar(client)

    # Sin cabecera: el navegador solo manda la cookie.
    perfil = client.get("/auth/perfil")

    assert perfil.status_code == 200
    assert perfil.json()["email"] == "ana@stockarg.com.ar"


def test_sin_cookie_ni_cabecera_no_se_entra(client, db):
    _cuenta(db)

    assert client.get("/auth/perfil").status_code == 401


def test_la_cabecera_gana_sobre_la_cookie(client, db):
    """Una cookie vieja no puede tapar un token puesto a proposito."""
    _cuenta(db)
    otra = _cuenta(db, email="otra@stockarg.com.ar", rol=Rol.VENDEDOR)
    _ingresar(client)
    token_de_otra = crear_token(str(otra.id), rol=otra.rol.value)

    perfil = client.get(
        "/auth/perfil", headers={"Authorization": f"Bearer {token_de_otra}"}
    )

    assert perfil.json()["email"] == "otra@stockarg.com.ar"


def test_cerrar_sesion_borra_la_cookie(client, db):
    _cuenta(db)
    _ingresar(client)

    salida = client.post("/auth/logout")

    assert salida.status_code == 200
    assert client.cookies.get(cookies.NOMBRE) is None
    assert client.get("/auth/perfil").status_code == 401


def test_cambiar_la_contrasena_renueva_la_cookie(client, db):
    _cuenta(db)
    _ingresar(client)
    anterior = client.cookies[cookies.NOMBRE]

    client.put(
        "/auth/contrasena",
        json={"contrasena_actual": CLAVE, "contrasena_nueva": "NuevaClave9"},
    )

    assert client.cookies[cookies.NOMBRE] != anterior
    assert client.get("/auth/perfil").status_code == 200


def test_en_desarrollo_la_cookie_no_es_segura(client, db):
    """En desarrollo la API es http: una cookie Secure no viajaria."""
    _cuenta(db)

    galleta = _ingresar(client).headers["set-cookie"]

    assert "Secure" not in galleta


def test_en_produccion_la_cookie_es_segura(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    _cuenta(db)

    galleta = _ingresar(client).headers["set-cookie"]

    assert "Secure" in galleta


def test_la_demo_tambien_entra_por_cookie(client):
    creada = client.post("/demo/sesion")
    assert creada.status_code == 201

    galleta = creada.headers["set-cookie"]
    assert cookies.NOMBRE in galleta
    assert "HttpOnly" in galleta
    assert client.get("/productos").status_code == 200

    client.post("/demo/sesion/terminar")

    assert client.cookies.get(cookies.NOMBRE) is None
    assert client.get("/productos").status_code == 401
