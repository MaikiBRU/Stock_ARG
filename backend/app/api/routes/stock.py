"""Endpoints de stock y movimientos (modulo D)."""

from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    cupo_de_exportacion,
    exigir_gestion,
    obtener_usuario_actual,
)
from app.core import tiempo
from app.db.session import get_db
from app.models import MovimientoStock, Producto, TipoMovimiento, Usuario
from app.schemas.comunes import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Pagina
from app.schemas.stock import (
    BajaEntrada,
    MovimientoEntrada,
    MovimientoSalida,
    ResumenStock,
)
from app.services import exportacion, nombres
from app.services import stock as servicio
from app.services.productos import ErrorDeProducto, NoEncontrado

router = APIRouter(prefix="/stock", tags=["stock"])

# El PDF se arma entero en memoria, asi que un archivo no puede
# traer filas sin limite.
MAX_FILAS_EXPORTACION = 5000


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


def _con_nombres(
    db: Session, movimientos: list[MovimientoStock], id_sesion_demo: str | None
) -> list[MovimientoSalida]:
    """Convierte los movimientos y les agrega los nombres para mostrar."""
    productos = nombres.de_productos(
        db, (m.id_producto for m in movimientos), id_sesion_demo
    )
    usuarios = nombres.de_usuarios(
        db, (m.id_usuario for m in movimientos), id_sesion_demo
    )
    salida = []
    for movimiento in movimientos:
        fila = MovimientoSalida.model_validate(movimiento)
        fila.producto = productos.get(movimiento.id_producto)
        fila.usuario = usuarios.get(movimiento.id_usuario)
        salida.append(fila)
    return salida


@router.get("/resumen", response_model=ResumenStock)
def resumen(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> ResumenStock:
    """Cuantos productos hay en cada estado (RF-D02)."""
    return ResumenStock(**servicio.resumen_de_stock(db, usuario.id_sesion_demo))


@router.get("/movimientos", response_model=Pagina[MovimientoSalida])
def listar_movimientos(
    id_producto: int | None = None,
    tipo: TipoMovimiento | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Pagina[MovimientoSalida]:
    """Historial de movimientos, filtrable (RF-D04)."""
    items, total = servicio.listar_movimientos(
        db,
        id_producto=id_producto,
        tipo=tipo,
        desde=desde,
        hasta=hasta,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
        id_sesion_demo=usuario.id_sesion_demo,
    )
    return Pagina[MovimientoSalida](
        items=_con_nombres(db, items, usuario.id_sesion_demo),
        total=total,
        pagina=pagina,
        limite=limite,
    )


@router.post(
    "/movimientos",
    response_model=MovimientoSalida,
    status_code=status.HTTP_201_CREATED,
)
def registrar_movimiento(
    datos: MovimientoEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> MovimientoSalida:
    """Movimiento manual. Propietario o encargado (RF-D03)."""
    try:
        movimiento = servicio.registrar_movimiento(
            db,
            id_producto=datos.id_producto,
            tipo=datos.tipo,
            cantidad=datos.cantidad,
            usuario=usuario,
            nota=datos.nota,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return _con_nombres(db, [movimiento], usuario.id_sesion_demo)[0]


@router.post(
    "/bajas",
    response_model=MovimientoSalida,
    status_code=status.HTTP_201_CREATED,
)
def registrar_baja(
    datos: BajaEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> MovimientoSalida:
    """Descarte de mercaderia. Propietario o encargado (RF-D06)."""
    try:
        _, movimiento = servicio.registrar_baja(
            db,
            id_producto=datos.id_producto,
            cantidad=datos.cantidad,
            motivo=datos.motivo,
            usuario=usuario,
            detalle=datos.detalle,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return _con_nombres(db, [movimiento], usuario.id_sesion_demo)[0]


# --- exportacion (RF-D09) ------------------------------------------------

ENCABEZADOS_MOVIMIENTOS = [
    "fecha",
    "producto",
    "tipo",
    "cantidad",
    "stock_resultante",
    "nota",
    "usuario",
]


@router.get(
    "/movimientos/exportar", dependencies=[Depends(cupo_de_exportacion)]
)
def exportar_movimientos(
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    id_producto: int | None = None,
    tipo: TipoMovimiento | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Response:
    """Descarga el historial filtrado en CSV o PDF (RF-D09)."""
    items, _ = servicio.listar_movimientos(
        db,
        id_producto=id_producto,
        tipo=tipo,
        desde=desde,
        hasta=hasta,
        desplazamiento=0,
        limite=MAX_FILAS_EXPORTACION,
        id_sesion_demo=usuario.id_sesion_demo,
    )

    # Se resuelven los nombres de una sola vez, en lugar de una consulta
    # por fila dentro del armado del archivo.
    ids = {m.id_producto for m in items}
    nombres = (
        {
            p.id: p.nombre
            for p in db.scalars(
                select(Producto).where(Producto.id.in_(ids))
            ).all()
        }
        if ids
        else {}
    )

    filas: list[list[object]] = [
        [
            tiempo.en_zona(m.fecha_hora).strftime("%d/%m/%Y %H:%M")
            if m.fecha_hora
            else None,
            nombres.get(m.id_producto, f"#{m.id_producto}"),
            m.tipo.value,
            m.cantidad,
            m.stock_resultante,
            m.nota,
            m.id_usuario,
        ]
        for m in items
    ]

    if formato == "pdf":
        cuerpo = exportacion.a_pdf(
            "Movimientos de stock", ENCABEZADOS_MOVIMIENTOS, filas
        )
        tipo_mime = "application/pdf"
        nombre = exportacion.nombre_de_archivo("movimientos", "pdf")
    else:
        cuerpo = exportacion.a_csv(ENCABEZADOS_MOVIMIENTOS, filas)
        tipo_mime = "text/csv; charset=utf-8"
        nombre = exportacion.nombre_de_archivo("movimientos", "csv")

    return Response(
        content=cuerpo,
        media_type=tipo_mime,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
