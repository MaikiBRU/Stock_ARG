"""Movimientos de inventario y bajas (modulo D)."""

from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core import tiempo
from app.models import (
    BajaProducto,
    MotivoBaja,
    MovimientoStock,
    Producto,
    TipoMovimiento,
    Usuario,
)
from app.services.productos import ErrorDeProducto, NoEncontrado

# Como afecta cada tipo al stock. El ajuste no suma ni resta: fija el
# valor, que es lo que se hace despues de contar la mercaderia.
SUMAN = {TipoMovimiento.ENTRADA, TipoMovimiento.DEVOLUCION}
RESTAN = {
    TipoMovimiento.SALIDA,
    TipoMovimiento.VENTA,
    TipoMovimiento.BAJA,
}


class StockInsuficiente(ErrorDeProducto):
    """La operacion dejaria el stock por debajo de cero."""


def _producto_bloqueado(
    db: Session, id_producto: int, id_sesion_demo: str | None
) -> Producto:
    """Trae el producto tomando el bloqueo de su fila.

    with_for_update es lo que evita que dos operaciones simultaneas lean
    el mismo stock y lo descuenten dos veces. En SQLite no hace nada,
    porque escribe de a una operacion por vez; en PostgreSQL, que es
    donde corre en produccion, es la garantia real.
    """
    consulta = (
        select(Producto)
        .where(
            Producto.id == id_producto,
            Producto.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Producto.id_sesion_demo == id_sesion_demo,
        )
        .with_for_update()
    )
    producto = db.scalars(consulta).first()
    if producto is None:
        raise NoEncontrado("No existe el producto.", "no_encontrado")
    return producto


def _calcular_stock(
    producto: Producto, tipo: TipoMovimiento, cantidad: int
) -> int:
    """Stock resultante de aplicar un movimiento."""
    actual = producto.stock_actual or 0

    if tipo in SUMAN:
        return actual + cantidad
    if tipo in RESTAN:
        if actual < cantidad:
            raise StockInsuficiente(
                f'Stock insuficiente de "{producto.nombre}". '
                f"Disponible: {actual}, solicitado: {cantidad}.",
                "stock_insuficiente",
            )
        return actual - cantidad
    # Ajuste: la cantidad es el valor contado, no una diferencia.
    return cantidad


def registrar_movimiento(
    db: Session,
    *,
    id_producto: int,
    tipo: TipoMovimiento,
    cantidad: int,
    usuario: Usuario,
    nota: str | None = None,
    id_venta: int | None = None,
    id_compra: int | None = None,
    id_sesion_demo: str | None = None,
) -> MovimientoStock:
    """Aplica un movimiento y lo deja registrado (RF-D03 a RF-D08).

    El movimiento y el cambio de stock van en la misma transaccion: no
    puede quedar un stock modificado sin la linea que lo explique, ni al
    reves.
    """
    if cantidad <= 0:
        raise ErrorDeProducto(
            "La cantidad debe ser mayor a cero.", "cantidad_invalida"
        )

    producto = _producto_bloqueado(db, id_producto, id_sesion_demo)
    resultante = _calcular_stock(producto, tipo, cantidad)

    producto.stock_actual = resultante
    movimiento = MovimientoStock(
        id_producto=producto.id,
        tipo=tipo,
        cantidad=cantidad,
        stock_resultante=resultante,
        nota=(nota or "").strip() or None,
        id_venta=id_venta,
        id_compra=id_compra,
        id_usuario=usuario.id,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(movimiento)
    db.flush()
    return movimiento


def registrar_baja(
    db: Session,
    *,
    id_producto: int,
    cantidad: int,
    motivo: MotivoBaja,
    usuario: Usuario,
    detalle: str | None = None,
    id_sesion_demo: str | None = None,
) -> tuple[BajaProducto, MovimientoStock]:
    """Descarta mercaderia y descuenta del inventario (RF-D06)."""
    movimiento = registrar_movimiento(
        db,
        id_producto=id_producto,
        tipo=TipoMovimiento.BAJA,
        cantidad=cantidad,
        usuario=usuario,
        nota=f"Baja por {motivo.value}" + (f": {detalle}" if detalle else ""),
        id_sesion_demo=id_sesion_demo,
    )

    baja = BajaProducto(
        id_producto=id_producto,
        cantidad=cantidad,
        motivo=motivo,
        detalle=(detalle or "").strip() or None,
        id_usuario=usuario.id,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(baja)
    db.flush()
    return baja, movimiento


def _base_movimientos(id_sesion_demo: str | None) -> Select:
    """Consulta de movimientos acotada a su particion."""
    return select(MovimientoStock).where(
        MovimientoStock.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else MovimientoStock.id_sesion_demo == id_sesion_demo
    )


def listar_movimientos(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    id_producto: int | None = None,
    tipo: TipoMovimiento | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    desplazamiento: int = 0,
    limite: int = 25,
) -> tuple[list[MovimientoStock], int]:
    """Historial filtrable de movimientos (RF-D04)."""
    consulta = _base_movimientos(id_sesion_demo)

    if id_producto is not None:
        consulta = consulta.where(MovimientoStock.id_producto == id_producto)
    if tipo is not None:
        consulta = consulta.where(MovimientoStock.tipo == tipo)
    if desde is not None:
        consulta = consulta.where(
            MovimientoStock.fecha_hora >= tiempo.inicio_del_dia(desde)
        )
    if hasta is not None:
        consulta = consulta.where(
            MovimientoStock.fecha_hora <= tiempo.fin_del_dia(hasta)
        )

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))

    pagina = db.scalars(
        consulta.order_by(
            MovimientoStock.fecha_hora.desc(), MovimientoStock.id.desc()
        )
        .offset(desplazamiento)
        .limit(limite)
    ).all()

    return list(pagina), total or 0


def resumen_de_stock(
    db: Session, id_sesion_demo: str | None = None
) -> dict[str, int]:
    """Cuantos productos hay en cada estado (RF-D02)."""
    productos = db.scalars(
        select(Producto).where(
            Producto.activo.is_(True),
            Producto.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Producto.id_sesion_demo == id_sesion_demo,
        )
    ).all()

    resumen = {"total": 0, "bajo": 0, "medio": 0, "ok": 0, "sin_stock": 0}
    for producto in productos:
        resumen["total"] += 1
        resumen[producto.estado_stock] += 1
        if (producto.stock_actual or 0) == 0:
            resumen["sin_stock"] += 1
    return resumen
