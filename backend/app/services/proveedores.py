"""Reglas de proveedores (modulo G)."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Compra, Producto, Proveedor
from app.services.productos import ErrorDeProducto, NoEncontrado

CAMPOS = (
    "razon_social",
    "cuit",
    "contacto",
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
    return select(Proveedor).where(
        Proveedor.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Proveedor.id_sesion_demo == id_sesion_demo
    )


def obtener(
    db: Session, id_proveedor: int, id_sesion_demo: str | None = None
) -> Proveedor:
    """Un proveedor de la particion, o error si no esta."""
    proveedor = db.scalars(
        _base(id_sesion_demo).where(Proveedor.id == id_proveedor)
    ).first()
    if proveedor is None:
        raise NoEncontrado("No existe el proveedor.", "no_encontrado")
    return proveedor


def listar(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    busqueda: str | None = None,
    incluir_inactivos: bool = False,
    desplazamiento: int = 0,
    limite: int = 25,
) -> tuple[list[Proveedor], int]:
    """Listado con busqueda y paginado (RF-G05)."""
    consulta = _base(id_sesion_demo)

    if not incluir_inactivos:
        consulta = consulta.where(Proveedor.activo.is_(True))

    if busqueda:
        patron = f"%{busqueda.strip().lower()}%"
        consulta = consulta.where(
            or_(
                func.lower(Proveedor.razon_social).like(patron),
                func.lower(Proveedor.cuit).like(patron),
                func.lower(Proveedor.contacto).like(patron),
                func.lower(Proveedor.email).like(patron),
            )
        )

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = db.scalars(
        consulta.order_by(Proveedor.razon_social, Proveedor.id)
        .offset(desplazamiento)
        .limit(limite)
    ).all()
    return list(pagina), total or 0


def _cuit_libre(
    db: Session,
    cuit: str | None,
    id_sesion_demo: str | None,
    excluir: int | None = None,
) -> None:
    """Comprueba que el CUIT no este tomado en la particion."""
    if not cuit:
        return
    consulta = _base(id_sesion_demo).where(Proveedor.cuit == cuit)
    if excluir is not None:
        consulta = consulta.where(Proveedor.id != excluir)
    otro = db.scalars(consulta).first()
    if otro is not None:
        raise ErrorDeProducto(
            f"El CUIT {cuit} ya lo tiene {otro.razon_social}.",
            "cuit_en_uso",
        )


def crear(
    db: Session, datos: dict, id_sesion_demo: str | None = None
) -> Proveedor:
    """Alta de proveedor (RF-G01)."""
    _cuit_libre(db, _limpiar(datos.get("cuit")), id_sesion_demo)

    proveedor = Proveedor(
        razon_social=datos["razon_social"],
        **{
            campo: _limpiar(datos.get(campo))
            for campo in CAMPOS
            if campo != "razon_social"
        },
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(proveedor)
    db.flush()
    return proveedor


def actualizar(
    db: Session,
    id_proveedor: int,
    datos: dict,
    id_sesion_demo: str | None = None,
) -> Proveedor:
    """Edicion de proveedor (RF-G01)."""
    proveedor = obtener(db, id_proveedor, id_sesion_demo)
    _cuit_libre(
        db, _limpiar(datos.get("cuit")), id_sesion_demo, excluir=id_proveedor
    )

    proveedor.razon_social = datos["razon_social"]
    for campo in CAMPOS:
        if campo != "razon_social":
            setattr(proveedor, campo, _limpiar(datos.get(campo)))
    db.flush()
    return proveedor


def tiene_historial(db: Session, id_proveedor: int) -> bool:
    """True si el proveedor tiene compras o productos asociados."""
    con_compras = db.scalars(
        select(Compra.id).where(Compra.id_proveedor == id_proveedor).limit(1)
    ).first()
    if con_compras is not None:
        return True
    con_productos = db.scalars(
        select(Producto.id)
        .where(Producto.id_proveedor == id_proveedor)
        .limit(1)
    ).first()
    return con_productos is not None


def eliminar(
    db: Session, id_proveedor: int, id_sesion_demo: str | None = None
) -> tuple[Proveedor, bool]:
    """Da de baja un proveedor.

    Con compras o productos asociados se desactiva: borrarlo dejaria las
    compras sin duena y los productos apuntando a un id que ya no existe.
    """
    proveedor = obtener(db, id_proveedor, id_sesion_demo)

    if tiene_historial(db, id_proveedor):
        proveedor.activo = False
        db.flush()
        return proveedor, False

    db.delete(proveedor)
    db.flush()
    return proveedor, True


def productos_que_provee(
    db: Session, id_proveedor: int, id_sesion_demo: str | None = None
) -> list[Producto]:
    """Productos asociados al proveedor (RF-G02)."""
    obtener(db, id_proveedor, id_sesion_demo)
    return list(
        db.scalars(
            select(Producto)
            .where(
                Producto.id_proveedor == id_proveedor,
                Producto.activo.is_(True),
            )
            .order_by(Producto.nombre)
        )
    )
