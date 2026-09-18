"""Verificacion del ingreso con Google (RF-A03).

El navegador obtiene un token de identidad de Google y lo manda; aca se
comprueba contra las claves publicas de Google, que sea para esta
aplicacion y que no haya vencido. Nada de eso se puede falsificar desde
el cliente.

Se usa el token de identidad y no el intercambio con codigo: asi no hace
falta guardar el secreto del cliente para entrar, y el flujo entero es
una sola peticion.
"""

from typing import Any

from app.core.config import get_settings

# Los unicos emisores que Google usa para estos tokens.
EMISORES = ("accounts.google.com", "https://accounts.google.com")


class ErrorDeGoogle(Exception):
    """No se pudo validar el ingreso con Google."""

    def __init__(self, mensaje: str, codigo: str) -> None:
        """Guarda el mensaje visible y un codigo para el frontend."""
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class GoogleNoConfigurado(ErrorDeGoogle):
    """Falta el identificador de cliente en el entorno."""


class CredencialInvalida(ErrorDeGoogle):
    """El token no es de Google, no es de esta app o ya vencio."""


def esta_configurado() -> bool:
    """True si el ingreso con Google se puede ofrecer."""
    return bool(get_settings().google_client_id)


def verificar_credencial(credencial: str) -> dict[str, Any]:
    """Valida el token de identidad y devuelve el perfil.

    Google firma el token y la libreria comprueba la firma, el emisor,
    el destinatario y el vencimiento. Lo unico que queda por mirar aca es
    que el correo venga verificado: una cuenta de Google puede existir
    con un correo que su duena nunca confirmo, y con ese correo no se
    puede tomar un usuario de la aplicacion.
    """
    ajustes = get_settings()
    if not ajustes.google_client_id:
        raise GoogleNoConfigurado(
            "El ingreso con Google no esta disponible.", "google_no_disponible"
        )

    # Import local: en desarrollo, sin Google configurado, el paquete no
    # hace falta.
    from google.auth.transport import requests as transporte
    from google.oauth2 import id_token

    try:
        perfil = id_token.verify_oauth2_token(
            credencial, transporte.Request(), ajustes.google_client_id
        )
    except Exception as error:
        # La libreria levanta ValueError para todo lo que no valida, y
        # errores de red al buscar las claves. En los dos casos, para
        # quien llama es lo mismo: esta credencial no sirve.
        raise CredencialInvalida(
            "La credencial de Google no es valida.", "credencial_invalida"
        ) from error

    if perfil.get("iss") not in EMISORES:
        raise CredencialInvalida(
            "La credencial de Google no es valida.", "credencial_invalida"
        )
    if not perfil.get("email") or not perfil.get("email_verified"):
        raise CredencialInvalida(
            "La cuenta de Google no tiene el correo verificado.",
            "correo_sin_verificar",
        )
    return perfil
