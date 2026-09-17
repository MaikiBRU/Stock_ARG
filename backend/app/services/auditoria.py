"""Registro de auditoria (RF-I04).

Deja constancia de quien hizo que y cuando. Se copia el correo del
usuario ademas de su id: si la cuenta se elimina mas adelante, la linea
tiene que seguir diciendo quien fue.
"""

from datetime import date
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core import tiempo
from app.core.security import hash_opaco
from app.models import Auditoria, Usuario

# Nunca entra al detalle: son los nombres de campo que, si se colaran,
# dejarian una credencial escrita en una tabla que se consulta desde la
# pantalla de administracion.
PROHIBIDOS = {
    "password",
    "contrasena",
    "contrasena_nueva",
    "contrasena_actual",
    "password_hash",
    "token",
    "access_token",
    "codigo",
    "secret",
    "secret_key",
}


def _limpiar_detalle(detalle: dict[str, Any] | None) -> dict[str, Any] | None:
    """Saca del detalle cualquier campo sensible.

    Filtrar aca y no en cada llamada es lo que hace que agregar una
    accion nueva no pueda introducir una filtracion por descuido.
    """
    if not detalle:
        return None
    return {
        clave: valor
        for clave, valor in detalle.items()
        if clave.lower() not in PROHIBIDOS
    }


def registrar(
    db: Session,
    *,
    usuario: Usuario | None,
    accion: str,
    entidad: str,
    id_entidad: str | int | None = None,
    detalle: dict[str, Any] | None = None,
    ip: str | None = None,
) -> Auditoria:
    """Anota una operacion sensible."""
    linea = Auditoria(
        id_usuario=usuario.id if usuario else None,
        email_usuario=usuario.email if usuario else None,
        accion=accion,
        entidad=entidad,
        id_entidad=str(id_entidad) if id_entidad is not None else None,
        detalle=_limpiar_detalle(detalle),
        ip_hash=hash_opaco(ip) if ip else None,
        # La linea queda en la particion de quien actua: una accion hecha
        # dentro de un sandbox muere con el.
        id_sesion_demo=usuario.id_sesion_demo if usuario else None,
    )
    db.add(linea)
    db.flush()
    return linea


def listar(
    db: Session,
    *,
    accion: str | None = None,
    entidad: str | None = None,
    id_usuario: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    desplazamiento: int = 0,
    limite: int = 25,
    id_sesion_demo: str | None = None,
) -> tuple[list[Auditoria], int]:
    """Historial de auditoria, filtrable (RF-I04)."""
    consulta: Select = select(Auditoria).where(
        Auditoria.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Auditoria.id_sesion_demo == id_sesion_demo
    )

    if accion:
        consulta = consulta.where(Auditoria.accion == accion)
    if entidad:
        consulta = consulta.where(Auditoria.entidad == entidad)
    if id_usuario is not None:
        consulta = consulta.where(Auditoria.id_usuario == id_usuario)
    if desde is not None:
        consulta = consulta.where(
            Auditoria.fecha_hora >= tiempo.inicio_del_dia(desde)
        )
    if hasta is not None:
        consulta = consulta.where(
            Auditoria.fecha_hora <= tiempo.fin_del_dia(hasta)
        )

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = db.scalars(
        consulta.order_by(Auditoria.fecha_hora.desc(), Auditoria.id.desc())
        .offset(desplazamiento)
        .limit(limite)
    ).all()
    return list(pagina), total or 0
