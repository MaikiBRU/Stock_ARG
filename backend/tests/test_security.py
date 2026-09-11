from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    ALGORITMO,
    ContrasenaDemasiadoLarga,
    comparar_seguro,
    crear_token,
    generar_codigo_numerico,
    generar_token_urlsafe,
    hash_contrasena,
    hash_opaco,
    leer_token,
    verificar_contrasena,
)

# --- contrasenas --------------------------------------------------------


def test_el_hash_verifica_la_contrasena_correcta():
    assert verificar_contrasena("Kiosco2026!", hash_contrasena("Kiosco2026!"))


def test_el_hash_rechaza_la_contrasena_incorrecta():
    assert not verificar_contrasena("otra", hash_contrasena("Kiosco2026!"))


def test_el_mismo_texto_da_hashes_distintos():
    """Sal por hash: dos cuentas con la misma clave no se ven iguales."""
    assert hash_contrasena("igual") != hash_contrasena("igual")


def test_una_cuenta_sin_contrasena_no_valida_nada():
    """Cuentas de Google: hash nulo no puede dejar entrar a nadie."""
    assert not verificar_contrasena("", None)
    assert not verificar_contrasena("cualquier cosa", None)


def test_un_hash_corrupto_no_hace_estallar_el_login():
    assert not verificar_contrasena("clave", "esto-no-es-un-hash")


def test_se_rechaza_la_contrasena_que_bcrypt_truncaria():
    with pytest.raises(ContrasenaDemasiadoLarga):
        hash_contrasena("a" * 73)


def test_el_limite_exacto_se_acepta():
    assert verificar_contrasena("a" * 72, hash_contrasena("a" * 72))


def test_una_contrasena_larga_no_valida_por_truncamiento():
    """Sin el limite, estas dos compartirian hash en bcrypt."""
    guardado = hash_contrasena("a" * 72)

    assert not verificar_contrasena("a" * 72 + "distinto", guardado)


def test_los_acentos_cuentan_como_bytes_no_como_letras():
    """Cada acentuada ocupa dos bytes: el limite es de bytes."""
    with pytest.raises(ContrasenaDemasiadoLarga):
        hash_contrasena("ñ" * 37)


# --- tokens -------------------------------------------------------------


def test_el_token_devuelve_su_sujeto():
    carga = leer_token(crear_token("42"))

    assert carga["sub"] == "42"
    assert carga["typ"] == "acceso"


def test_un_token_de_demo_no_sirve_como_token_de_aplicacion():
    token = crear_token("demo:abc", tipo="demo")

    with pytest.raises(jwt.InvalidTokenError):
        leer_token(token, tipo_esperado="acceso")


def test_un_token_vencido_se_rechaza():
    token = crear_token("42", minutos=-1)

    with pytest.raises(jwt.ExpiredSignatureError):
        leer_token(token)


def test_un_token_firmado_con_otra_clave_se_rechaza():
    ajeno = jwt.encode(
        {
            "sub": "42",
            "typ": "acceso",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "clave-de-otro-sistema-distinta-y-larga",
        algorithm=ALGORITMO,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        leer_token(ajeno)


def test_un_token_sin_firma_se_rechaza():
    """Confusion de algoritmo: alg=none es el ataque clasico."""
    sin_firma = jwt.encode(
        {
            "sub": "42",
            "typ": "acceso",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        key="",
        algorithm="none",
    )

    with pytest.raises(jwt.InvalidTokenError):
        leer_token(sin_firma)


def test_un_token_sin_vencimiento_se_rechaza():
    ajustes = get_settings()
    eterno = jwt.encode(
        {"sub": "42", "typ": "acceso"},
        ajustes.secret_key,
        algorithm=ALGORITMO,
    )

    with pytest.raises(jwt.MissingRequiredClaimError):
        leer_token(eterno)


def test_un_token_manipulado_se_rechaza():
    token = crear_token("42")
    cabecera, carga, firma = token.split(".")
    alterado = f"{cabecera}.{carga}.{firma[:-4]}AAAA"

    with pytest.raises(jwt.PyJWTError):
        leer_token(alterado)


def test_el_token_lleva_los_datos_extra_que_se_le_pasan():
    carga = leer_token(crear_token("42", rol="propietario"))

    assert carga["rol"] == "propietario"


# --- codigos y huellas --------------------------------------------------


def test_el_codigo_de_verificacion_tiene_seis_digitos():
    for _ in range(50):
        codigo = generar_codigo_numerico()
        assert len(codigo) == 6
        assert codigo.isdigit()


def test_los_codigos_no_se_repiten_siempre():
    assert len({generar_codigo_numerico() for _ in range(60)}) > 1


def test_los_tokens_opacos_son_distintos_entre_si():
    assert generar_token_urlsafe() != generar_token_urlsafe()


def test_la_huella_es_estable_y_no_devuelve_el_original():
    valor = "190.2.3.4"

    huella = hash_opaco(valor)

    assert huella == hash_opaco(valor)
    assert valor not in huella
    assert len(huella) == 64


def test_la_comparacion_segura_distingue_cadenas():
    assert comparar_seguro("abc", "abc")
    assert not comparar_seguro("abc", "abd")
