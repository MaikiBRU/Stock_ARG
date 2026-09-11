"""Flujo de cuentas: alta, verificacion, ingreso y contrasena."""

import pytest

from app.core.security import hash_contrasena
from app.models import Rol, Usuario
from app.services.limites import limitador

CLAVE = "Kiosco2026"


@pytest.fixture(autouse=True)
def _sin_limites():
    """Los limites por IP no deben arrastrarse entre pruebas."""
    limitador.reiniciar()
    yield
    limitador.reiniciar()


@pytest.fixture
def correos(monkeypatch):
    """Intercepta los envios y guarda lo que se habria mandado."""
    enviados: list[tuple[str, str]] = []

    def _capturar(destinatario, valor):
        enviados.append((destinatario, valor))

    monkeypatch.setattr(
        "app.api.routes.auth.correo.enviar_codigo_de_verificacion",
        _capturar,
    )
    monkeypatch.setattr(
        "app.api.routes.auth.correo.enviar_enlace_de_recuperacion",
        _capturar,
    )
    return enviados


def _registrar(client, correos, email="ana@stockarg.com.ar", nombre="Ana"):
    respuesta = client.post(
        "/auth/registro",
        json={"email": email, "nombre": nombre, "contrasena": CLAVE},
    )
    assert respuesta.status_code == 201
    return correos[-1][1]


def _cuenta_lista(client, correos, email="ana@stockarg.com.ar"):
    """Registra y verifica una cuenta; devuelve su token."""
    codigo = _registrar(client, correos, email)
    respuesta = client.post(
        "/auth/verificar", json={"email": email, "codigo": codigo}
    )
    assert respuesta.status_code == 200
    return respuesta.json()["access_token"]


def _cabecera(token):
    return {"Authorization": f"Bearer {token}"}


# --- alta y verificacion (RF-A01) ---------------------------------------


def test_el_alta_envia_un_codigo_de_seis_digitos(client, correos):
    codigo = _registrar(client, correos)

    assert len(codigo) == 6
    assert codigo.isdigit()


def test_la_cuenta_nace_sin_verificar(client, correos, db):
    _registrar(client, correos)

    usuario = db.query(Usuario).filter_by(email="ana@stockarg.com.ar").one()
    assert usuario.verificado is False


def test_el_primer_usuario_queda_como_propietario(client, correos, db):
    """Si todos nacieran vendedores, nadie podria administrar."""
    _cuenta_lista(client, correos)

    usuario = db.query(Usuario).filter_by(email="ana@stockarg.com.ar").one()
    assert usuario.rol is Rol.PROPIETARIO


def test_el_segundo_usuario_queda_como_vendedor(client, correos, db):
    _cuenta_lista(client, correos, "ana@stockarg.com.ar")
    _cuenta_lista(client, correos, "beto@stockarg.com.ar")

    segundo = db.query(Usuario).filter_by(email="beto@stockarg.com.ar").one()
    assert segundo.rol is Rol.VENDEDOR


def test_verificar_deja_la_sesion_iniciada(client, correos):
    codigo = _registrar(client, correos)

    respuesta = client.post(
        "/auth/verificar",
        json={"email": "ana@stockarg.com.ar", "codigo": codigo},
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["access_token"]
    assert cuerpo["usuario"]["email"] == "ana@stockarg.com.ar"


def test_un_codigo_equivocado_no_verifica(client, correos):
    _registrar(client, correos)

    respuesta = client.post(
        "/auth/verificar",
        json={"email": "ana@stockarg.com.ar", "codigo": "000000"},
    )

    assert respuesta.status_code == 400


def test_el_codigo_sirve_una_sola_vez(client, correos):
    codigo = _registrar(client, correos)
    client.post(
        "/auth/verificar",
        json={"email": "ana@stockarg.com.ar", "codigo": codigo},
    )

    segunda = client.post(
        "/auth/verificar",
        json={"email": "ana@stockarg.com.ar", "codigo": codigo},
    )

    assert segunda.status_code == 400


def test_el_codigo_se_agota_tras_varios_intentos(client, correos):
    """Seis digitos se prueban enteros si no hay tope."""
    codigo = _registrar(client, correos)

    for _ in range(6):
        client.post(
            "/auth/verificar",
            json={"email": "ana@stockarg.com.ar", "codigo": "000000"},
        )

    respuesta = client.post(
        "/auth/verificar",
        json={"email": "ana@stockarg.com.ar", "codigo": codigo},
    )
    assert respuesta.status_code == 400


def test_pedir_un_codigo_nuevo_invalida_el_anterior(client, correos):
    viejo = _registrar(client, correos)
    client.post("/auth/reenviar", json={"email": "ana@stockarg.com.ar"})

    respuesta = client.post(
        "/auth/verificar",
        json={"email": "ana@stockarg.com.ar", "codigo": viejo},
    )

    assert respuesta.status_code == 400


def test_registrar_un_correo_existente_no_lo_revela(client, correos):
    """El alta no puede servir para averiguar que cuentas existen."""
    _cuenta_lista(client, correos)

    repetido = client.post(
        "/auth/registro",
        json={
            "email": "ana@stockarg.com.ar",
            "nombre": "Otra",
            "contrasena": CLAVE,
        },
    )

    assert repetido.status_code == 201
    assert repetido.json()["mensaje"]


def test_registrar_dos_veces_no_duplica_la_cuenta(client, correos, db):
    _cuenta_lista(client, correos)
    client.post(
        "/auth/registro",
        json={
            "email": "ana@stockarg.com.ar",
            "nombre": "Otra",
            "contrasena": CLAVE,
        },
    )

    assert db.query(Usuario).filter_by(email="ana@stockarg.com.ar").count() == 1


def test_el_correo_no_distingue_mayusculas(client, correos, db):
    _cuenta_lista(client, correos, "Ana@StockARG.com.ar")

    assert db.query(Usuario).count() == 1
    assert db.query(Usuario).one().email == "ana@stockarg.com.ar"


@pytest.mark.parametrize(
    "contrasena",
    ["corta1", "sinnumeros", "12345678", "        1"],
)
def test_se_rechazan_las_contrasenas_debiles(client, contrasena):
    respuesta = client.post(
        "/auth/registro",
        json={
            "email": "ana@stockarg.com.ar",
            "nombre": "Ana",
            "contrasena": contrasena,
        },
    )

    assert respuesta.status_code == 422


def test_se_rechaza_un_correo_mal_formado(client):
    respuesta = client.post(
        "/auth/registro",
        json={"email": "no-es-correo", "nombre": "Ana", "contrasena": CLAVE},
    )

    assert respuesta.status_code == 422


# --- ingreso (RF-A02) ----------------------------------------------------


def test_se_puede_ingresar_tras_verificar(client, correos):
    _cuenta_lista(client, correos)

    respuesta = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["access_token"]


def test_no_se_puede_ingresar_sin_verificar(client, correos):
    _registrar(client, correos)

    respuesta = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    )

    assert respuesta.status_code == 401


def test_el_error_es_el_mismo_para_correo_y_para_clave(client, correos):
    """Distinguirlos convierte el login en un detector de cuentas."""
    _cuenta_lista(client, correos)

    inexistente = client.post(
        "/auth/login",
        json={"email": "nadie@stockarg.com.ar", "contrasena": CLAVE},
    )
    clave_mala = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": "Otra12345"},
    )

    assert inexistente.status_code == clave_mala.status_code == 401
    assert inexistente.json()["detail"] == clave_mala.json()["detail"]


def test_la_respuesta_no_incluye_el_hash_de_la_contrasena(client, correos):
    _cuenta_lista(client, correos)

    cuerpo = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    ).json()

    texto = str(cuerpo)
    assert "password" not in texto
    assert "$2b$" not in texto
    assert "intentos" not in texto


def test_una_cuenta_dada_de_baja_no_ingresa(client, correos, db):
    _cuenta_lista(client, correos)
    db.query(Usuario).filter_by(
        email="ana@stockarg.com.ar"
    ).one().activo = False
    db.commit()

    respuesta = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    )

    assert respuesta.status_code == 401


# --- bloqueo por intentos (RF-A05) ---------------------------------------


def test_la_cuenta_se_bloquea_tras_cinco_intentos(client, correos):
    _cuenta_lista(client, correos)

    for _ in range(5):
        client.post(
            "/auth/login",
            json={"email": "ana@stockarg.com.ar", "contrasena": "Mala12345"},
        )

    con_la_buena = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    )

    assert con_la_buena.status_code == 429
    assert "bloquead" in con_la_buena.json()["detail"].lower()


def test_un_ingreso_correcto_borra_los_intentos(client, correos, db):
    _cuenta_lista(client, correos)
    for _ in range(3):
        client.post(
            "/auth/login",
            json={"email": "ana@stockarg.com.ar", "contrasena": "Mala12345"},
        )

    client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    )

    usuario = db.query(Usuario).filter_by(email="ana@stockarg.com.ar").one()
    assert usuario.intentos_fallidos == 0
    assert usuario.bloqueado_hasta is None


# --- recuperacion (RF-A04) -----------------------------------------------


def test_recuperar_envia_un_enlace(client, correos):
    _cuenta_lista(client, correos)
    correos.clear()

    client.post("/auth/recuperar", json={"email": "ana@stockarg.com.ar"})

    assert len(correos) == 1


def test_recuperar_un_correo_inexistente_responde_igual(client, correos):
    _cuenta_lista(client, correos)

    conocido = client.post(
        "/auth/recuperar", json={"email": "ana@stockarg.com.ar"}
    )
    desconocido = client.post(
        "/auth/recuperar", json={"email": "nadie@stockarg.com.ar"}
    )

    assert conocido.status_code == desconocido.status_code == 200
    assert conocido.json() == desconocido.json()


def test_el_token_permite_fijar_una_contrasena_nueva(client, correos):
    _cuenta_lista(client, correos)
    correos.clear()
    client.post("/auth/recuperar", json={"email": "ana@stockarg.com.ar"})
    token = correos[-1][1]

    respuesta = client.post(
        "/auth/restablecer",
        json={"token": token, "contrasena": "NuevaClave9"},
    )

    assert respuesta.status_code == 200
    assert (
        client.post(
            "/auth/login",
            json={
                "email": "ana@stockarg.com.ar",
                "contrasena": "NuevaClave9",
            },
        ).status_code
        == 200
    )


def test_la_contrasena_vieja_deja_de_servir(client, correos):
    _cuenta_lista(client, correos)
    correos.clear()
    client.post("/auth/recuperar", json={"email": "ana@stockarg.com.ar"})
    client.post(
        "/auth/restablecer",
        json={"token": correos[-1][1], "contrasena": "NuevaClave9"},
    )

    respuesta = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": CLAVE},
    )

    assert respuesta.status_code == 401


def test_el_enlace_de_recuperacion_sirve_una_sola_vez(client, correos):
    _cuenta_lista(client, correos)
    correos.clear()
    client.post("/auth/recuperar", json={"email": "ana@stockarg.com.ar"})
    token = correos[-1][1]
    client.post(
        "/auth/restablecer",
        json={"token": token, "contrasena": "NuevaClave9"},
    )

    segunda = client.post(
        "/auth/restablecer",
        json={"token": token, "contrasena": "OtraMas9876"},
    )

    assert segunda.status_code == 400


def test_recuperar_destraba_una_cuenta_bloqueada(client, correos):
    """Quien llego al correo demostro ser la duena de la cuenta."""
    _cuenta_lista(client, correos)
    for _ in range(5):
        client.post(
            "/auth/login",
            json={"email": "ana@stockarg.com.ar", "contrasena": "Mala12345"},
        )
    correos.clear()

    client.post("/auth/recuperar", json={"email": "ana@stockarg.com.ar"})
    client.post(
        "/auth/restablecer",
        json={"token": correos[-1][1], "contrasena": "NuevaClave9"},
    )

    respuesta = client.post(
        "/auth/login",
        json={"email": "ana@stockarg.com.ar", "contrasena": "NuevaClave9"},
    )
    assert respuesta.status_code == 200


def test_un_token_inventado_no_restablece_nada(client, correos):
    _cuenta_lista(client, correos)

    respuesta = client.post(
        "/auth/restablecer",
        json={"token": "x" * 40, "contrasena": "NuevaClave9"},
    )

    assert respuesta.status_code == 400


# --- perfil y sesion (RF-A06, RF-A07) ------------------------------------


def test_el_perfil_exige_token(client):
    assert client.get("/auth/perfil").status_code == 401


def test_el_perfil_rechaza_un_token_inventado(client):
    respuesta = client.get("/auth/perfil", headers=_cabecera("no.es.un.token"))

    assert respuesta.status_code == 401


def test_el_perfil_devuelve_la_sesion_en_curso(client, correos):
    token = _cuenta_lista(client, correos)

    cuerpo = client.get("/auth/perfil", headers=_cabecera(token)).json()

    assert cuerpo["email"] == "ana@stockarg.com.ar"
    assert cuerpo["rol"] == "propietario"
    assert "password_hash" not in cuerpo


def test_dar_de_baja_la_cuenta_corta_la_sesion_en_el_acto(client, correos, db):
    """No se espera a que venza el token ya emitido."""
    token = _cuenta_lista(client, correos)
    db.query(Usuario).filter_by(
        email="ana@stockarg.com.ar"
    ).one().activo = False
    db.commit()

    respuesta = client.get("/auth/perfil", headers=_cabecera(token))

    assert respuesta.status_code == 401


def test_se_puede_cambiar_el_nombre_propio(client, correos):
    token = _cuenta_lista(client, correos)

    respuesta = client.put(
        "/auth/perfil",
        json={"nombre": "Ana Gomez"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Ana Gomez"


def test_cambiar_la_contrasena_exige_la_anterior(client, correos):
    token = _cuenta_lista(client, correos)

    respuesta = client.put(
        "/auth/contrasena",
        json={
            "contrasena_actual": "Equivocada9",
            "contrasena_nueva": "NuevaClave9",
        },
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 400


def test_cambiar_la_contrasena_con_la_anterior_correcta(client, correos):
    token = _cuenta_lista(client, correos)

    client.put(
        "/auth/contrasena",
        json={
            "contrasena_actual": CLAVE,
            "contrasena_nueva": "NuevaClave9",
        },
        headers=_cabecera(token),
    )

    assert (
        client.post(
            "/auth/login",
            json={
                "email": "ana@stockarg.com.ar",
                "contrasena": "NuevaClave9",
            },
        ).status_code
        == 200
    )


def test_una_cuenta_de_google_no_entra_con_contrasena_vacia(client, db):
    """Hash nulo no puede validar nada, ni siquiera la cadena vacia."""
    db.add(
        Usuario(
            email="google@stockarg.com.ar",
            nombre="Con Google",
            google_id="1234567890",
            password_hash=None,
            verificado=True,
            activo=True,
        )
    )
    db.commit()

    for intento in ["", " ", "None", "null"]:
        respuesta = client.post(
            "/auth/login",
            json={"email": "google@stockarg.com.ar", "contrasena": intento},
        )
        assert respuesta.status_code in (401, 422)


def test_el_hash_de_la_contrasena_nunca_vuelve_en_una_respuesta(
    client, correos, db
):
    db.add(
        Usuario(
            email="otro@stockarg.com.ar",
            nombre="Otro",
            password_hash=hash_contrasena(CLAVE),
            verificado=True,
        )
    )
    db.commit()
    token = _cuenta_lista(client, correos)

    texto = str(client.get("/auth/perfil", headers=_cabecera(token)).json())

    assert "$2b$" not in texto


def test_no_se_puede_secuestrar_una_cuenta_sin_verificar(client, correos, db):
    """Pre-secuestro de cuenta.

    Alguien se registra y todavia no verifico. Un tercero manda un alta
    con el mismo correo y una contrasena que el elige. Si ese segundo
    registro pisara la contrasena, al verificar la duena legitima con el
    codigo que le llega a su casilla, la cuenta quedaria abierta con la
    clave del tercero.
    """
    codigo_legitimo = _registrar(client, correos, "victima@stockarg.com.ar")

    client.post(
        "/auth/registro",
        json={
            "email": "victima@stockarg.com.ar",
            "nombre": "Atacante",
            "contrasena": "DelAtacante9",
        },
    )

    client.post(
        "/auth/verificar",
        json={
            "email": "victima@stockarg.com.ar",
            "codigo": correos[-1][1],
        },
    )

    con_la_del_atacante = client.post(
        "/auth/login",
        json={
            "email": "victima@stockarg.com.ar",
            "contrasena": "DelAtacante9",
        },
    )
    assert con_la_del_atacante.status_code == 401

    con_la_legitima = client.post(
        "/auth/login",
        json={"email": "victima@stockarg.com.ar", "contrasena": CLAVE},
    )
    assert con_la_legitima.status_code == 200
    assert codigo_legitimo
