"""Hash de contrasenas y emision de tokens de sesion."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITMO = "HS256"

# bcrypt trunca en silencio lo que pase de 72 bytes: dos contrasenas que
# comparten los primeros 72 darian el mismo hash. Se rechaza antes de
# hashear en vez de dejar que la libreria recorte.
LIMITE_BCRYPT_BYTES = 72


class ContrasenaDemasiadoLarga(ValueError):
    """La contrasena supera lo que bcrypt puede procesar."""


def hash_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de una contrasena."""
    bytes_contrasena = contrasena.encode("utf-8")
    if len(bytes_contrasena) > LIMITE_BCRYPT_BYTES:
        raise ContrasenaDemasiadoLarga(
            f"La contrasena no puede superar los {LIMITE_BCRYPT_BYTES} bytes."
        )
    return bcrypt.hashpw(bytes_contrasena, bcrypt.gensalt()).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str | None) -> bool:
    """Compara una contrasena con su hash.

    Un hash nulo es una cuenta que entra por Google y todavia no tiene
    contrasena. Devuelve False sin comparar: si se dejara pasar al
    verificador, cualquier cadena podria terminar validando.
    """
    if not hash_guardado:
        return False
    bytes_contrasena = contrasena.encode("utf-8")
    if len(bytes_contrasena) > LIMITE_BCRYPT_BYTES:
        return False
    try:
        return bcrypt.checkpw(bytes_contrasena, hash_guardado.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash con formato invalido: se trata como credencial incorrecta.
        return False


def crear_token(
    sujeto: str,
    tipo: str = "acceso",
    minutos: int | None = None,
    **extra: Any,
) -> str:
    """Firma un token con vencimiento.

    El campo "typ" separa los tokens de la aplicacion de los de la demo.
    Sin el, un token de sandbox serviria para entrar a la aplicacion real.
    """
    ajustes = get_settings()
    ahora = datetime.now(UTC)
    minutos = minutos or ajustes.access_token_expire_minutes

    carga = {
        "sub": sujeto,
        "typ": tipo,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
        **extra,
    }
    return jwt.encode(carga, ajustes.secret_key, algorithm=ALGORITMO)


def leer_token(
    token: str, tipo_esperado: str | tuple[str, ...] = "acceso"
) -> dict[str, Any]:
    """Valida un token y devuelve su contenido.

    Fija el algoritmo en la verificacion: aceptar el que venga en la
    cabecera permitiria presentar un token sin firma, o firmado con la
    clave publica de otro esquema, y darlo por valido.
    """
    ajustes = get_settings()
    carga = jwt.decode(
        token,
        ajustes.secret_key,
        algorithms=[ALGORITMO],
        options={"require": ["exp", "sub", "typ"]},
    )
    aceptados = (
        (tipo_esperado,) if isinstance(tipo_esperado, str) else tipo_esperado
    )
    if carga.get("typ") not in aceptados:
        raise jwt.InvalidTokenError("El token no es del tipo esperado.")
    return carga


def generar_codigo_numerico(digitos: int = 6) -> str:
    """Codigo de un solo uso para verificar un correo (RF-A01)."""
    tope = 10**digitos
    return str(secrets.randbelow(tope)).zfill(digitos)


def generar_token_urlsafe(bytes_aleatorios: int = 32) -> str:
    """Token opaco para enlaces de recuperacion y sesiones de demo."""
    return secrets.token_urlsafe(bytes_aleatorios)


def hash_opaco(valor: str) -> str:
    """Huella de un valor, con la clave de la aplicacion como sal.

    Se usa para guardar codigos de verificacion y direcciones IP: alcanza
    para compararlos y contarlos, pero el valor original no se puede
    reconstruir desde la base.
    """
    ajustes = get_settings()
    return hmac.new(
        ajustes.secret_key.encode("utf-8"),
        valor.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def comparar_seguro(a: str, b: str) -> bool:
    """Compara dos cadenas en tiempo constante.

    Se comparan los bytes y no las cadenas: compare_digest rechaza con
    TypeError un str que no sea ASCII, y una cabecera con un caracter
    raro terminaria en un 500 en lugar de un rechazo comun.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
