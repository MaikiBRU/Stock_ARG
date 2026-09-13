"""Parametros que se cambian sin reiniciar (RF-I06).

El problema que resuelve: los umbrales de stock, la ventana de aviso de
vencimiento y el tope de descuento se pueden editar desde la pantalla de
configuracion, pero quien los consume no siempre puede consultar la base
en ese punto -- una propiedad de un modelo no recibe la sesion. Si cada
lado usara su propia fuente, guardar un umbral devolveria 200 y el panel
seguiria calculando con el valor viejo.

Los valores viajan en la sesion de base de la peticion y no en el
proceso. Con una cache global, dos peticiones simultaneas se pisarian:
el propietario de un sandbox de la demo podria subir el tope de
descuento y ese valor le llegaria a un vendedor de la aplicacion real
que cobra en el mismo instante. Cada peticion tiene su propia sesion, asi
que cada una ve solo los parametros de su particion.

El valor del entorno queda como respaldo para cuando no se guardo nada.
Este modulo no importa modelos a proposito: si lo hiciera, el modelo que
lo consulta cerraria un ciclo de imports.
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings

# Nombre del parametro en la base -> nombre del ajuste de entorno que lo
# respalda. Lo que no esta aca no afecta el comportamiento del sistema.
RESPALDOS = {
    "stock_umbral_bajo": "stock_umbral_bajo",
    "stock_umbral_medio": "stock_umbral_medio",
    "dias_aviso_vencimiento": "dias_proximo_vencimiento",
    "descuento_max_vendedor": "descuento_max_vendedor_porcentaje",
}

CLAVE_EN_SESION = "ajustes_vivos"


def fijar(sesion: Session, valores: dict[str, str]) -> None:
    """Deja en la sesion los parametros guardados de su particion."""
    sesion.info[CLAVE_EN_SESION] = dict(valores)


def entero(clave: str, sesion: Session | None) -> int:
    """Valor numerico del parametro, o el del entorno si no se guardo.

    Sin sesion, o con una sesion que no cargo parametros, vale el
    respaldo. Un valor guardado ilegible tampoco puede tumbar el calculo:
    se cae al respaldo, que siempre es un entero validado.
    """
    respaldo = getattr(get_settings(), RESPALDOS[clave])
    guardados = sesion.info.get(CLAVE_EN_SESION, {}) if sesion else {}
    guardado = guardados.get(clave)

    if guardado is None:
        return respaldo
    try:
        return int(guardado)
    except (TypeError, ValueError):
        return respaldo
