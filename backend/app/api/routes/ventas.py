"""Endpoints del punto de venta (modulo E)."""

from datetime import date
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    cupo_de_exportacion,
    exigir_gestion,
    obtener_usuario_actual,
)
from app.core import tiempo
from app.db.session import get_db
from app.models import EstadoVenta, Usuario, Venta
from app.schemas.comunes import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Pagina
from app.schemas.venta import (
    AnulacionEntrada,
    VentaEntrada,
    VentaResumenSalida,
    VentaSalida,
)
from app.services import exportacion, nombres
from app.services import ventas as servicio
from app.services.productos import ErrorDeProducto, NoEncontrado

router = APIRouter(prefix="/ventas", tags=["ventas"])

MAX_FILAS_EXPORTACION = 5000


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP.

    El detalle de los faltantes de stock viaja aparte del mensaje, para
    que la pantalla pueda marcar cada linea sin parsear texto.
    """
    if isinstance(excepcion, NoEncontrado):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=excepcion.mensaje
        )

    cuerpo: dict | str = excepcion.mensaje
    if isinstance(excepcion, servicio.StockInsuficiente):
        cuerpo = {
            "mensaje": excepcion.mensaje,
            "codigo": excepcion.codigo,
            "faltantes": excepcion.faltantes,
        }
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=cuerpo)


def _visible_para(usuario: Usuario, venta: Venta) -> bool:
    """Decide si el rol puede ver ese ticket.

    Quien atiende el mostrador ve lo que cobro el mismo; el historial
    completo es de la gestion (matriz de permisos, seccion 05).
    """
    return usuario.puede_gestionar or venta.id_usuario == usuario.id


def _con_nombres[S: (VentaSalida, VentaResumenSalida)](
    db: Session,
    ventas: list[Venta],
    esquema: type[S],
    id_sesion_demo: str | None,
) -> list[S]:
    """Convierte las ventas y les agrega los nombres para mostrar."""
    medios = nombres.de_medios(
        db, (v.id_medio_pago for v in ventas), id_sesion_demo
    )
    usuarios = nombres.de_usuarios(
        db, (v.id_usuario for v in ventas), id_sesion_demo
    )
    clientes = nombres.de_clientes(
        db, (v.id_cliente for v in ventas), id_sesion_demo
    )
    salida = []
    for venta in ventas:
        fila = esquema.model_validate(venta)
        fila.medio_pago = medios.get(venta.id_medio_pago)
        fila.vendedor = usuarios.get(venta.id_usuario)
        fila.cliente = (
            clientes.get(venta.id_cliente) if venta.id_cliente else None
        )
        salida.append(fila)
    return salida


@router.get("", response_model=Pagina[VentaResumenSalida])
def listar(
    desde: date | None = None,
    hasta: date | None = None,
    id_usuario: int | None = None,
    id_cliente: int | None = None,
    id_medio_pago: int | None = None,
    estado: EstadoVenta | None = None,
    busqueda: str | None = Query(default=None, max_length=120),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Pagina[VentaResumenSalida]:
    """Historial con filtros (RF-E13).

    Un vendedor ve unicamente sus ventas: el filtro se fuerza al margen
    de lo que venga en la peticion, asi pedir otro id_usuario no sirve
    para espiar lo que cobraron los demas.
    """
    if not usuario.puede_gestionar:
        id_usuario = usuario.id

    items, total = servicio.listar(
        db,
        desde=tiempo.inicio_del_dia(desde) if desde else None,
        hasta=tiempo.fin_del_dia(hasta) if hasta else None,
        id_usuario=id_usuario,
        id_cliente=id_cliente,
        id_medio_pago=id_medio_pago,
        estado=estado,
        busqueda=busqueda,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
        id_sesion_demo=usuario.id_sesion_demo,
    )
    return Pagina[VentaResumenSalida](
        items=_con_nombres(
            db, items, VentaResumenSalida, usuario.id_sesion_demo
        ),
        total=total,
        pagina=pagina,
        limite=limite,
    )


@router.get("/exportar", dependencies=[Depends(cupo_de_exportacion)])
def exportar(
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    desde: date | None = None,
    hasta: date | None = None,
    estado: EstadoVenta | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Response:
    """Descarga el historial filtrado (RF-H08)."""
    items, _ = servicio.listar(
        db,
        desde=tiempo.inicio_del_dia(desde) if desde else None,
        hasta=tiempo.fin_del_dia(hasta) if hasta else None,
        estado=estado,
        desplazamiento=0,
        limite=MAX_FILAS_EXPORTACION,
        id_sesion_demo=usuario.id_sesion_demo,
    )

    encabezados = [
        "ticket",
        "fecha",
        "articulos",
        "descuento",
        "total",
        "estado",
        "usuario",
        "cliente",
    ]
    filas: list[list[object]] = [
        [
            v.id,
            tiempo.en_zona(v.fecha_hora).strftime("%d/%m/%Y %H:%M")
            if v.fecha_hora
            else None,
            v.cantidad_articulos,
            v.descuento,
            v.total,
            v.estado.value,
            fila.vendedor,
            fila.cliente,
        ]
        for v, fila in zip(
            items,
            _con_nombres(db, items, VentaResumenSalida, usuario.id_sesion_demo),
            strict=True,
        )
    ]

    if formato == "pdf":
        cuerpo = exportacion.a_pdf("Historial de ventas", encabezados, filas)
        tipo = "application/pdf"
        nombre = exportacion.nombre_de_archivo("ventas", "pdf")
    else:
        cuerpo = exportacion.a_csv(encabezados, filas)
        tipo = "text/csv; charset=utf-8"
        nombre = exportacion.nombre_de_archivo("ventas", "csv")

    return Response(
        content=cuerpo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post(
    "", response_model=VentaSalida, status_code=status.HTTP_201_CREATED
)
def registrar(
    datos: VentaEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> VentaSalida:
    """Registra una venta. La puede hacer cualquier rol (RF-E01)."""
    lineas = [
        servicio.LineaPedida(
            id_producto=item.id_producto,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            descuento=item.descuento,
        )
        for item in datos.items
    ]

    try:
        venta = servicio.registrar(
            db,
            lineas=lineas,
            id_medio_pago=datos.id_medio_pago,
            usuario=usuario,
            id_cliente=datos.id_cliente,
            recibido=datos.recibido,
            descuento_general=datos.descuento or Decimal("0.00"),
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except ErrorDeProducto as error:
        # Nada a medias: si algo falla, ni la venta ni el descuento de
        # stock quedan escritos.
        db.rollback()
        raise _error(error) from error

    db.commit()
    return _con_nombres(db, [venta], VentaSalida, usuario.id_sesion_demo)[0]


@router.get("/{id_venta}", response_model=VentaSalida)
def obtener(
    id_venta: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> VentaSalida:
    """Detalle completo del ticket (RF-E14)."""
    try:
        venta = servicio.obtener(db, id_venta, usuario.id_sesion_demo)
    except ErrorDeProducto as error:
        raise _error(error) from error

    if not _visible_para(usuario, venta):
        # 404 y no 403: un 403 confirmaria que el ticket existe y de
        # quien es.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la venta.",
        )
    return _con_nombres(db, [venta], VentaSalida, usuario.id_sesion_demo)[0]


@router.get(
    "/{id_venta}/comprobante", dependencies=[Depends(cupo_de_exportacion)]
)
def comprobante(
    id_venta: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Response:
    """Comprobante del ticket en PDF (RF-E15).

    Es un comprobante interno: no reemplaza una factura, porque el
    sistema no emite documentos fiscales.
    """
    try:
        venta = servicio.obtener(db, id_venta, usuario.id_sesion_demo)
    except ErrorDeProducto as error:
        raise _error(error) from error

    if not _visible_para(usuario, venta):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la venta.",
        )

    encabezados = ["cantidad", "producto", "precio", "descuento", "subtotal"]
    filas: list[list[object]] = [
        [
            item.cantidad,
            item.nombre_producto,
            item.precio_unitario,
            item.descuento,
            item.subtotal,
        ]
        for item in venta.items
    ]
    if venta.descuento:
        filas.append(["", "Descuento general", "", "", f"-{venta.descuento}"])
    filas.append(["", "TOTAL", "", "", venta.total])
    if venta.recibido is not None:
        filas.append(["", "Recibido", "", "", venta.recibido])
        filas.append(["", "Vuelto", "", "", venta.vuelto])

    titulo = f"Comprobante interno - Venta #{venta.id}"
    if venta.estado is EstadoVenta.ANULADA:
        titulo += " (ANULADA)"

    cuerpo = exportacion.a_pdf(titulo, encabezados, filas)
    nombre = f"comprobante-{venta.id}.pdf"
    return Response(
        content=cuerpo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post("/{id_venta}/anular", response_model=VentaSalida)
def anular(
    id_venta: int,
    datos: AnulacionEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> VentaSalida:
    """Anula una venta y repone el stock (RF-E12)."""
    try:
        venta = servicio.anular(
            db,
            id_venta,
            usuario,
            datos.motivo,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return _con_nombres(db, [venta], VentaSalida, usuario.id_sesion_demo)[0]
