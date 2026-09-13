"""Endpoints de medios de cobro (RF-E06, RF-I06)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_administracion, obtener_usuario_actual
from app.db.session import get_db
from app.models import Usuario
from app.schemas.venta import MedioPagoEntrada, MedioPagoSalida
from app.services import medios_pago as servicio
from app.services.productos import ErrorDeProducto, NoEncontrado

router = APIRouter(prefix="/medios-pago", tags=["medios de pago"])


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


@router.get("", response_model=list[MedioPagoSalida])
def listar(
    solo_activos: bool = True,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> list[MedioPagoSalida]:
    """Medios habilitados. Los necesita cualquiera que cobre."""
    return [
        MedioPagoSalida.model_validate(m)
        for m in servicio.listar(db, solo_activos=solo_activos)
    ]


@router.post(
    "/sembrar",
    response_model=list[MedioPagoSalida],
    status_code=status.HTTP_201_CREATED,
)
def sembrar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> list[MedioPagoSalida]:
    """Carga los medios habituales en un comercio recien instalado."""
    creados = servicio.sembrar_iniciales(db)
    db.commit()
    return [MedioPagoSalida.model_validate(m) for m in creados]


@router.post(
    "", response_model=MedioPagoSalida, status_code=status.HTTP_201_CREATED
)
def crear(
    datos: MedioPagoEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> MedioPagoSalida:
    """Alta de medio de cobro. Solo el propietario (RF-I06)."""
    try:
        medio = servicio.crear(db, datos.nombre, datos.es_efectivo)
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return MedioPagoSalida.model_validate(medio)


@router.post("/{id_medio}/habilitar", response_model=MedioPagoSalida)
def habilitar(
    id_medio: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> MedioPagoSalida:
    """Vuelve a habilitar un medio de cobro."""
    try:
        medio = servicio.cambiar_estado(db, id_medio, activo=True)
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return MedioPagoSalida.model_validate(medio)


@router.delete("/{id_medio}", response_model=MedioPagoSalida)
def deshabilitar(
    id_medio: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> MedioPagoSalida:
    """Deshabilita un medio de cobro, sin borrarlo."""
    try:
        medio = servicio.cambiar_estado(db, id_medio, activo=False)
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return MedioPagoSalida.model_validate(medio)
