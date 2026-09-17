"""Reportes de ventas, rentabilidad y compras (modulo H).

Una regla atraviesa todo el archivo: **las ventas anuladas no cuentan**.
Si contaran, el reporte diria que se vendio algo que despues se dio
marcha atras, y el numero no cerraria contra la caja.

Los periodos son ventanas moviles terminadas hoy, no meses de
calendario: asi el reporte de los ultimos 30 dias dice lo mismo sin
importar el dia en que se lo pida.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from app.core import tiempo
from app.models import (
    Categoria,
    Compra,
    EstadoCompra,
    EstadoVenta,
    MedioPago,
    Producto,
    Venta,
    VentaItem,
)
from app.services.productos import ErrorDeProducto

CENTAVO = Decimal("0.01")

PERIODOS = {"hoy": 0, "semana": 6, "mes": 29}


class PeriodoInvalido(ErrorDeProducto):
    """El rango de fechas pedido no tiene sentido."""


def resolver_rango(
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> tuple[date, date]:
    """Traduce un periodo o un rango explicito a dos fechas.

    Un rango explicito gana sobre el periodo: si alguien manda las dos
    cosas, lo que quiso decir son las fechas que escribio.
    """
    hoy = tiempo.hoy()

    if desde is not None or hasta is not None:
        inicio = desde or hoy
        fin = hasta or hoy
        if inicio > fin:
            raise PeriodoInvalido(
                'La fecha "desde" no puede ser posterior a "hasta".',
                "rango_invalido",
            )
        return inicio, fin

    dias = PERIODOS.get(periodo or "hoy")
    if dias is None:
        admitidos = ", ".join(sorted(PERIODOS))
        raise PeriodoInvalido(
            f"Periodo invalido. Admitidos: {admitidos}.", "periodo_invalido"
        )
    return hoy - timedelta(days=dias), hoy


def _ventas_del_rango(
    inicio: date, fin: date, id_sesion_demo: str | None
) -> Select:
    """Ventas registradas dentro del rango, sin las anuladas."""
    return select(Venta).where(
        Venta.estado == EstadoVenta.REGISTRADA,
        Venta.fecha_hora >= tiempo.inicio_del_dia(inicio),
        Venta.fecha_hora <= tiempo.fin_del_dia(fin),
        Venta.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Venta.id_sesion_demo == id_sesion_demo,
    )


def _decimal(valor) -> Decimal:
    """Pasa a Decimal un agregado que puede venir nulo o flotante."""
    return Decimal(str(valor or 0)).quantize(CENTAVO)


# --- ventas por periodo (RF-H01) -----------------------------------------


def ventas_por_periodo(
    db: Session,
    *,
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    id_sesion_demo: str | None = None,
) -> dict:
    """Total facturado, tickets y ticket promedio del periodo."""
    inicio, fin = resolver_rango(periodo, desde, hasta)
    base = _ventas_del_rango(inicio, fin, id_sesion_demo).subquery()

    cantidad, total = db.execute(
        select(func.count(base.c.id), func.coalesce(func.sum(base.c.total), 0))
    ).one()

    cantidad = cantidad or 0
    facturado = _decimal(total)
    promedio = (
        (facturado / cantidad).quantize(CENTAVO)
        if cantidad
        else Decimal("0.00")
    )

    return {
        "desde": inicio,
        "hasta": fin,
        "cantidad_ventas": cantidad,
        "total_facturado": facturado,
        "ticket_promedio": promedio,
        # RF-H07: sin operaciones se dice explicitamente, en lugar de
        # mostrar ceros que parecen un dia de ventas nulas.
        "sin_datos": cantidad == 0,
    }


def serie_diaria(
    db: Session,
    *,
    periodo: str | None = "mes",
    desde: date | None = None,
    hasta: date | None = None,
    id_sesion_demo: str | None = None,
) -> list[dict]:
    """Facturado por dia, con los dias sin ventas en cero.

    Completar los huecos es lo que hace que un grafico de linea no
    invente una pendiente entre dos dias lejanos.
    """
    inicio, fin = resolver_rango(periodo, desde, hasta)
    base = _ventas_del_rango(inicio, fin, id_sesion_demo).subquery()

    # El dia se arma en la zona del comercio y no con func.date, que
    # agruparia por el dia UTC y partiria en dos la venta de la noche.
    filas = db.execute(select(base.c.fecha_hora, base.c.total)).all()

    por_dia: dict[date, tuple[int, Decimal]] = {}
    for fecha_hora, importe in filas:
        dia = tiempo.en_zona(fecha_hora).date()
        cantidad, acumulado = por_dia.get(dia, (0, Decimal("0.00")))
        por_dia[dia] = (cantidad + 1, acumulado + _decimal(importe))

    serie: list[dict] = []
    actual = inicio
    while actual <= fin:
        cantidad, total = por_dia.get(actual, (0, Decimal("0.00")))
        serie.append(
            {"fecha": actual, "cantidad_ventas": cantidad, "total": total}
        )
        actual += timedelta(days=1)
    return serie


# --- mas vendidos (RF-H02) -----------------------------------------------


def mas_vendidos(
    db: Session,
    *,
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    ordenar_por: str = "unidades",
    limite: int = 10,
    id_sesion_demo: str | None = None,
) -> dict:
    """Ranking de productos, por unidades o por facturacion."""
    if ordenar_por not in ("unidades", "facturacion"):
        raise PeriodoInvalido(
            'Se puede ordenar por "unidades" o por "facturacion".',
            "orden_invalido",
        )

    inicio, fin = resolver_rango(periodo, desde, hasta)
    ventas = _ventas_del_rango(inicio, fin, id_sesion_demo).subquery()

    unidades = func.sum(VentaItem.cantidad).label("unidades")
    facturado = func.sum(VentaItem.subtotal).label("facturado")
    criterio = unidades if ordenar_por == "unidades" else facturado

    filas = db.execute(
        select(
            VentaItem.id_producto,
            func.min(VentaItem.nombre_producto).label("nombre"),
            unidades,
            facturado,
        )
        .join(ventas, ventas.c.id == VentaItem.id_venta)
        .group_by(VentaItem.id_producto)
        .order_by(desc(criterio))
        .limit(limite)
    ).all()

    ranking = [
        {
            "id_producto": id_producto,
            "nombre": nombre,
            "unidades": int(cantidad or 0),
            "facturado": _decimal(importe),
        }
        for id_producto, nombre, cantidad, importe in filas
    ]

    return {
        "desde": inicio,
        "hasta": fin,
        "ordenado_por": ordenar_por,
        "ranking": ranking,
        "sin_datos": not ranking,
    }


# --- cortes por medio de pago y categoria (RF-H03) -----------------------


def por_medio_de_pago(
    db: Session,
    *,
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    id_sesion_demo: str | None = None,
) -> dict:
    """Cuanto entro por cada forma de cobro."""
    inicio, fin = resolver_rango(periodo, desde, hasta)
    ventas = _ventas_del_rango(inicio, fin, id_sesion_demo).subquery()

    filas = db.execute(
        select(
            MedioPago.id,
            MedioPago.nombre,
            func.count(ventas.c.id),
            func.coalesce(func.sum(ventas.c.total), 0),
        )
        .join(ventas, ventas.c.id_medio_pago == MedioPago.id)
        .group_by(MedioPago.id, MedioPago.nombre)
        .order_by(desc(func.coalesce(func.sum(ventas.c.total), 0)))
    ).all()

    detalle = [
        {
            "id_medio_pago": id_medio,
            "nombre": nombre,
            "cantidad_ventas": cantidad or 0,
            "total": _decimal(total),
        }
        for id_medio, nombre, cantidad, total in filas
    ]

    return {
        "desde": inicio,
        "hasta": fin,
        "detalle": detalle,
        "sin_datos": not detalle,
    }


def por_categoria(
    db: Session,
    *,
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    id_sesion_demo: str | None = None,
) -> dict:
    """Cuanto se vendio de cada rubro.

    Los productos sin categoria se agrupan bajo un rotulo propio en
    lugar de quedar fuera del reporte, que daria un total menor al real.
    """
    inicio, fin = resolver_rango(periodo, desde, hasta)
    ventas = _ventas_del_rango(inicio, fin, id_sesion_demo).subquery()

    filas = db.execute(
        select(
            Categoria.id,
            Categoria.nombre,
            func.sum(VentaItem.cantidad),
            func.coalesce(func.sum(VentaItem.subtotal), 0),
        )
        .select_from(VentaItem)
        .join(ventas, ventas.c.id == VentaItem.id_venta)
        .join(Producto, Producto.id == VentaItem.id_producto)
        .outerjoin(Categoria, Categoria.id == Producto.id_categoria)
        .group_by(Categoria.id, Categoria.nombre)
        .order_by(desc(func.coalesce(func.sum(VentaItem.subtotal), 0)))
    ).all()

    detalle = [
        {
            "id_categoria": id_categoria,
            "nombre": nombre or "Sin categoria",
            "unidades": int(unidades or 0),
            "total": _decimal(total),
        }
        for id_categoria, nombre, unidades, total in filas
    ]

    return {
        "desde": inicio,
        "hasta": fin,
        "detalle": detalle,
        "sin_datos": not detalle,
    }


# --- rentabilidad (RF-H06) -----------------------------------------------


def rentabilidad(
    db: Session,
    *,
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = 50,
    id_sesion_demo: str | None = None,
) -> dict:
    """Ganancia por producto en el periodo.

    El costo que se usa es el que el producto tiene hoy, no el que tenia
    el dia de la venta: el sistema guarda un unico costo por articulo.
    La cifra sirve para comparar productos entre si, no para cerrar un
    balance, y el reporte lo dice en su advertencia.
    """
    inicio, fin = resolver_rango(periodo, desde, hasta)
    ventas = _ventas_del_rango(inicio, fin, id_sesion_demo).subquery()

    unidades = func.sum(VentaItem.cantidad)
    ingreso = func.coalesce(func.sum(VentaItem.subtotal), 0)
    costo = func.coalesce(
        func.sum(VentaItem.cantidad * Producto.precio_costo), 0
    )

    filas = db.execute(
        select(
            VentaItem.id_producto,
            func.min(VentaItem.nombre_producto),
            unidades,
            ingreso,
            costo,
        )
        .select_from(VentaItem)
        .join(ventas, ventas.c.id == VentaItem.id_venta)
        .join(Producto, Producto.id == VentaItem.id_producto)
        .group_by(VentaItem.id_producto)
        .order_by(desc(ingreso - costo))
        .limit(limite)
    ).all()

    detalle = []
    total_ingreso = Decimal("0.00")
    total_costo = Decimal("0.00")
    for id_producto, nombre, cantidad, importe, gasto in filas:
        vendido = _decimal(importe)
        invertido = _decimal(gasto)
        ganancia = (vendido - invertido).quantize(CENTAVO)
        margen = (
            (ganancia / vendido * 100).quantize(CENTAVO)
            if vendido > 0
            else None
        )
        detalle.append(
            {
                "id_producto": id_producto,
                "nombre": nombre,
                "unidades": int(cantidad or 0),
                "ingreso": vendido,
                "costo": invertido,
                "ganancia": ganancia,
                "margen_porcentaje": margen,
            }
        )
        total_ingreso += vendido
        total_costo += invertido

    return {
        "desde": inicio,
        "hasta": fin,
        "detalle": detalle,
        "total_ingreso": total_ingreso.quantize(CENTAVO),
        "total_costo": total_costo.quantize(CENTAVO),
        "ganancia": (total_ingreso - total_costo).quantize(CENTAVO),
        "sin_datos": not detalle,
        "advertencia": (
            "El costo es el vigente hoy para cada producto, no el del dia "
            "de la venta."
        ),
    }


# --- compras del periodo -------------------------------------------------


def compras_por_periodo(
    db: Session,
    *,
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    id_sesion_demo: str | None = None,
) -> dict:
    """Cuanto se gasto en mercaderia en el periodo."""
    inicio, fin = resolver_rango(periodo, desde, hasta)

    cantidad, total = db.execute(
        select(
            func.count(Compra.id), func.coalesce(func.sum(Compra.total), 0)
        ).where(
            Compra.estado == EstadoCompra.REGISTRADA,
            Compra.fecha >= inicio,
            Compra.fecha <= fin,
            Compra.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Compra.id_sesion_demo == id_sesion_demo,
        )
    ).one()

    return {
        "desde": inicio,
        "hasta": fin,
        "cantidad_compras": cantidad or 0,
        "total_gastado": _decimal(total),
        "sin_datos": not cantidad,
    }
