"""Panel principal y administracion (modulos B e I)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_administracion, exigir_gestion, ip_del_cliente
from app.db.session import get_db
from app.models import Usuario
from app.schemas.admin import (
    AuditoriaSalida,
    ConfiguracionEntrada,
    ConfiguracionSalida,
    PanelSalida,
    RolEntrada,
    UsuarioAdminSalida,
    UsuarioNuevoEntrada,
)
from app.schemas.comunes import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Pagina
from app.schemas.producto import ProductoSalida
from app.services import administracion as servicio
from app.services import auditoria as registro
from app.services import dashboard
from app.services.productos import ErrorDeProducto, NoEncontrado

router = APIRouter(tags=["administracion"])


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


def _a_salida_admin(usuario: Usuario) -> UsuarioAdminSalida:
    """Arma la ficha de un usuario para la administracion."""
    salida = UsuarioAdminSalida.model_validate(usuario)
    salida.bloqueado = usuario.bloqueado_hasta is not None
    return salida


# --- panel principal (modulo B) ------------------------------------------


@router.get("/panel", response_model=PanelSalida)
def panel(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> PanelSalida:
    """Indicadores del dia, alertas y grafico (RF-B01 a RF-B08)."""
    datos = dashboard.armar(db, ver_costo=usuario.puede_administrar)

    for clave in ("bajo_minimo", "proximos_a_vencer", "vencidos"):
        salidas = []
        for producto in datos[clave]:
            salida = ProductoSalida.model_validate(producto)
            if usuario.puede_administrar:
                salida.margen = producto.margen
            else:
                salida.precio_costo = None
            salidas.append(salida)
        datos[clave] = salidas

    return PanelSalida(**datos)


# --- usuarios (RF-I01 a RF-I03) ------------------------------------------


@router.get("/usuarios", response_model=Pagina[UsuarioAdminSalida])
def listar_usuarios(
    incluir_inactivos: bool = True,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> Pagina[UsuarioAdminSalida]:
    """Listado de usuarios. Solo el propietario (RF-I01)."""
    items, total = servicio.listar_usuarios(
        db,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
    )
    return Pagina[UsuarioAdminSalida](
        items=[_a_salida_admin(u) for u in items],
        total=total,
        pagina=pagina,
        limite=limite,
    )


@router.post(
    "/usuarios",
    response_model=UsuarioAdminSalida,
    status_code=status.HTTP_201_CREATED,
)
def crear_usuario(
    datos: UsuarioNuevoEntrada,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> UsuarioAdminSalida:
    """Alta de usuario. Solo el propietario (RF-I01)."""
    try:
        nuevo = servicio.crear_usuario(
            db,
            email=datos.email,
            nombre=datos.nombre,
            contrasena=datos.contrasena,
            rol=datos.rol,
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error

    registro.registrar(
        db,
        usuario=usuario,
        accion="usuario.crear",
        entidad="usuario",
        id_entidad=nuevo.id,
        detalle={"email": nuevo.email, "rol": nuevo.rol.value},
        ip=ip_del_cliente(request),
    )
    db.commit()
    return _a_salida_admin(nuevo)


@router.put("/usuarios/{id_usuario}/rol", response_model=UsuarioAdminSalida)
def cambiar_rol(
    id_usuario: int,
    datos: RolEntrada,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> UsuarioAdminSalida:
    """Cambia el rol de un usuario (RF-I01, RF-I03)."""
    try:
        modificado = servicio.cambiar_rol(db, id_usuario, datos.rol)
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error

    registro.registrar(
        db,
        usuario=usuario,
        accion="usuario.cambiar_rol",
        entidad="usuario",
        id_entidad=id_usuario,
        detalle={"rol": datos.rol.value},
        ip=ip_del_cliente(request),
    )
    db.commit()
    return _a_salida_admin(modificado)


@router.post(
    "/usuarios/{id_usuario}/habilitar", response_model=UsuarioAdminSalida
)
def habilitar(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> UsuarioAdminSalida:
    """Vuelve a habilitar una cuenta y le saca el bloqueo."""
    try:
        modificado = servicio.cambiar_estado(
            db, id_usuario, activo=True, ejecutor=usuario
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error

    registro.registrar(
        db,
        usuario=usuario,
        accion="usuario.habilitar",
        entidad="usuario",
        id_entidad=id_usuario,
        ip=ip_del_cliente(request),
    )
    db.commit()
    return _a_salida_admin(modificado)


@router.delete("/usuarios/{id_usuario}", response_model=UsuarioAdminSalida)
def deshabilitar(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> UsuarioAdminSalida:
    """Da de baja una cuenta sin borrarla (RF-I02, RF-I03)."""
    try:
        modificado = servicio.cambiar_estado(
            db, id_usuario, activo=False, ejecutor=usuario
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error

    registro.registrar(
        db,
        usuario=usuario,
        accion="usuario.deshabilitar",
        entidad="usuario",
        id_entidad=id_usuario,
        ip=ip_del_cliente(request),
    )
    db.commit()
    return _a_salida_admin(modificado)


# --- auditoria (RF-I04) --------------------------------------------------


@router.get("/auditoria", response_model=Pagina[AuditoriaSalida])
def auditoria(
    accion: str | None = Query(default=None, max_length=60),
    entidad: str | None = Query(default=None, max_length=40),
    id_usuario: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> Pagina[AuditoriaSalida]:
    """Quien hizo que y cuando. Solo el propietario (RF-I04)."""
    items, total = registro.listar(
        db,
        accion=accion,
        entidad=entidad,
        id_usuario=id_usuario,
        desde=desde,
        hasta=hasta,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
    )
    return Pagina[AuditoriaSalida](
        items=[AuditoriaSalida.model_validate(a) for a in items],
        total=total,
        pagina=pagina,
        limite=limite,
    )


# --- configuracion (RF-I06) ----------------------------------------------


@router.get("/configuracion", response_model=ConfiguracionSalida)
def leer_configuracion(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ConfiguracionSalida:
    """Parametros del comercio. Los lee la gestion."""
    return ConfiguracionSalida(valores=servicio.leer_configuracion(db))


@router.put("/configuracion", response_model=ConfiguracionSalida)
def guardar_configuracion(
    datos: ConfiguracionEntrada,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> ConfiguracionSalida:
    """Cambia los parametros. Solo el propietario (RF-I06)."""
    try:
        valores = servicio.guardar_configuracion(db, datos.cambios)
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error

    registro.registrar(
        db,
        usuario=usuario,
        accion="configuracion.guardar",
        entidad="configuracion",
        detalle=datos.cambios,
        ip=ip_del_cliente(request),
    )
    db.commit()
    return ConfiguracionSalida(valores=valores)
