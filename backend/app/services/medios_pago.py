"""Medios de cobro habilitados (RF-E06)."""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import MedioPago, Venta
from app.services.productos import ErrorDeProducto, NoEncontrado

# Los que trae un comercio recien instalado. El efectivo va marcado
# porque es el unico que pide importe recibido y calcula vuelto.
INICIALES = (
    ("Efectivo", True),
    ("Débito", False),
    ("Crédito", False),
    ("Transferencia", False),
    ("QR", False),
)


def _base(id_sesion_demo: str | None) -> Select:
    """Consulta acotada a su particion de datos."""
    return select(MedioPago).where(
        MedioPago.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else MedioPago.id_sesion_demo == id_sesion_demo
    )


def listar(
    db: Session,
    id_sesion_demo: str | None = None,
    solo_activos: bool = True,
) -> list[MedioPago]:
    """Medios de pago de la particion."""
    consulta = _base(id_sesion_demo)
    if solo_activos:
        consulta = consulta.where(MedioPago.activo.is_(True))
    return list(db.scalars(consulta.order_by(MedioPago.id)))


def obtener(
    db: Session, id_medio: int, id_sesion_demo: str | None = None
) -> MedioPago:
    """Un medio de pago de la particion, o error si no esta."""
    medio = db.scalars(
        _base(id_sesion_demo).where(MedioPago.id == id_medio)
    ).first()
    if medio is None:
        raise NoEncontrado("No existe el medio de pago.", "no_encontrado")
    return medio


def crear(
    db: Session,
    nombre: str,
    es_efectivo: bool = False,
    id_sesion_demo: str | None = None,
) -> MedioPago:
    """Alta de medio de pago."""
    nombre = nombre.strip()
    existente = db.scalars(
        _base(id_sesion_demo).where(
            func.lower(MedioPago.nombre) == nombre.lower()
        )
    ).first()
    if existente is not None:
        raise ErrorDeProducto(
            f'Ya existe un medio de pago llamado "{nombre}".',
            "nombre_en_uso",
        )

    medio = MedioPago(
        nombre=nombre,
        es_efectivo=es_efectivo,
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(medio)
    db.flush()
    return medio


def cambiar_estado(
    db: Session,
    id_medio: int,
    activo: bool,
    id_sesion_demo: str | None = None,
) -> MedioPago:
    """Habilita o deshabilita un medio de pago.

    Nunca se borra: las ventas viejas lo referencian y el historial tiene
    que seguir diciendo como se cobro.
    """
    medio = obtener(db, id_medio, id_sesion_demo)

    if not activo:
        quedan = db.scalar(
            select(func.count(MedioPago.id)).where(
                MedioPago.activo.is_(True),
                MedioPago.id != id_medio,
                MedioPago.id_sesion_demo.is_(None)
                if id_sesion_demo is None
                else MedioPago.id_sesion_demo == id_sesion_demo,
            )
        )
        if not quedan:
            # Sin ningun medio habilitado no se puede cobrar nada, y la
            # pantalla de venta queda inutilizable sin explicacion.
            raise ErrorDeProducto(
                "Es el unico medio de pago habilitado. "
                "Habilite otro antes de deshabilitar este.",
                "ultimo_medio",
            )

    medio.activo = activo
    db.flush()
    return medio


def sembrar_iniciales(
    db: Session, id_sesion_demo: str | None = None
) -> list[MedioPago]:
    """Crea los medios de pago habituales si no hay ninguno."""
    if listar(db, id_sesion_demo, solo_activos=False):
        return []

    creados = [
        crear(db, nombre, es_efectivo, id_sesion_demo)
        for nombre, es_efectivo in INICIALES
    ]
    db.flush()
    return creados


def tiene_ventas(db: Session, id_medio: int) -> bool:
    """True si algun ticket se cobro con ese medio."""
    return (
        db.scalars(
            select(Venta.id).where(Venta.id_medio_pago == id_medio).limit(1)
        ).first()
        is not None
    )
