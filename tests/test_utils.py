import re
from Utils import (
    email_valido,
    password_valida,
    generar_codigo,
    hash_password,
    verificar_password,
    campos_requeridos,
    parse_int,
    parse_float,
    validar_id,
)


def test_email_valido():
    assert email_valido("a@b.com")
    assert not email_valido("ab.com")


def test_password_valida():
    assert password_valida("Abcdef12")
    assert not password_valida("short1")
    assert not password_valida("abcdefgh")
    assert not password_valida("12345678")


def test_generar_codigo():
    code = generar_codigo()
    assert len(code) == 6
    assert re.fullmatch(r"\d{6}", code)


def test_hash_y_verificacion():
    h = hash_password("Clave123")
    assert verificar_password("Clave123", h)
    assert not verificar_password("Incorrecta", h)


def test_campos_requeridos():
    ok, faltantes = campos_requeridos(nombre="Ana", email="", telefono=None)
    assert not ok
    assert "email" in faltantes
    assert "telefono" in faltantes


def test_parse_int():
    assert parse_int("10", min_value=1) == 10
    assert parse_int("0", allow_zero=False) is None
    assert parse_int("-1", min_value=0) is None


def test_parse_float():
    assert parse_float("1,5", min_value=1) == 1.5
    assert parse_float("$ 2.50") == 2.5
    assert parse_float("0", allow_zero=False) is None


def test_validar_id():
    ok, err = validar_id("ABC_123")
    assert ok
    ok, err = validar_id("A B")
    assert not ok
