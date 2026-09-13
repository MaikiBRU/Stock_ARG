"""Reglas de clientes (modulo F).

En la version de escritorio los clientes existian pero ninguna venta los
referenciaba: un ABM sin uso. Aca se vinculan al ticket, y la ficha
muestra que compro cada uno.
"""

from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Cliente, EstadoVenta, Venta
from app.services.productos import ErrorDeProducto, NoEncontrado

CAMPOS = (
    "nombre",
    "apellido",
    "documento",
    "cuit",
    "telefono",
    "email",
    "direccion",
    "localidad",
    "notas",
)


def _limpiar(valor: str | None) -> str | None:
    """Normaliza un texto opcional."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


def _base(id_sesion_demo: str | None) -> Select:
    """Consulta acotada a su particion de datos."""
    return select(Cliente).where(
        Cliente.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Cliente.id_sesion_demo == id_sesion_demo
    )


def obtener(
    db: Session, id_cliente: int, id_sesion_demo: str | None = None
) -> Cliente:
    """Un cliente de la particion, o error si no esta."""
    cliente = db.scalars(
        _base(id_sesion_demo).where(Cliente.id == id_cliente)
    ).first()
    if cliente is None:
        raise NoEncontrado("No existe el cliente.", "no_encontrado")
    return cliente


def listar(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    busqueda: str | None = None,
    incluir_inactivos: bool = False,
    desplazamiento: int = 0,
    limite: int = 25,
) -> tuple[list[Cliente], int]:
    """Listado con busqueda y paginado (RF-F04)."""
    consulta = _base(id_sesion_demo)

    if not incluir_inactivos:
        consulta = consulta.where(Cliente.activo.is_(True))

    if busqueda:
        patron = f"%{busqueda.strip().lower()}%"
        consulta = consulta.where(
            or_(
                func.lower(Cliente.nombre).like(patron),
                func.lower(Cliente.apellido).like(patron),
                func.lower(Cliente.documento).like(patron),
                func.lower(Cliente.email).like(patron),
            )
        )

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = db.scalars(
        consulta.order_by(Cliente.apellido, Cliente.nombre, Cliente.id)
        .offset(desplazamiento)
        .limit(limite)
    ).all()
    return list(pagina), total or 0


def _documento_libre(
    db: Session,
    documento: str | None,
    id_sesion_demo: str | None,
    excluir: int | None = None,
) -> None:
    """Comprueba que el documento no este tomado (RF-F02).

    La base ya lo impide con un indice parcial. Esto existe para nombrar
    al cliente que lo esta usando en lugar de devolver un error de
    integridad sin contexto.
    """
    if not documento:
        return
    consulta = _base(id_sesion_demo).where(Cliente.documento == documento)
    if excluir is not None:
        consulta = consulta.where(Cliente.id != excluir)
    otro = db.scalars(consulta).first()
    if otro is not None:
        raise ErrorDeProducto(
            f"El documento {documento} ya lo tiene {otro.nombre_completo}.",
            "documento_en_uso",
        )


def crear(
    db: Session, datos: dict, id_sesion_demo: str | None = None
) -> Cliente:
    """Alta de cliente (RF-F01)."""
    documento = _limpiar(datos.get("documento"))
    _documento_libre(db, documento, id_sesion_demo)

    cliente = Cliente(
        nombre=datos["nombre"],
        **{
            campo: _limpiar(datos.get(campo))
            for campo in CAMPOS
            if campo != "nombre"
        },
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(cliente)
    db.flush()
    return cliente


def actualizar(
    db: Session,
    id_cliente: int,
    datos: dict,
    id_sesion_demo: str | None = None,
) -> Cliente:
    """Edicion de cliente (RF-F01)."""
    cliente = obtener(db, id_cliente, id_sesion_demo)
    documento = _limpiar(datos.get("documento"))
    _documento_libre(db, documento, id_sesion_demo, excluir=id_cliente)

    cliente.nombre = datos["nombre"]
    for campo in CAMPOS:
        if campo != "nombre":
            setattr(cliente, campo, _limpiar(datos.get(campo)))
    db.flush()
    return cliente


def tiene_compras(db: Session, id_cliente: int) -> bool:
    """True si el cliente aparece en alguna venta."""
    return (
        db.scalars(
            select(Venta.id).where(Venta.id_cliente == id_cliente).limit(1)
        ).first()
        is not None
    )


def eliminar(
    db: Session, id_cliente: int, id_sesion_demo: str | None = None
) -> tuple[Cliente, bool]:
    """Da de baja un cliente.

    Con compras registradas se desactiva: borrarlo dejaria las ventas
    apuntando a un cliente que ya no existe, o forzaria a borrarlas.
    Devuelve el cliente y si se borro de verdad.
    """
    cliente = obtener(db, id_cliente, id_sesion_demo)

    if tiene_compras(db, id_cliente):
        cliente.activo = False
        db.flush()
        return cliente, False

    db.delete(cliente)
    db.flush()
    return cliente, True


def resumen_de_compras(
    db: Session, id_cliente: int, id_sesion_demo: str | None = None
) -> dict:
    """Cuanto y cuando compro un cliente (RF-F03).

    Las ventas anuladas quedan afuera del total: si contaran, el
    acumulado diria que compro algo que despues se dio marcha atras.
    """
    obtener(db, id_cliente, id_sesion_demo)

    fila = db.execute(
        select(
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
            func.max(Venta.fecha_hora),
        ).where(
            Venta.id_cliente == id_cliente,
            Venta.estado == EstadoVenta.REGISTRADA,
        )
    ).one()

    cantidad, total, ultima = fila
    return {
        "cantidad_compras": cantidad or 0,
        "total_comprado": Decimal(str(total or 0)).quantize(Decimal("0.01")),
        "ultima_compra": ultima,
    }
