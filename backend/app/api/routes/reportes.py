"""Endpoints de reportes (modulo H)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_administracion, exigir_gestion
from app.db.session import get_db
from app.models import Usuario
from app.schemas.compra import (
    ComprasPeriodoSalida,
    CorteCategoriaSalida,
    CorteMedioPagoSalida,
    PuntoSerieSalida,
    RankingSalida,
    RentabilidadSalida,
    VentasPeriodoSalida,
)
from app.services import exportacion, reportes
from app.services.productos import ErrorDeProducto

router = APIRouter(prefix="/reportes", tags=["reportes"])

PERIODO = Query(default=None, pattern="^(hoy|semana|mes)$")


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=excepcion.mensaje
    )


@router.get("/ventas", response_model=VentasPeriodoSalida)
def ventas(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> VentasPeriodoSalida:
    """Total facturado, tickets y ticket promedio (RF-H01)."""
    try:
        datos = reportes.ventas_por_periodo(
            db, periodo=periodo, desde=desde, hasta=hasta
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return VentasPeriodoSalida(**datos)


@router.get("/ventas/serie", response_model=list[PuntoSerieSalida])
def serie(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> list[PuntoSerieSalida]:
    """Facturado dia por dia, para el grafico."""
    try:
        puntos = reportes.serie_diaria(
            db, periodo=periodo or "mes", desde=desde, hasta=hasta
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return [PuntoSerieSalida(**p) for p in puntos]


@router.get("/mas-vendidos", response_model=RankingSalida)
def mas_vendidos(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    ordenar_por: str = Query(
        default="unidades", pattern="^(unidades|facturacion)$"
    ),
    limite: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> RankingSalida:
    """Ranking de productos (RF-H02)."""
    try:
        datos = reportes.mas_vendidos(
            db,
            periodo=periodo,
            desde=desde,
            hasta=hasta,
            ordenar_por=ordenar_por,
            limite=limite,
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return RankingSalida(**datos)


@router.get("/medios-pago", response_model=CorteMedioPagoSalida)
def medios_pago(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CorteMedioPagoSalida:
    """Cuanto entro por cada forma de cobro (RF-H03)."""
    try:
        datos = reportes.por_medio_de_pago(
            db, periodo=periodo, desde=desde, hasta=hasta
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return CorteMedioPagoSalida(**datos)


@router.get("/categorias", response_model=CorteCategoriaSalida)
def categorias(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CorteCategoriaSalida:
    """Cuanto se vendio de cada rubro (RF-H03)."""
    try:
        datos = reportes.por_categoria(
            db, periodo=periodo, desde=desde, hasta=hasta
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return CorteCategoriaSalida(**datos)


@router.get("/compras", response_model=ComprasPeriodoSalida)
def compras(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ComprasPeriodoSalida:
    """Cuanto se gasto en mercaderia."""
    try:
        datos = reportes.compras_por_periodo(
            db, periodo=periodo, desde=desde, hasta=hasta
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return ComprasPeriodoSalida(**datos)


@router.get("/rentabilidad", response_model=RentabilidadSalida)
def rentabilidad(
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_administracion),
) -> RentabilidadSalida:
    """Ganancia por producto (RF-H06).

    Solo el propietario: el costo y el margen son informacion del
    negocio, no del mostrador.
    """
    try:
        datos = reportes.rentabilidad(
            db, periodo=periodo, desde=desde, hasta=hasta, limite=limite
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return RentabilidadSalida(**datos)


@router.get("/exportar")
def exportar(
    reporte: str = Query(pattern="^(mas-vendidos|medios-pago|categorias)$"),
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    periodo: str | None = PERIODO,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Response:
    """Descarga un reporte en CSV o PDF (RF-H08).

    La rentabilidad no se exporta por aca: es del propietario y tiene su
    propia ruta, para que el permiso no dependa de un parametro.
    """
    try:
        if reporte == "mas-vendidos":
            datos = reportes.mas_vendidos(
                db, periodo=periodo, desde=desde, hasta=hasta, limite=200
            )
            titulo = "Productos mas vendidos"
            encabezados = ["producto", "unidades", "facturado"]
            filas = [
                [f["nombre"], f["unidades"], f["facturado"]]
                for f in datos["ranking"]
            ]
        elif reporte == "medios-pago":
            datos = reportes.por_medio_de_pago(
                db, periodo=periodo, desde=desde, hasta=hasta
            )
            titulo = "Ventas por medio de pago"
            encabezados = ["medio", "ventas", "total"]
            filas = [
                [f["nombre"], f["cantidad_ventas"], f["total"]]
                for f in datos["detalle"]
            ]
        else:
            datos = reportes.por_categoria(
                db, periodo=periodo, desde=desde, hasta=hasta
            )
            titulo = "Ventas por categoria"
            encabezados = ["categoria", "unidades", "total"]
            filas = [
                [f["nombre"], f["unidades"], f["total"]]
                for f in datos["detalle"]
            ]
    except ErrorDeProducto as error:
        raise _error(error) from error

    titulo = f"{titulo} ({datos['desde']} a {datos['hasta']})"
    base = reporte.replace("-", "_")

    if formato == "pdf":
        cuerpo = exportacion.a_pdf(titulo, encabezados, filas)
        tipo = "application/pdf"
        nombre = exportacion.nombre_de_archivo(base, "pdf")
    else:
        cuerpo = exportacion.a_csv(encabezados, filas)
        tipo = "text/csv; charset=utf-8"
        nombre = exportacion.nombre_de_archivo(base, "csv")

    return Response(
        content=cuerpo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
