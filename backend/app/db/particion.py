"""Aislamiento de los sandboxes de la demo en la capa ORM (RF-J03).

Cada servicio ya filtra por id_sesion_demo, pero eso depende de que cada
ruta le pase el valor correcto. Una ruta nueva que se olvide de hacerlo
le mostraria a un visitante anonimo los datos reales del comercio. Este
modulo agrega un segundo cerrojo que no depende de acordarse de nada:

- Lecturas: toda consulta ORM de una sesion con particion fijada se
  restringe a esa particion, incluidos Session.get, conteos, selects de
  columnas, updates y deletes masivos, y las cargas de relaciones.
- Escrituras: antes de cada flush se revisa que ninguna fila nueva,
  modificada o borrada pertenezca a otra particion. Si pasa, la
  transaccion se aborta con FugaDeParticion: un bug se ve como un 500 en
  las pruebas y no como datos cruzados en produccion.

Una sesion sin particion fijada no se filtra. Es la de los procesos del
sistema, como la limpieza de sandboxes vencidos, que tienen que ver
todas las filas.
"""

from functools import cache
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

CLAVE_EN_SESION = "particion"


@runtime_checkable
class ConParticion(Protocol):
    """Modelo que lleva la columna de particion."""

    id_sesion_demo: Any


class FugaDeParticion(RuntimeError):
    """Una escritura intento cruzar datos entre particiones."""


def fijar(sesion: Session, id_sesion_demo: str | None) -> None:
    """Restringe la sesion a un sandbox, o a la aplicacion si es None."""
    sesion.info[CLAVE_EN_SESION] = id_sesion_demo


def liberar(sesion: Session) -> None:
    """Quita la restriccion. Solo para procesos del sistema y pruebas."""
    sesion.info.pop(CLAVE_EN_SESION, None)


def actual(sesion: Session) -> tuple[bool, str | None]:
    """Si la sesion esta restringida, y a que particion."""
    if CLAVE_EN_SESION not in sesion.info:
        return False, None
    return True, sesion.info[CLAVE_EN_SESION]


@cache
def modelos_particionados() -> tuple[type[ConParticion], ...]:
    """Clases con columna id_sesion_demo.

    Se calcula la primera vez que se usa y no al importar: en ese momento
    todavia no se registraron todos los modelos.
    """
    import app.models  # noqa: F401
    from app.db.base import Base

    return tuple(
        mapeo.class_
        for mapeo in Base.registry.mappers
        if "id_sesion_demo" in mapeo.columns
    )


@event.listens_for(Session, "do_orm_execute")
def _filtrar_lecturas(estado: ORMExecuteState) -> None:
    restringida, valor = actual(estado.session)
    if not restringida:
        return
    if estado.is_column_load or estado.is_relationship_load:
        # El criterio agregado a la consulta original ya se propaga a
        # estas cargas; volver a agregarlo solo duplica el WHERE.
        return
    if not (estado.is_select or estado.is_update or estado.is_delete):
        return

    if valor is None:
        criterio = lambda cls: cls.id_sesion_demo.is_(None)  # noqa: E731
    else:
        criterio = lambda cls: cls.id_sesion_demo == valor  # noqa: E731

    estado.statement = estado.statement.options(
        *(
            with_loader_criteria(modelo, criterio, include_aliases=True)
            for modelo in modelos_particionados()
        )
    )


@event.listens_for(Session, "before_flush")
def _custodiar_escrituras(sesion: Session, _contexto, _instancias) -> None:
    restringida, valor = actual(sesion)
    if not restringida:
        return

    modelos = modelos_particionados()
    for fila in (*sesion.new, *sesion.dirty, *sesion.deleted):
        if isinstance(fila, modelos) and fila.id_sesion_demo != valor:
            raise FugaDeParticion(
                f"{type(fila).__name__} fuera de la particion de la sesion."
            )
