"""Compras a proveedores (RF-G03, RF-G04).

Es el camino inverso de la venta: en lugar de descontar, suma. Rigen las
mismas dos reglas, por los mismos motivos: el total lo calcula el
servidor y el stock se toca con la fila bloqueada, dentro de la misma
transaccion que escribe la compra.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, lazyload

from app.core import tiempo
from app.models import (
    Compra,
    CompraItem,
    EstadoCompra,
    Producto,
    TipoMovimiento,
    Usuario,
)
from app.services import proveedores as servicio_proveedores
from app.services.productos import ErrorDeProducto, NoEncontrado

CENTAVO = Decimal("0.01")
MAX_ITEMS = 500


class ErrorDeCompra(ErrorDeProducto):
    """Falla esperable al registrar una compra."""


@dataclass
class LineaComprada:
    """Una linea del remito tal como se carga."""

    id_producto: int
    cantidad: int
    costo_unitario: Decimal


def _ahora() -> datetime:
    """Momento actual en UTC."""
    return datetime.now(UTC)


def consolidar(lineas: list[LineaComprada]) -> list[LineaComprada]:
    """Junta el mismo producto repetido en una sola linea.

    El costo se promedia ponderado por cantidad: si el mismo articulo
    viene en dos renglones a precios distintos, quedarse con uno de los
    dos daria un costo que no es el que se pago.
    """
    juntadas: dict[int, LineaComprada] = {}
    for linea in lineas:
        previa = juntadas.get(linea.id_producto)
        if previa is None:
            juntadas[linea.id_producto] = LineaComprada(
                id_producto=linea.id_producto,
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
            )
        else:
            total_previo = previa.costo_unitario * previa.cantidad
            total_nuevo = linea.costo_unitario * linea.cantidad
            previa.cantidad += linea.cantidad
            previa.costo_unitario = (
                (total_previo + total_nuevo) / previa.cantidad
            ).quantize(CENTAVO)
    return list(juntadas.values())


def registrar(
    db: Session,
    *,
    lineas: list[LineaComprada],
    id_proveedor: int,
    usuario: Usuario,
    fecha: date | None = None,
    comprobante: str | None = None,
    notas: str | None = None,
    actualizar_costo: bool = True,
    id_sesion_demo: str | None = None,
) -> Compra:
    """Registra una compra y da entrada al stock (RF-G03)."""
    lineas = consolidar(lineas)

    if not lineas:
        raise ErrorDeCompra(
            "La compra tiene que incluir al menos un producto.", "sin_items"
        )
    if len(lineas) > MAX_ITEMS:
        raise ErrorDeCompra(
            f"Una compra no puede tener mas de {MAX_ITEMS} lineas.",
            "demasiados_items",
        )
    for linea in lineas:
        if linea.cantidad <= 0:
            raise ErrorDeCompra(
                "La cantidad de cada linea tiene que ser mayor a cero.",
                "cantidad_invalida",
            )
        if linea.costo_unitario < 0:
            raise ErrorDeCompra(
                "El costo no puede ser negativo.", "costo_invalido"
            )

    proveedor = servicio_proveedores.obtener(db, id_proveedor, id_sesion_demo)
    if not proveedor.activo:
        raise ErrorDeCompra(
            f'El proveedor "{proveedor.razon_social}" esta dado de baja.',
            "proveedor_inactivo",
        )

    fecha = fecha or tiempo.hoy()
    if fecha > tiempo.hoy():
        # Una compra con fecha futura descuadra cualquier reporte por
        # periodo y no corresponde a mercaderia que ya entro.
        raise ErrorDeCompra(
            "La fecha de la compra no puede ser futura.", "fecha_futura"
        )

    ids = [linea.id_producto for linea in lineas]
    filas = db.scalars(
        select(Producto)
        .where(
            Producto.id.in_(ids),
            Producto.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Producto.id_sesion_demo == id_sesion_demo,
        )
        # Sin esto, la categoria y el proveedor entran con un LEFT JOIN
        # y PostgreSQL rechaza el FOR UPDATE sobre el lado nulable.
        .options(lazyload("*"))
        .order_by(Producto.id)
        .with_for_update()
    ).all()
    productos = {p.id: p for p in filas}

    compra = Compra(
        fecha=fecha,
        registrada_en=_ahora(),
        id_proveedor=proveedor.id,
        id_usuario=usuario.id,
        comprobante=(comprobante or "").strip() or None,
        notas=(notas or "").strip() or None,
        total=Decimal("0.00"),
        id_sesion_demo=id_sesion_demo,
    )

    total = Decimal("0.00")
    for linea in lineas:
        producto = productos.get(linea.id_producto)
        if producto is None:
            raise NoEncontrado(
                f"No existe el producto con id {linea.id_producto}.",
                "no_encontrado",
            )

        costo = linea.costo_unitario.quantize(CENTAVO)
        subtotal = (costo * linea.cantidad).quantize(CENTAVO)

        compra.items.append(
            CompraItem(
                id_producto=producto.id,
                nombre_producto=producto.nombre,
                cantidad=linea.cantidad,
                costo_unitario=costo,
                subtotal=subtotal,
                id_sesion_demo=id_sesion_demo,
            )
        )
        total += subtotal

        if actualizar_costo and costo > 0:
            # El costo del producto pasa a ser el de la ultima compra:
            # es el que hace que el margen diga algo real.
            producto.precio_costo = costo

    compra.total = total.quantize(CENTAVO)
    db.add(compra)
    db.flush()

    from app.services import stock as servicio_stock

    for linea in lineas:
        servicio_stock.registrar_movimiento(
            db,
            id_producto=linea.id_producto,
            tipo=TipoMovimiento.ENTRADA,
            cantidad=linea.cantidad,
            usuario=usuario,
            nota=f"Compra #{compra.id}",
            id_compra=compra.id,
            id_sesion_demo=id_sesion_demo,
        )

    db.flush()
    return compra


def _base(id_sesion_demo: str | None) -> Select:
    """Consulta de compras acotada a su particion."""
    return select(Compra).where(
        Compra.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Compra.id_sesion_demo == id_sesion_demo
    )


def obtener(
    db: Session, id_compra: int, id_sesion_demo: str | None = None
) -> Compra:
    """Una compra de la particion, o error si no esta."""
    compra = db.scalars(
        _base(id_sesion_demo).where(Compra.id == id_compra)
    ).first()
    if compra is None:
        raise NoEncontrado("No existe la compra.", "no_encontrado")
    return compra


def listar(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    id_proveedor: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    desplazamiento: int = 0,
    limite: int = 25,
) -> tuple[list[Compra], int]:
    """Historial de compras (RF-G04)."""
    consulta = _base(id_sesion_demo)

    if id_proveedor is not None:
        consulta = consulta.where(Compra.id_proveedor == id_proveedor)
    if desde is not None:
        consulta = consulta.where(Compra.fecha >= desde)
    if hasta is not None:
        consulta = consulta.where(Compra.fecha <= hasta)

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = db.scalars(
        consulta.order_by(Compra.fecha.desc(), Compra.id.desc())
        .offset(desplazamiento)
        .limit(limite)
    ).all()
    return list(pagina), total or 0


def resumen_por_proveedor(
    db: Session, id_proveedor: int, id_sesion_demo: str | None = None
) -> dict:
    """Cuanto y cuando se le compro a un proveedor (RF-G04)."""
    servicio_proveedores.obtener(db, id_proveedor, id_sesion_demo)

    cantidad, total, ultima = db.execute(
        select(
            func.count(Compra.id),
            func.coalesce(func.sum(Compra.total), 0),
            func.max(Compra.fecha),
        ).where(
            Compra.id_proveedor == id_proveedor,
            Compra.estado == EstadoCompra.REGISTRADA,
        )
    ).one()

    return {
        "cantidad_compras": cantidad or 0,
        "total_comprado": Decimal(str(total or 0)).quantize(CENTAVO),
        "ultima_compra": ultima,
    }


def anular(
    db: Session,
    id_compra: int,
    usuario: Usuario,
    motivo: str | None = None,
    id_sesion_demo: str | None = None,
) -> Compra:
    """Anula una compra y descuenta lo que habia entrado.

    Un remito mal cargado infla el stock. Sin esto, la unica correccion
    seria un ajuste manual que no queda ligado a la compra que lo
    origino, y el historial deja de explicar de donde salio el numero.

    Si algo ya se vendio y el stock no alcanza para devolver la entrada,
    la anulacion se rechaza entera: descontar de menos dejaria el
    inventario mintiendo.
    """
    compra = obtener(db, id_compra, id_sesion_demo)

    if compra.estado is EstadoCompra.ANULADA:
        raise ErrorDeCompra("La compra ya estaba anulada.", "ya_anulada")

    ids = [item.id_producto for item in compra.items]
    filas = db.scalars(
        select(Producto)
        .where(
            Producto.id.in_(ids),
            Producto.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Producto.id_sesion_demo == id_sesion_demo,
        )
        # Sin esto, la categoria y el proveedor entran con un LEFT JOIN
        # y PostgreSQL rechaza el FOR UPDATE sobre el lado nulable.
        .options(lazyload("*"))
        .order_by(Producto.id)
        .with_for_update()
    ).all()
    productos = {p.id: p for p in filas}

    faltantes = [
        {
            "id_producto": item.id_producto,
            "nombre": item.nombre_producto,
            "a_descontar": item.cantidad,
            "disponible": (
                productos[item.id_producto].stock_actual or 0
                if item.id_producto in productos
                else 0
            ),
        }
        for item in compra.items
        if item.id_producto not in productos
        or (productos[item.id_producto].stock_actual or 0) < item.cantidad
    ]
    if faltantes:
        detalle = "; ".join(
            f"{f['nombre']}: hay {f['disponible']}, "
            f"habria que descontar {f['a_descontar']}"
            for f in faltantes
        )
        raise ErrorDeCompra(
            "No se puede anular: parte de la mercaderia ya no esta en "
            f"stock. {detalle}.",
            "stock_ya_consumido",
        )

    from app.services import stock as servicio_stock

    for item in compra.items:
        servicio_stock.registrar_movimiento(
            db,
            id_producto=item.id_producto,
            tipo=TipoMovimiento.SALIDA,
            cantidad=item.cantidad,
            usuario=usuario,
            nota=f"Anulacion de la compra #{compra.id}",
            id_compra=compra.id,
            id_sesion_demo=id_sesion_demo,
        )

    compra.estado = EstadoCompra.ANULADA
    compra.anulada_en = _ahora()
    compra.id_usuario_anulacion = usuario.id
    compra.motivo_anulacion = (motivo or "").strip() or None
    db.flush()
    return compra
