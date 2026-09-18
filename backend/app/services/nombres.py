"""Nombres para mostrar junto a los ids de un listado.

Los historiales guardan ids; la pantalla necesita nombres. Resolverlos
aca, con una consulta por tabla y por pagina, evita que el navegador
tenga que bajar catalogos enteros (algunos, como usuarios, ni siquiera
los puede leer cualquier rol).
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.models import Cliente, MedioPago, Producto, Proveedor, Usuario


def _particion(modelo: Any, id_sesion_demo: str | None) -> ColumnElement[bool]:
    return (
        modelo.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else modelo.id_sesion_demo == id_sesion_demo
    )


def _buscar(
    db: Session,
    modelo: Any,
    columnas: tuple[Any, ...],
    ids: Iterable[int | None],
    id_sesion_demo: str | None,
) -> list[Any]:
    buscados = {v for v in ids if v is not None}
    if not buscados:
        return []
    return list(
        db.execute(
            select(modelo.id, *columnas).where(
                modelo.id.in_(buscados), _particion(modelo, id_sesion_demo)
            )
        )
    )


def de_usuarios(
    db: Session, ids: Iterable[int | None], id_sesion_demo: str | None
) -> dict[int, str]:
    """Nombre de cada usuario."""
    filas = _buscar(db, Usuario, (Usuario.nombre,), ids, id_sesion_demo)
    return {id_: nombre for id_, nombre in filas}


def de_medios(
    db: Session, ids: Iterable[int | None], id_sesion_demo: str | None
) -> dict[int, str]:
    """Nombre de cada medio de pago."""
    filas = _buscar(db, MedioPago, (MedioPago.nombre,), ids, id_sesion_demo)
    return {id_: nombre for id_, nombre in filas}


def de_clientes(
    db: Session, ids: Iterable[int | None], id_sesion_demo: str | None
) -> dict[int, str]:
    """Nombre y apellido de cada cliente."""
    filas = _buscar(
        db, Cliente, (Cliente.nombre, Cliente.apellido), ids, id_sesion_demo
    )
    return {
        id_: f"{nombre} {apellido}" if apellido else nombre
        for id_, nombre, apellido in filas
    }


def de_proveedores(
    db: Session, ids: Iterable[int | None], id_sesion_demo: str | None
) -> dict[int, str]:
    """Razon social de cada proveedor."""
    filas = _buscar(
        db, Proveedor, (Proveedor.razon_social,), ids, id_sesion_demo
    )
    return {id_: nombre for id_, nombre in filas}


def de_productos(
    db: Session, ids: Iterable[int | None], id_sesion_demo: str | None
) -> dict[int, str]:
    """Nombre de cada producto."""
    filas = _buscar(db, Producto, (Producto.nombre,), ids, id_sesion_demo)
    return {id_: nombre for id_, nombre in filas}
