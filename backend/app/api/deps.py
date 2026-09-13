"""Dependencias compartidas por los endpoints."""

from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import ajustes_vivos
from app.core.security import leer_token
from app.db import particion
from app.db.session import get_db
from app.models import Rol, Usuario
from app.services import demo

# auto_error=False para responder 401 con nuestro propio mensaje en vez
# del texto por defecto de Starlette.
esquema_bearer = HTTPBearer(auto_error=False)

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sesion invalida o expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)


def ip_del_cliente(request: Request) -> str | None:
    """Direccion de quien llama, mirando primero el proxy.

    Detras de Caddy, request.client.host es siempre el proxy. Se toma la
    primera entrada de X-Forwarded-For, que es la que agrega el proxy de
    confianza. Se usa unicamente para contar intentos, nunca para
    autorizar: una cabecera la escribe cualquiera.
    """
    reenviada = request.headers.get("X-Forwarded-For")
    if reenviada:
        primera = reenviada.split(",")[0].strip()
        if primera:
            return primera
    return request.client.host if request.client else None


def _usuario_de_la_aplicacion(db: Session, carga: dict[str, Any]) -> Usuario:
    """Usuario real al que apunta un token de tipo "acceso"."""
    try:
        id_usuario = int(carga["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise CREDENCIALES_INVALIDAS from error

    usuario = db.get(Usuario, id_usuario)
    # Se comprueba contra la base en cada peticion, no contra el token:
    # dar de baja una cuenta la cierra en el acto, sin esperar a que
    # venza el token que ya tenia emitido.
    if usuario is None or not usuario.activo:
        raise CREDENCIALES_INVALIDAS
    # RF-A06: cerrar sesion incrementa la version del usuario, asi que
    # un token de una version anterior ya no vale aunque no haya vencido.
    if carga.get("sv", 0) != (usuario.version_sesion or 0):
        raise CREDENCIALES_INVALIDAS
    # Un token de la aplicacion nunca abre un usuario de un sandbox: los
    # ids son una secuencia compartida y se pueden adivinar.
    if usuario.id_sesion_demo is not None:
        raise CREDENCIALES_INVALIDAS
    return usuario


def obtener_usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Resuelve el usuario autenticado a partir del token.

    Acepta dos tipos de token. Uno de "acceso" abre un usuario real; uno
    de "demo" abre el usuario de un sandbox vigente con el rol elegido y
    deja de valer en cuanto la sesion vence o se termina.

    Lo que cada uno puede ver no se decide aca endpoint por endpoint: la
    particion del usuario se fija en la sesion de base y la capa ORM
    encierra ahi toda la peticion (ver app.db.particion). Un endpoint
    nuevo queda aislado sin tener que acordarse de nada.
    """
    if credenciales is None or not credenciales.credentials:
        raise CREDENCIALES_INVALIDAS

    try:
        carga = leer_token(
            credenciales.credentials, tipo_esperado=("acceso", "demo")
        )
    except jwt.PyJWTError as error:
        raise CREDENCIALES_INVALIDAS from error

    if carga["typ"] == "demo":
        usuario = demo.usuario_del_token(db, carga)
        if usuario is None:
            raise CREDENCIALES_INVALIDAS
    else:
        usuario = _usuario_de_la_aplicacion(db, carga)

    if not usuario.verificado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta todavia no fue verificada.",
        )

    # Los parametros configurables se refrescan aca y no al arrancar: un
    # cambio guardado desde la pantalla tiene efecto en la peticion
    # siguiente, sin reiniciar el proceso.
    from app.services.administracion import leer_configuracion

    # Desde aca, toda consulta de la peticion queda encerrada en la
    # particion del usuario.
    particion.fijar(db, usuario.id_sesion_demo)
    ajustes_vivos.fijar(db, leer_configuracion(db, usuario.id_sesion_demo))

    return usuario


def exigir_rol(*roles: Rol) -> Callable[[Usuario], Usuario]:
    """Restringe un endpoint a los roles indicados."""

    def verificar(
        usuario: Usuario = Depends(obtener_usuario_actual),
    ) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta operacion.",
            )
        return usuario

    return verificar


# Atajos que nombran la intencion en lugar de enumerar roles en cada
# endpoint: si manana aparece un rol nuevo, se cambia en un solo lugar.
exigir_gestion = exigir_rol(Rol.PROPIETARIO, Rol.ENCARGADO)
exigir_administracion = exigir_rol(Rol.PROPIETARIO)


def exigir_demo(
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Usuario:
    """Solo para quien esta recorriendo un sandbox de la demo."""
    if usuario.id_sesion_demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay una demo en curso.",
        )
    return usuario


def rechazar_demo(
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Usuario:
    """Cierra a la demo lo que no tiene sentido dentro de un sandbox."""
    if usuario.id_sesion_demo is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta accion no esta disponible en la demo.",
        )
    return usuario


def _cupo_de_la_demo(recurso: str) -> Callable[..., None]:
    """Descuenta un uso del cupo del sandbox antes de operar (RF-J06).

    El uso se consume aunque despues la operacion falle: lo que se acota
    es el trabajo que un visitante anonimo le puede pedir al servidor, y
    ese trabajo se hace igual. Fuera de la demo no hace nada.
    """

    def consumir(
        db: Session = Depends(get_db),
        usuario: Usuario = Depends(obtener_usuario_actual),
    ) -> None:
        if usuario.id_sesion_demo is None:
            return
        try:
            demo.consumir_cupo(db, usuario.id_sesion_demo, recurso)
        except demo.CupoAgotado as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error.detalle(),
            ) from error

    return consumir


cupo_de_exportacion = _cupo_de_la_demo("exportaciones")
cupo_de_importacion = _cupo_de_la_demo("importaciones")
