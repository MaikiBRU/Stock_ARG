"""Endpoints de categorias (RF-C03)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_gestion, obtener_usuario_actual
from app.db.session import get_db
from app.models import Usuario
from app.schemas.auth import MensajeSalida
from app.schemas.producto import CategoriaEntrada, CategoriaSalida
from app.services import productos as servicio

router = APIRouter(prefix="/categorias", tags=["categorias"])


def _error(excepcion: servicio.ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, servicio.NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


@router.get("", response_model=list[CategoriaSalida])
def listar(
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> list[CategoriaSalida]:
    """Categorias disponibles. Las ve cualquier rol."""
    return [
        CategoriaSalida.model_validate(c)
        for c in servicio.listar_categorias(
            db,
            incluir_inactivas=incluir_inactivas,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    ]


@router.post(
    "", response_model=CategoriaSalida, status_code=status.HTTP_201_CREATED
)
def crear(
    datos: CategoriaEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CategoriaSalida:
    """Alta de categoria. Propietario o encargado."""
    try:
        categoria = servicio.crear_categoria(
            db,
            datos.nombre,
            datos.descripcion,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return CategoriaSalida.model_validate(categoria)


@router.put("/{id_categoria}", response_model=CategoriaSalida)
def actualizar(
    id_categoria: int,
    datos: CategoriaEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CategoriaSalida:
    """Edicion de categoria. Propietario o encargado."""
    try:
        categoria = servicio.actualizar_categoria(
            db,
            id_categoria,
            datos.nombre,
            datos.descripcion,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return CategoriaSalida.model_validate(categoria)


@router.delete("/{id_categoria}", response_model=MensajeSalida)
def desactivar(
    id_categoria: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> MensajeSalida:
    """Baja logica de categoria. Propietario o encargado."""
    try:
        servicio.desactivar_categoria(db, id_categoria, usuario.id_sesion_demo)
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return MensajeSalida(mensaje="La categoria se desactivo.")
