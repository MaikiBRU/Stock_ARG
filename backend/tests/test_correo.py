"""Envio de correo por SMTP, contra un servidor falso (sin red)."""

import smtplib
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.services import correo

CLAVE = "re_clave_de_prueba_123"


def _ajustes(**cambios):
    valores = {
        "es_produccion": True,
        "smtp_host": "smtp.ejemplo.com",
        "smtp_puerto": 465,
        "smtp_usuario": "resend",
        "smtp_contrasena": SecretStr(CLAVE),
        "email_from": "no-reply@stockarg.ejemplo.com",
        "email_from_nombre": "StockARG",
        "frontend_url": "https://stockarg.ejemplo.com",
    }
    valores.update(cambios)
    return SimpleNamespace(**valores)


class ServidorFalso:
    """Registra lo que haria un servidor SMTP de verdad."""

    creados: list["ServidorFalso"] = []
    fallar_en: str | None = None

    def __init__(self, host, puerto, timeout=None, context=None):
        self.host = host
        self.puerto = puerto
        self.timeout = timeout
        self.tls_directo = context is not None
        self.starttls_hecho = False
        self.login_con = None
        self.enviados = []
        self.cerrado = False
        ServidorFalso.creados.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrado = True
        return False

    def starttls(self, context=None):
        if self.fallar_en == "starttls":
            raise smtplib.SMTPNotSupportedError("STARTTLS no disponible")
        self.starttls_hecho = True

    def login(self, usuario, clave):
        if self.fallar_en == "login":
            raise smtplib.SMTPAuthenticationError(535, f"mala clave {clave}")
        self.login_con = (usuario, clave)

    def send_message(self, mensaje):
        self.enviados.append(mensaje)


@pytest.fixture
def servidor(monkeypatch):
    ServidorFalso.creados = []
    ServidorFalso.fallar_en = None
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", ServidorFalso)
    monkeypatch.setattr(correo.smtplib, "SMTP", ServidorFalso)
    return ServidorFalso


def _usar(monkeypatch, **cambios):
    ajustes = _ajustes(**cambios)
    monkeypatch.setattr(correo, "get_settings", lambda: ajustes)
    return ajustes


def test_en_produccion_envia_por_tls_directo(monkeypatch, servidor):
    _usar(monkeypatch)

    correo.enviar_codigo_de_verificacion("ana@ejemplo.com", "123456")

    conexion = servidor.creados[0]
    assert conexion.tls_directo
    assert conexion.puerto == 465
    assert conexion.login_con == ("resend", CLAVE)
    assert conexion.cerrado
    mensaje = conexion.enviados[0]
    assert mensaje["To"] == "ana@ejemplo.com"
    assert mensaje["From"] == "StockARG <no-reply@stockarg.ejemplo.com>"
    assert "123456" in mensaje.get_content()
    assert mensaje["Message-ID"].endswith("@stockarg.ejemplo.com>")


def test_con_587_pasa_a_tls_antes_del_login(monkeypatch, servidor):
    _usar(monkeypatch, smtp_puerto=587)

    correo.enviar_codigo_de_verificacion("ana@ejemplo.com", "123456")

    conexion = servidor.creados[0]
    assert not conexion.tls_directo
    assert conexion.starttls_hecho
    assert conexion.login_con is not None


def test_sin_starttls_no_manda_la_clave(monkeypatch, servidor):
    """Si el servidor no cifra, la clave no viaja en claro."""
    _usar(monkeypatch, smtp_puerto=587)
    servidor.fallar_en = "starttls"

    with pytest.raises(correo.ErrorDeEnvio):
        correo.enviar_codigo_de_verificacion("ana@ejemplo.com", "123456")

    conexion = servidor.creados[0]
    assert conexion.login_con is None
    assert conexion.cerrado


def test_una_falla_no_filtra_la_clave(monkeypatch, servidor, caplog):
    _usar(monkeypatch)
    servidor.fallar_en = "login"

    with pytest.raises(correo.ErrorDeEnvio) as error:
        correo.enviar_codigo_de_verificacion("ana@ejemplo.com", "123456")

    assert CLAVE not in str(error.value)
    assert CLAVE not in caplog.text


@pytest.mark.parametrize(
    "faltante", ["smtp_host", "smtp_usuario", "smtp_contrasena"]
)
def test_sin_configurar_falla_sin_conectar(monkeypatch, servidor, faltante):
    _usar(monkeypatch, **{faltante: None})

    with pytest.raises(correo.ErrorDeEnvio):
        correo.enviar_codigo_de_verificacion("ana@ejemplo.com", "123456")

    assert servidor.creados == []


def test_en_desarrollo_no_se_conecta(monkeypatch, servidor, caplog):
    _usar(monkeypatch, es_produccion=False)

    with caplog.at_level("INFO", logger="stockarg.correo"):
        correo.enviar_enlace_de_recuperacion("ana@ejemplo.com", "t" * 30)

    assert servidor.creados == []
    assert "restablecer?token=" in caplog.text


def test_la_clave_no_aparece_al_imprimir_los_ajustes():
    ajustes = _ajustes()
    assert CLAVE not in repr(ajustes.smtp_contrasena)
