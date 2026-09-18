"""La sesion en una cookie, para el navegador.

El token se sigue aceptando por cabecera: lo usan las pruebas, curl y
cualquier cliente que no sea un navegador. Pero una pagina que guarda el
token en localStorage se lo entrega entero al primer XSS, asi que el
frontend usa esta cookie, que el JavaScript de la pagina no puede leer.

Es HttpOnly, SameSite=Lax y Secure fuera de desarrollo. El frontend y la
API viven en dos subdominios del mismo sitio, asi que el navegador la
manda igual; una pagina ajena no puede provocar una peticion con
credenciales, porque CORS solo admite los origenes declarados.
"""

from fastapi import Response

from app.core.config import get_settings

NOMBRE = "stockarg_sesion"


def fijar_sesion(respuesta: Response, token: str, minutos: int) -> None:
    """Deja la sesion en el navegador, con la vida del token."""
    respuesta.set_cookie(
        NOMBRE,
        token,
        max_age=minutos * 60,
        httponly=True,
        # En desarrollo la API es http: una cookie Secure no viajaria.
        secure=get_settings().es_produccion,
        samesite="lax",
        path="/",
    )


def borrar_sesion(respuesta: Response) -> None:
    """Saca la sesion del navegador."""
    respuesta.delete_cookie(
        NOMBRE,
        path="/",
        httponly=True,
        secure=get_settings().es_produccion,
        samesite="lax",
    )
