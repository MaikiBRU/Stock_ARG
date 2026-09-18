"""Punto de venta (modulo E).

Aca esta la operacion mas delicada del sistema: cobrar y descontar stock
tienen que pasar juntos o no pasar. Dos reglas gobiernan el archivo:

1. Los importes los calcula el servidor. Lo que manda el cliente son
   productos, cantidades y, si corresponde, precios pactados y
   descuentos; el total se deriva de eso. Aceptar un total enviado
   dejaria cobrar mil pesos una compra de cien mil.
2. El stock se toca con la fila bloqueada y dentro de la misma
   transaccion que escribe la venta.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, lazyload
from sqlalchemy.sql.elements import ColumnElement

from app.core import ajustes_vivos
from app.core.config import get_settings
from app.models import (
    Cliente,
    EstadoVenta,
    Producto,
    TipoMovimiento,
    Usuario,
    Venta,
    VentaItem,
)
from app.services import (
    medios_pago as servicio_medios,
)
from app.services.productos import ErrorDeProducto, NoEncontrado

CENTAVO = Decimal("0.01")
MAX_ITEMS = 200


class ErrorDeVenta(ErrorDeProducto):
    """Falla esperable al registrar o anular una venta."""


class StockInsuficiente(ErrorDeVenta):
    """Falta stock de uno o mas productos del pedido.

    Lleva el detalle de cada faltante para que la pantalla pueda mostrar
    todo lo que hay que corregir de una sola vez, en lugar de que el
    usuario descubra los problemas de a uno.
    """

    def __init__(self, faltantes: list[dict]) -> None:
        """Arma el mensaje a partir de la lista de faltantes."""
        detalle = "; ".join(
            f"{f['nombre']}: pedido {f['solicitado']}, "
            f"disponible {f['disponible']}"
            for f in faltantes
        )
        super().__init__(
            f"No hay stock suficiente. {detalle}.", "stock_insuficiente"
        )
        self.faltantes = faltantes


@dataclass
class LineaPedida:
    """Una linea tal como la pide quien cobra."""

    id_producto: int
    cantidad: int
    precio_unitario: Decimal | None = None
    descuento: Decimal = Decimal("0.00")


def _ahora() -> datetime:
    """Momento actual en UTC."""
    return datetime.now(UTC)


def consolidar(lineas: list[LineaPedida]) -> list[LineaPedida]:
    """Junta en una sola linea el mismo producto repetido (RF-E11).

    Sin esto, dos lineas del mismo producto se validan por separado
    contra el stock y la suma puede superar lo que hay. Se conserva el
    precio de la primera aparicion, que es el que el operador vio.
    """
    juntadas: dict[int, LineaPedida] = {}
    for linea in lineas:
        previa = juntadas.get(linea.id_producto)
        if previa is None:
            juntadas[linea.id_producto] = LineaPedida(
                id_producto=linea.id_producto,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
                descuento=linea.descuento,
            )
        else:
            previa.cantidad += linea.cantidad
            previa.descuento += linea.descuento
    return list(juntadas.values())


def _validar_pedido(lineas: list[LineaPedida]) -> None:
    """Comprueba la forma del pedido antes de tocar la base."""
    if not lineas:
        raise ErrorDeVenta(
            "La venta tiene que incluir al menos un producto.", "sin_items"
        )
    if len(lineas) > MAX_ITEMS:
        raise ErrorDeVenta(
            f"Una venta no puede tener mas de {MAX_ITEMS} lineas.",
            "demasiados_items",
        )
    for linea in lineas:
        if linea.cantidad <= 0:
            raise ErrorDeVenta(
                "La cantidad de cada linea tiene que ser mayor a cero.",
                "cantidad_invalida",
            )
        if linea.precio_unitario is not None and linea.precio_unitario < 0:
            raise ErrorDeVenta(
                "El precio no puede ser negativo.", "precio_invalido"
            )
        if linea.descuento < 0:
            raise ErrorDeVenta(
                "El descuento no puede ser negativo.", "descuento_invalido"
            )


def _productos_bloqueados(
    db: Session, ids: list[int], id_sesion_demo: str | None
) -> dict[int, Producto]:
    """Trae los productos del pedido con sus filas bloqueadas.

    Se ordena por id: dos ventas simultaneas que toquen los mismos
    productos los bloquean en el mismo orden y no se trancan entre si.
    """
    filas = db.scalars(
        select(Producto)
        .where(
            Producto.id.in_(ids),
            Producto.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Producto.id_sesion_demo == id_sesion_demo,
        )
        # Sin esto, la categoria y el proveedor entran con un LEFT JOIN
        # y PostgreSQL rechaza el FOR UPDATE sobre el lado nulable: no
        # se podria registrar ninguna venta.
        .options(lazyload("*"))
        .order_by(Producto.id)
        .with_for_update()
    ).all()
    return {p.id: p for p in filas}


def registrar(
    db: Session,
    *,
    lineas: list[LineaPedida],
    id_medio_pago: int,
    usuario: Usuario,
    id_cliente: int | None = None,
    recibido: Decimal | None = None,
    descuento_general: Decimal = Decimal("0.00"),
    id_sesion_demo: str | None = None,
) -> Venta:
    """Registra una venta completa (RF-E01 a RF-E11)."""
    lineas = consolidar(lineas)
    _validar_pedido(lineas)

    if descuento_general < 0:
        raise ErrorDeVenta(
            "El descuento no puede ser negativo.", "descuento_invalido"
        )

    medio = servicio_medios.obtener(db, id_medio_pago, id_sesion_demo)
    if not medio.activo:
        raise ErrorDeVenta(
            f'El medio de pago "{medio.nombre}" no esta habilitado.',
            "medio_deshabilitado",
        )

    if id_cliente is not None:
        cliente = db.scalars(
            select(Cliente).where(
                Cliente.id == id_cliente,
                Cliente.activo.is_(True),
                Cliente.id_sesion_demo.is_(None)
                if id_sesion_demo is None
                else Cliente.id_sesion_demo == id_sesion_demo,
            )
        ).first()
        if cliente is None:
            raise NoEncontrado("No existe el cliente.", "no_encontrado")

    productos = _productos_bloqueados(
        db, [linea.id_producto for linea in lineas], id_sesion_demo
    )

    # Primero se juntan todos los faltantes y despues se informan, para
    # que quien cobra vea de una vez todo lo que tiene que corregir.
    faltantes: list[dict] = []
    for linea in lineas:
        producto = productos.get(linea.id_producto)
        if producto is None:
            raise NoEncontrado(
                f"No existe el producto con id {linea.id_producto}.",
                "no_encontrado",
            )
        if not producto.activo:
            raise ErrorDeVenta(
                f'"{producto.nombre}" esta dado de baja y no se puede vender.',
                "producto_inactivo",
            )
        disponible = producto.stock_actual or 0
        if disponible < linea.cantidad:
            faltantes.append(
                {
                    "id_producto": producto.id,
                    "nombre": producto.nombre,
                    "solicitado": linea.cantidad,
                    "disponible": disponible,
                }
            )

    if faltantes:
        raise StockInsuficiente(faltantes)

    venta = Venta(
        fecha_hora=_ahora(),
        id_usuario=usuario.id,
        id_medio_pago=medio.id,
        id_cliente=id_cliente,
        estado=EstadoVenta.REGISTRADA,
        total=Decimal("0.00"),
        descuento=descuento_general.quantize(CENTAVO),
        id_sesion_demo=id_sesion_demo,
    )

    ajustes = get_settings()
    puede_pactar = (
        usuario.puede_gestionar or ajustes.vendedor_puede_pactar_precio
    )

    bruto = Decimal("0.00")
    for linea in lineas:
        producto = productos[linea.id_producto]
        # Sin precio pactado se usa el de lista. El total nunca sale de
        # lo que manda el cliente: se recalcula con estos valores.
        de_lista = (producto.precio_venta or Decimal("0.00")).quantize(CENTAVO)
        pactado = (
            linea.precio_unitario.quantize(CENTAVO)
            if linea.precio_unitario is not None
            else None
        )

        # Quien atiende el mostrador vende al precio de lista. Poder
        # escribir otro precio es, en la practica, poder regalar
        # mercaderia: el stock se descuenta igual y el faltante recien
        # aparece en el cierre de caja.
        if pactado is not None and pactado != de_lista and not puede_pactar:
            raise ErrorDeVenta(
                f"No tiene permiso para cambiar el precio de "
                f'"{producto.nombre}".',
                "precio_no_permitido",
            )

        precio = pactado if pactado is not None else de_lista

        subtotal = (precio * linea.cantidad) - linea.descuento
        if subtotal < 0:
            raise ErrorDeVenta(
                f'El descuento de "{producto.nombre}" supera el importe '
                "de la linea.",
                "descuento_excesivo",
            )

        venta.items.append(
            VentaItem(
                id_producto=producto.id,
                nombre_producto=producto.nombre,
                cantidad=linea.cantidad,
                precio_unitario=precio,
                descuento=linea.descuento.quantize(CENTAVO),
                subtotal=subtotal.quantize(CENTAVO),
                id_sesion_demo=id_sesion_demo,
            )
        )
        bruto += subtotal

    total = (bruto - venta.descuento).quantize(CENTAVO)
    if total < 0:
        raise ErrorDeVenta(
            "El descuento supera el total de la venta.",
            "descuento_excesivo",
        )

    if not usuario.puede_gestionar and bruto > 0:
        # El tope mira el descuento total, de linea mas general: repartir
        # el mismo descuento entre varias lineas no debe servir para
        # esquivarlo.
        descontado = (
            sum((item.descuento for item in venta.items), Decimal("0.00"))
            + venta.descuento
        )
        tope = (
            (
                bruto + descontado  # importe antes de descontar
            )
            * Decimal(ajustes_vivos.entero("descuento_max_vendedor", db))
            / 100
        )
        if descontado > tope.quantize(CENTAVO):
            raise ErrorDeVenta(
                "El descuento supera el maximo permitido para su rol "
                f"({ajustes_vivos.entero('descuento_max_vendedor', db)}%). "
                "Pida autorizacion a un encargado.",
                "descuento_no_permitido",
            )

    venta.total = total

    if recibido is not None:
        if not medio.es_efectivo:
            # Guardar un recibido con tarjeta haria aparecer un vuelto
            # que nadie entrego.
            raise ErrorDeVenta(
                "El importe recibido solo corresponde a un pago en efectivo.",
                "recibido_sin_efectivo",
            )
        recibido = recibido.quantize(CENTAVO)
        if recibido < total:
            raise ErrorDeVenta(
                f"El importe recibido ({recibido}) es menor que el total "
                f"({total}).",
                "recibido_insuficiente",
            )
        venta.recibido = recibido

    db.add(venta)
    db.flush()

    # El descuento de stock va en la misma transaccion, con las filas ya
    # bloqueadas mas arriba. El import es local para no crear un ciclo
    # entre los dos servicios.
    from app.services import stock as servicio_stock

    for linea in lineas:
        servicio_stock.registrar_movimiento(
            db,
            id_producto=linea.id_producto,
            tipo=TipoMovimiento.VENTA,
            cantidad=linea.cantidad,
            usuario=usuario,
            nota=f"Venta #{venta.id}",
            id_venta=venta.id,
            id_sesion_demo=id_sesion_demo,
        )

    db.flush()
    return venta


# --- consulta y anulacion ------------------------------------------------


def _base(id_sesion_demo: str | None) -> Select:
    """Consulta de ventas acotada a su particion."""
    return select(Venta).where(
        Venta.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Venta.id_sesion_demo == id_sesion_demo
    )


def obtener(
    db: Session, id_venta: int, id_sesion_demo: str | None = None
) -> Venta:
    """Una venta de la particion, o error si no esta."""
    venta = db.scalars(
        _base(id_sesion_demo).where(Venta.id == id_venta)
    ).first()
    if venta is None:
        raise NoEncontrado("No existe la venta.", "no_encontrado")
    return venta


def listar(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    id_usuario: int | None = None,
    id_cliente: int | None = None,
    id_medio_pago: int | None = None,
    estado: EstadoVenta | None = None,
    busqueda: str | None = None,
    desplazamiento: int = 0,
    limite: int = 25,
) -> tuple[list[Venta], int]:
    """Historial con filtros (RF-E13)."""
    consulta = _base(id_sesion_demo)

    if desde is not None:
        consulta = consulta.where(Venta.fecha_hora >= desde)
    if hasta is not None:
        consulta = consulta.where(Venta.fecha_hora <= hasta)
    if id_usuario is not None:
        consulta = consulta.where(Venta.id_usuario == id_usuario)
    if id_cliente is not None:
        consulta = consulta.where(Venta.id_cliente == id_cliente)
    if id_medio_pago is not None:
        consulta = consulta.where(Venta.id_medio_pago == id_medio_pago)
    if estado is not None:
        consulta = consulta.where(Venta.estado == estado)

    if busqueda:
        # Por numero de ticket o por producto vendido: son las dos formas
        # en que alguien recuerda una venta.
        patron = f"%{busqueda.strip().lower()}%"
        por_producto = select(VentaItem.id_venta).where(
            func.lower(VentaItem.nombre_producto).like(patron)
        )
        condiciones: list[ColumnElement[bool]] = [Venta.id.in_(por_producto)]
        if busqueda.strip().isdigit():
            condiciones.append(Venta.id == int(busqueda.strip()))
        consulta = consulta.where(or_(*condiciones))

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = db.scalars(
        consulta.order_by(Venta.fecha_hora.desc(), Venta.id.desc())
        .offset(desplazamiento)
        .limit(limite)
    ).all()
    return list(pagina), total or 0


def anular(
    db: Session,
    id_venta: int,
    usuario: Usuario,
    motivo: str | None = None,
    id_sesion_demo: str | None = None,
) -> Venta:
    """Anula una venta y repone el stock (RF-E12).

    La venta no se borra: queda marcada como anulada, con quien la anulo
    y cuando. Asi el historial sigue mostrando que la operacion existio y
    que se dio marcha atras, que es lo que un control diario necesita.
    """
    venta = obtener(db, id_venta, id_sesion_demo)

    if venta.estado is EstadoVenta.ANULADA:
        # Sin esta guarda, anular dos veces repone el stock dos veces y
        # el inventario queda inflado.
        raise ErrorDeVenta("La venta ya estaba anulada.", "ya_anulada")

    # Se bloquean las filas antes de devolver las unidades, igual que al
    # vender.
    _productos_bloqueados(
        db, [item.id_producto for item in venta.items], id_sesion_demo
    )

    from app.services import stock as servicio_stock

    for item in venta.items:
        servicio_stock.registrar_movimiento(
            db,
            id_producto=item.id_producto,
            tipo=TipoMovimiento.DEVOLUCION,
            cantidad=item.cantidad,
            usuario=usuario,
            nota=f"Anulacion de la venta #{venta.id}",
            id_venta=venta.id,
            id_sesion_demo=id_sesion_demo,
        )

    venta.estado = EstadoVenta.ANULADA
    venta.anulada_en = _ahora()
    venta.id_usuario_anulacion = usuario.id
    venta.motivo_anulacion = (motivo or "").strip() or None
    db.flush()
    return venta
