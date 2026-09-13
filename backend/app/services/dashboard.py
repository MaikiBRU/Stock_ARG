"""Panel principal (modulo B).

No calcula nada por su cuenta: compone lo que ya resuelven los servicios
de reportes, stock y productos. Si el dashboard tuviera su propia suma
de ventas, tarde o temprano diria un numero distinto al del reporte y
nadie sabria cual de los dos creer.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core import ajustes_vivos
from app.models import Producto
from app.services import reportes
from app.services import stock as servicio_stock


def _productos(id_sesion_demo: str | None) -> Select:
    """Productos activos de la particion."""
    return select(Producto).where(
        Producto.activo.is_(True),
        Producto.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Producto.id_sesion_demo == id_sesion_demo,
    )


def bajo_minimo(
    db: Session, id_sesion_demo: str | None = None, limite: int = 20
) -> list[Producto]:
    """Productos que conviene reponer (RF-B03)."""
    return list(
        db.scalars(
            _productos(id_sesion_demo)
            .where(Producto.stock_actual <= Producto.stock_minimo)
            .order_by(Producto.stock_actual)
            .limit(limite)
        )
    )


def proximos_a_vencer(
    db: Session,
    id_sesion_demo: str | None = None,
    dias: int | None = None,
    limite: int = 20,
) -> list[Producto]:
    """Productos que vencen dentro de la ventana de aviso (RF-B04).

    Los que ya vencieron quedan afuera: tienen su propia lista, y
    mezclarlos haria que la de aviso no sirva para prevenir nada.
    """
    ventana = (
        dias
        if dias is not None
        else ajustes_vivos.entero("dias_aviso_vencimiento", db)
    )
    hoy = datetime.now(UTC).date()

    return list(
        db.scalars(
            _productos(id_sesion_demo)
            .where(
                Producto.fecha_vencimiento.is_not(None),
                Producto.fecha_vencimiento >= hoy,
                Producto.fecha_vencimiento <= hoy + timedelta(days=ventana),
            )
            .order_by(Producto.fecha_vencimiento)
            .limit(limite)
        )
    )


def vencidos(
    db: Session, id_sesion_demo: str | None = None, limite: int = 20
) -> list[Producto]:
    """Productos vencidos que todavia tienen stock (RF-B05).

    Sin stock no hay nada que dar de baja, asi que no tiene sentido
    pedirle una accion a alguien que no puede hacer nada.
    """
    hoy: date = datetime.now(UTC).date()
    return list(
        db.scalars(
            _productos(id_sesion_demo)
            .where(
                Producto.fecha_vencimiento.is_not(None),
                Producto.fecha_vencimiento < hoy,
                Producto.stock_actual > 0,
            )
            .order_by(Producto.fecha_vencimiento)
            .limit(limite)
        )
    )


def armar(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    ver_costo: bool = False,
) -> dict:
    """Todo lo que muestra el panel principal (RF-B01 a RF-B08)."""
    del_dia = reportes.ventas_por_periodo(
        db, periodo="hoy", id_sesion_demo=id_sesion_demo
    )
    medios = reportes.por_medio_de_pago(
        db, periodo="hoy", id_sesion_demo=id_sesion_demo
    )
    top = reportes.mas_vendidos(
        db, periodo="mes", limite=5, id_sesion_demo=id_sesion_demo
    )
    serie = reportes.serie_diaria(
        db, periodo="mes", id_sesion_demo=id_sesion_demo
    )
    resumen = servicio_stock.resumen_de_stock(db, id_sesion_demo)

    panel = {
        "fecha": datetime.now(UTC).date(),
        "ventas_del_dia": del_dia,
        "medios_de_pago": medios["detalle"],
        "resumen_stock": resumen,
        "bajo_minimo": bajo_minimo(db, id_sesion_demo),
        "proximos_a_vencer": proximos_a_vencer(db, id_sesion_demo),
        "vencidos": vencidos(db, id_sesion_demo),
        "mas_vendidos_del_mes": top["ranking"],
        "serie_ventas": serie,
        "dias_aviso_vencimiento": ajustes_vivos.entero(
            "dias_aviso_vencimiento", db
        ),
    }

    if ver_costo:
        # La ganancia del mes solo la ve quien puede ver los costos.
        panel["rentabilidad_del_mes"] = reportes.rentabilidad(
            db, periodo="mes", limite=1, id_sesion_demo=id_sesion_demo
        )["ganancia"]

    return panel
