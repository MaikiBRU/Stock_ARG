"""Endpoints de la demo publica (modulo J)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_demo, ip_del_cliente
from app.core.config import get_settings
from app.core.security import comparar_seguro, hash_opaco
from app.db.session import get_db
from app.models import Rol, SesionDemo, Usuario
from app.schemas.auth import MensajeSalida, UsuarioSalida
from app.schemas.demo import (
    CupoSalida,
    EstadoDemoSalida,
    LimpiezaSalida,
    RolDemoEntrada,
    SesionDemoSalida,
)
from app.services import demo as servicio
from app.services.limites import clave_de_ip, limitador

UNA_HORA = 3600
# Reiniciar vuelve a sembrar todo el comercio: es la operacion mas cara
# que un visitante anonimo puede pedir.
MAX_REINICIOS_POR_HORA = 6
MAX_LIMPIEZAS_POR_HORA = 30


def demo_habilitada() -> None:
    """Con la demo apagada, /demo/* no existe (RF-J11)."""
    if not get_settings().demo_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )


router = APIRouter(
    prefix="/demo", tags=["demo"], dependencies=[Depends(demo_habilitada)]
)


def _salida(sesion: SesionDemo, usuario: Usuario) -> SesionDemoSalida:
    """Token del sandbox para ese usuario."""
    return SesionDemoSalida(
        access_token=servicio.emitir_token(sesion, usuario),
        expira_en=servicio.vence(sesion),
        usuario=UsuarioSalida.model_validate(usuario),
        roles=list(Rol),
    )


def _sesion_de(db: Session, usuario: Usuario) -> SesionDemo:
    """Sesion del sandbox en el que esta el usuario."""
    sesion = db.get(SesionDemo, usuario.id_sesion_demo)
    if sesion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay una demo en curso.",
        )
    return sesion


@router.post(
    "/sesion",
    response_model=SesionDemoSalida,
    status_code=status.HTTP_201_CREATED,
)
def crear_sesion(
    request: Request,
    db: Session = Depends(get_db),
) -> SesionDemoSalida:
    """Abre un sandbox sin credenciales ni cuerpo (RF-J01, RF-J07)."""
    ajustes = get_settings()
    ip = ip_del_cliente(request)
    if not limitador.permitido(
        clave_de_ip(ip, "demo"), ajustes.demo_rate_limit_per_hour, UNA_HORA
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Se abrieron demasiadas demos. Pruebe mas tarde.",
        )

    try:
        sesion, propietario = servicio.crear_sesion(db, ip)
    except servicio.DemoSinCapacidad as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error.mensaje,
            headers={"Retry-After": "300"},
        ) from error
    return _salida(sesion, propietario)


@router.get("/sesion", response_model=EstadoDemoSalida)
def estado(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_demo),
) -> EstadoDemoSalida:
    """Tiempo restante y cupos, para la franja de la demo (RF-J10)."""
    sesion = _sesion_de(db, usuario)
    vence = servicio.vence(sesion)
    restante = (vence - datetime.now(UTC)).total_seconds()
    return EstadoDemoSalida(
        expira_en=servicio.expira_en(sesion),
        vence_por_inactividad_en=servicio.vence_por_inactividad(sesion),
        segundos_restantes=max(0, int(restante)),
        rol=usuario.rol,
        cupos={
            clave: CupoSalida(**valor)
            for clave, valor in servicio.estado_de_cupos(db, sesion).items()
        },
    )


@router.post("/sesion/rol", response_model=SesionDemoSalida)
def cambiar_rol(
    datos: RolDemoEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_demo),
) -> SesionDemoSalida:
    """Recorre la demo con otro de los tres roles."""
    sesion = _sesion_de(db, usuario)
    elegido = servicio.usuario_por_rol(db, sesion.id, datos.rol)
    if elegido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay un usuario activo con ese rol en la demo.",
        )
    return _salida(sesion, elegido)


@router.post("/sesion/reiniciar", response_model=SesionDemoSalida)
def reiniciar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_demo),
) -> SesionDemoSalida:
    """Vuelve el sandbox a cero sin cambiar de token (RF-J08)."""
    id_sesion, rol = usuario.id_sesion_demo, usuario.rol
    clave = f"demo-reinicio:{hash_opaco(id_sesion)}"
    if not limitador.permitido(clave, MAX_REINICIOS_POR_HORA, UNA_HORA):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="La demo se reinicio demasiadas veces. Pruebe mas tarde.",
        )

    try:
        sesion = servicio.reiniciar(db, id_sesion)
    except servicio.ErrorDeDemo as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=error.mensaje
        ) from error

    # La semilla trae un usuario por rol, asi que siempre hay a quien
    # devolverle el token.
    elegido = servicio.usuario_por_rol(db, id_sesion, rol)
    return _salida(sesion, elegido)


@router.post("/sesion/terminar", response_model=MensajeSalida)
def terminar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_demo),
) -> MensajeSalida:
    """Borra el sandbox y todos sus datos en el acto (RF-J08)."""
    servicio.terminar(db, usuario.id_sesion_demo)
    return MensajeSalida(mensaje="La demo termino y sus datos se borraron.")


@router.post("/mantenimiento/limpieza", response_model=LimpiezaSalida)
def limpieza(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Header(
        default=None, alias="X-Demo-Mantenimiento-Token"
    ),
) -> LimpiezaSalida:
    """Limpieza manual, para dispararla desde afuera del proceso (RF-J09).

    Sin token configurado responde 404: nunca queda abierta por omision.
    Un token equivocado tambien da 404, asi no confirma que la ruta
    existe.
    """
    if not limitador.permitido(
        clave_de_ip(ip_del_cliente(request), "demo-limpieza"),
        MAX_LIMPIEZAS_POR_HORA,
        UNA_HORA,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Espere unos minutos.",
        )
    configurado = get_settings().demo_maintenance_token
    if not configurado or not token or not comparar_seguro(token, configurado):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    return LimpiezaSalida(eliminadas=servicio.purgar_vencidas(db))
