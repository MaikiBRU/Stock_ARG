"""Dependencias compartidas por los endpoints."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import ajustes_vivos
from app.core.security import leer_token
from app.db.session import get_db
from app.models import Rol, Usuario

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


def obtener_usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Resuelve el usuario autenticado a partir del token.

    Solo acepta tokens de tipo "acceso". Un token de demo llega aca y se
    rechaza, de modo que todo endpoint que dependa de esta funcion queda
    cerrado al sandbox por omision: olvidarse de proteger uno nuevo falla
    del lado seguro.
    """
    if credenciales is None or not credenciales.credentials:
        raise CREDENCIALES_INVALIDAS

    try:
        carga = leer_token(credenciales.credentials, tipo_esperado="acceso")
    except jwt.PyJWTError as error:
        raise CREDENCIALES_INVALIDAS from error

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

    if not usuario.verificado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta todavia no fue verificada.",
        )

    # Los parametros configurables se refrescan aca y no al arrancar: un
    # cambio guardado desde la pantalla tiene efecto en la peticion
    # siguiente, sin reiniciar el proceso.
    from app.services.administracion import leer_configuracion

    ajustes_vivos.fijar(leer_configuracion(db, usuario.id_sesion_demo))

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
