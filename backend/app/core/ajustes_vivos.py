"""Parametros que se cambian sin reiniciar (RF-I06).

El problema que resuelve: los umbrales de stock, la ventana de aviso de
vencimiento y el tope de descuento se pueden editar desde la pantalla de
configuracion, pero quien los consume no puede consultar la base en ese
punto -- una propiedad de un modelo no tiene sesion. Si cada lado usara
su propia fuente, guardar un umbral devolveria 200 y el panel seguiria
calculando con el valor viejo.

Aca vive la unica fuente de verdad: una cache por proceso que se refresca
en cada peticion autenticada. El valor del entorno queda como respaldo
para cuando todavia no se guardo nada.

Este modulo no importa modelos a proposito: si lo hiciera, el modelo que
lo consulta cerraria un ciclo de imports.
"""

from threading import Lock

from app.core.config import get_settings

# Nombre del parametro en la base -> nombre del ajuste de entorno que lo
# respalda. Lo que no esta aca no afecta el comportamiento del sistema.
RESPALDOS = {
    "stock_umbral_bajo": "stock_umbral_bajo",
    "stock_umbral_medio": "stock_umbral_medio",
    "dias_aviso_vencimiento": "dias_proximo_vencimiento",
    "descuento_max_vendedor": "descuento_max_vendedor_porcentaje",
}

_valores: dict[str, str] = {}
_candado = Lock()


def fijar(valores: dict[str, str]) -> None:
    """Reemplaza la cache con lo que hay guardado en la base."""
    with _candado:
        _valores.clear()
        _valores.update(valores)


def limpiar() -> None:
    """Vacia la cache. La usan las pruebas entre casos."""
    with _candado:
        _valores.clear()


def entero(clave: str) -> int:
    """Valor numerico del parametro, o el del entorno si no se guardo.

    Un valor guardado ilegible no puede tumbar el calculo: se cae al
    respaldo, que siempre es un entero validado por la configuracion.
    """
    respaldo = getattr(get_settings(), RESPALDOS[clave])

    with _candado:
        guardado = _valores.get(clave)

    if guardado is None:
        return respaldo
    try:
        return int(guardado)
    except (TypeError, ValueError):
        return respaldo


def texto(clave: str, por_defecto: str = "") -> str:
    """Valor de texto del parametro."""
    with _candado:
        return _valores.get(clave, por_defecto)
