import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {"database_url": "sqlite+pysqlite:///:memory:"}


def test_no_arranca_sin_clave(monkeypatch):
    # _env_file=None ignora el archivo .env, no las variables de entorno,
    # y conftest exporta SECRET_KEY para el resto de la suite. Hay que
    # sacarla para comprobar que sin clave la aplicacion no levanta.
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **BASE)


@pytest.mark.parametrize("relleno", ["change-me", "secret", "CAMBIAR", "todo"])
def test_rechaza_claves_de_relleno(relleno):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key=relleno, **BASE)


def test_rechaza_claves_demasiado_cortas():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key="corta", **BASE)


def test_produccion_cierra_la_documentacion():
    ajustes = Settings(
        _env_file=None,
        secret_key="una-clave-larga-de-verdad-para-firmar",
        environment="production",
        **BASE,
    )

    assert ajustes.es_produccion is True
    assert ajustes.mostrar_documentacion is False


def test_desarrollo_publica_la_documentacion():
    ajustes = Settings(
        _env_file=None,
        secret_key="una-clave-larga-de-verdad-para-firmar",
        **BASE,
    )

    assert ajustes.mostrar_documentacion is True


def test_origenes_se_parsean_sin_espacios():
    ajustes = Settings(
        _env_file=None,
        secret_key="una-clave-larga-de-verdad-para-firmar",
        allowed_origins="https://a.com, https://b.com ,",
        **BASE,
    )

    assert ajustes.origenes_permitidos == ["https://a.com", "https://b.com"]


def test_rechaza_claves_por_debajo_del_minimo_de_hmac(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key="a" * 31, **BASE)


def test_acepta_una_clave_de_la_longitud_correcta(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    ajustes = Settings(_env_file=None, secret_key="a" * 32, **BASE)

    assert len(ajustes.secret_key) == 32


CLAVE = "una-clave-larga-de-verdad-para-firmar-bien"


def _ajustes(**extra):
    return Settings(_env_file=None, secret_key=CLAVE, **BASE, **extra)


def test_rechaza_umbrales_de_stock_invertidos():
    with pytest.raises(ValidationError):
        _ajustes(stock_umbral_bajo=80, stock_umbral_medio=20)


def test_rechaza_umbrales_de_stock_iguales():
    with pytest.raises(ValidationError):
        _ajustes(stock_umbral_bajo=50, stock_umbral_medio=50)


def test_rechaza_umbrales_de_stock_fuera_de_escala():
    with pytest.raises(ValidationError):
        _ajustes(stock_umbral_bajo=30, stock_umbral_medio=120)


def test_acepta_los_umbrales_de_la_version_de_escritorio():
    ajustes = _ajustes(stock_umbral_bajo=30, stock_umbral_medio=54)

    assert ajustes.stock_umbral_bajo == 30
    assert ajustes.stock_umbral_medio == 54


def test_rechaza_una_demo_que_caduca_antes_de_empezar():
    with pytest.raises(ValidationError):
        _ajustes(demo_session_ttl_minutes=0)
