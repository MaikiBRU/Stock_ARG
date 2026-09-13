"""Demo publica: sandboxes anonimos y temporales (modulo J).

Cada visitante del portfolio recibe un comercio propio, sembrado con
datos de ejemplo, que vive en la misma base que la aplicacion pero en
otra particion (ver app.db.particion). Nadie se registra: el token de la
demo nombra al sandbox y al rol con el que se lo recorre, no a un
usuario, asi que sigue valiendo despues de reiniciar el sandbox.

La sesion muere por vencimiento absoluto o por inactividad, lo que pase
primero, y eso se decide en cada peticion (RF-J05). La limpieza
periodica solo recupera espacio: no es la que corta el acceso.
"""

import math
import random
import secrets
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, delete, event, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import crear_token, generar_token_urlsafe, hash_opaco
from app.db import particion
from app.models import (
    Auditoria,
    BajaProducto,
    Categoria,
    Cliente,
    Compra,
    CompraItem,
    Configuracion,
    MedioPago,
    MovimientoStock,
    Producto,
    Proveedor,
    Rol,
    SesionDemo,
    Usuario,
    Venta,
    VentaItem,
)

# Acciones que no dejan filas propias y se cuentan en la sesion.
RECURSOS_CONTADOS = ("importaciones", "exportaciones")

# Cada cuanto se anota la ultima actividad. Anotarla en cada peticion no
# agrega precision que sirva y le suma una escritura a cada lectura.
INTERVALO_DE_ACTIVIDAD = timedelta(seconds=30)

# Marca de la sesion de base mientras se siembra: los cupos de filas no
# aplican a los datos de ejemplo, que ya estan acotados por el codigo.
CLAVE_SEMBRANDO = "demo_sembrando"


class ErrorDeDemo(Exception):
    """Falla esperable de una operacion de la demo."""

    def __init__(self, mensaje: str, codigo: str) -> None:
        """Guarda el mensaje visible y un codigo para el frontend."""
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class DemoSinCapacidad(ErrorDeDemo):
    """Se alcanzo el tope global de sandboxes activos."""


class CupoAgotado(ErrorDeDemo):
    """El sandbox llego al maximo de algun recurso (RF-J06)."""

    def __init__(self, recurso: str, maximo: int) -> None:
        """Arma el mensaje con el recurso y su tope."""
        if recurso in RECURSOS_CONTADOS:
            # Estos contadores sobreviven al reinicio: sugerirlo seria
            # mandar al visitante a un callejon sin salida.
            mensaje = f"La demo llego al maximo de {recurso} ({maximo})."
        else:
            mensaje = (
                f"La demo llego al maximo de {recurso} ({maximo}). "
                "Reinicie la demo para empezar de nuevo."
            )
        super().__init__(mensaje, "cupo_agotado")
        self.recurso = recurso
        self.maximo = maximo

    def detalle(self) -> dict[str, Any]:
        """Cuerpo de la respuesta 429."""
        return {
            "mensaje": self.mensaje,
            "codigo": self.codigo,
            "recurso": self.recurso,
            "maximo": self.maximo,
        }


def _ahora() -> datetime:
    """Momento actual en UTC."""
    return datetime.now(UTC)


def _con_zona(momento: datetime) -> datetime:
    """Completa la zona de una fecha leida de SQLite, que la pierde."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


# --- vigencia (RF-J05) ---------------------------------------------------


def expira_en(sesion: SesionDemo) -> datetime:
    """Vencimiento absoluto, fijado al crear la sesion."""
    return _con_zona(sesion.expira_en)


def vence_por_inactividad(sesion: SesionDemo) -> datetime:
    """Momento en que la sesion muere si nadie la usa."""
    minutos = get_settings().demo_idle_timeout_minutes
    return _con_zona(sesion.ultima_actividad) + timedelta(minutes=minutos)


def vence(sesion: SesionDemo) -> datetime:
    """Lo que llegue primero: el vencimiento o la inactividad."""
    return min(expira_en(sesion), vence_por_inactividad(sesion))


def esta_vigente(sesion: SesionDemo, ahora: datetime | None = None) -> bool:
    """True si la sesion todavia sirve."""
    return (ahora or _ahora()) < vence(sesion)


def _vencidas(ahora: datetime) -> ColumnElement[bool]:
    """Condicion SQL equivalente a no estar vigente."""
    inactividad = timedelta(minutes=get_settings().demo_idle_timeout_minutes)
    return or_(
        SesionDemo.expira_en <= ahora,
        SesionDemo.ultima_actividad <= ahora - inactividad,
    )


def contar_activas(db: Session, ahora: datetime | None = None) -> int:
    """Sandboxes vigentes en este momento."""
    return (
        db.scalar(
            select(func.count())
            .select_from(SesionDemo)
            .where(~_vencidas(ahora or _ahora()))
        )
        or 0
    )


# --- alta, reinicio y fin (RF-J01, RF-J08) -------------------------------


def _sembrar(db: Session, id_sesion: str) -> Usuario:
    """Llena el sandbox con la particion ya fijada.

    Fijar la particion antes de sembrar no es un detalle: el cerrojo de
    escrituras verifica que cada fila de ejemplo quede en este sandbox y
    no en la aplicacion.
    """
    from app.services import demo_semilla

    particion.fijar(db, id_sesion)
    db.info[CLAVE_SEMBRANDO] = True
    try:
        return demo_semilla.sembrar(
            db, id_sesion, random.Random(secrets.randbits(64))
        )
    finally:
        db.info.pop(CLAVE_SEMBRANDO, None)


def crear_sesion(db: Session, ip: str | None) -> tuple[SesionDemo, Usuario]:
    """Abre un sandbox sembrado y devuelve su propietaria (RF-J01).

    Todo va en una transaccion: si la semilla falla a mitad de camino, no
    queda ni la sesion ni ninguna fila suelta. Un sandbox a medias nunca
    se entrega.
    """
    ajustes = get_settings()
    ahora = _ahora()

    if contar_activas(db, ahora) >= ajustes.demo_max_active_sessions:
        raise DemoSinCapacidad(
            "La demo esta completa en este momento. "
            "Pruebe de nuevo en unos minutos.",
            "demo_completa",
        )

    sesion = SesionDemo(
        # 32 bytes de secrets: no es una secuencia y no se puede adivinar.
        id=generar_token_urlsafe(32),
        creada_en=ahora,
        ultima_actividad=ahora,
        expira_en=ahora + timedelta(minutes=ajustes.demo_session_ttl_minutes),
        # Alcanza para contar sesiones por visitante sin guardar su IP.
        ip_hash=hash_opaco(ip) if ip else None,
    )
    try:
        db.add(sesion)
        db.flush()
        propietario = _sembrar(db, sesion.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        particion.liberar(db)
    return sesion, propietario


def usuario_por_rol(db: Session, id_sesion: str, rol: Rol) -> Usuario | None:
    """Primer usuario activo del sandbox con ese rol."""
    return db.scalars(
        select(Usuario)
        .where(
            Usuario.id_sesion_demo == id_sesion,
            Usuario.rol == rol,
            Usuario.activo.is_(True),
        )
        .order_by(Usuario.id)
    ).first()


def reiniciar(db: Session, id_sesion: str) -> SesionDemo:
    """Vuelve el sandbox a su estado inicial, con el mismo token (RF-J08).

    Se borra la sesion, que arrastra todas sus filas por la clave foranea,
    y se la vuelve a crear con el mismo id. Conserva el vencimiento: si
    reiniciar lo renovara, una demo podria durar para siempre. Conserva
    tambien los contadores de cupo, por el mismo motivo.
    """
    anterior = db.get(SesionDemo, id_sesion)
    if anterior is None:
        raise ErrorDeDemo("La demo ya no existe.", "demo_inexistente")
    db.refresh(anterior)
    conservado = {
        "id": anterior.id,
        "creada_en": anterior.creada_en,
        "expira_en": anterior.expira_en,
        "ip_hash": anterior.ip_hash,
        "importaciones": anterior.importaciones,
        "exportaciones": anterior.exportaciones,
    }

    particion.liberar(db)
    try:
        db.execute(delete(SesionDemo).where(SesionDemo.id == id_sesion))
        # Lo que estaba en memoria ya no existe en la base. Sin esto, un
        # id reutilizado por la base chocaria con un objeto viejo.
        db.expunge_all()
        nueva = SesionDemo(**conservado, ultima_actividad=_ahora())
        db.add(nueva)
        db.flush()
        _sembrar(db, nueva.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        particion.liberar(db)
    return nueva


def terminar(db: Session, id_sesion: str) -> None:
    """Borra el sandbox en el acto (RF-J08)."""
    db.execute(delete(SesionDemo).where(SesionDemo.id == id_sesion))
    db.commit()


def purgar_vencidas(db: Session, ahora: datetime | None = None) -> int:
    """Borra los sandboxes vencidos y devuelve cuantos (RF-J09).

    Es idempotente: una segunda pasada no encuentra nada. No puede tocar
    filas de la aplicacion, porque solo borra sesiones y lo demas cae por
    ON DELETE CASCADE, que por construccion no alcanza a una fila con
    id_sesion_demo NULL. Tampoco quedan huerfanos que reclamar: la clave
    foranea impide que exista una fila de sandbox sin su sesion.
    """
    resultado = db.execute(
        delete(SesionDemo)
        .where(_vencidas(ahora or _ahora()))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return resultado.rowcount or 0


# --- tokens --------------------------------------------------------------


def emitir_token(sesion: SesionDemo, usuario: Usuario) -> str:
    """Token de demo para recorrer el sandbox con el rol del usuario.

    Vence junto con la sesion. La inactividad no se puede anticipar en el
    token: la controla la API en cada peticion.
    """
    restante = (expira_en(sesion) - _ahora()).total_seconds()
    return crear_token(
        f"demo:{sesion.id}",
        tipo="demo",
        minutos=max(1, math.ceil(restante / 60)),
        sid=sesion.id,
        rol=usuario.rol.value,
        sv=usuario.version_sesion or 0,
    )


def usuario_del_token(db: Session, carga: dict[str, Any]) -> Usuario | None:
    """Usuario del sandbox al que apunta un token de demo, si sigue vivo.

    Devuelve None ante cualquier problema, sin distinguir cual: una
    sesion inexistente, vencida o terminada y un token armado a mano
    reciben la misma respuesta, asi que probar no revela nada.
    """
    if not get_settings().demo_enabled:
        return None

    id_sesion = carga.get("sid")
    if not isinstance(id_sesion, str):
        return None
    if carga.get("sub") != f"demo:{id_sesion}":
        return None
    try:
        rol = Rol(carga.get("rol"))
    except ValueError:
        return None

    sesion = db.get(SesionDemo, id_sesion)
    ahora = _ahora()
    if sesion is None or not esta_vigente(sesion, ahora):
        return None

    usuario = usuario_por_rol(db, id_sesion, rol)
    if usuario is None:
        return None
    if carga.get("sv", 0) != (usuario.version_sesion or 0):
        return None

    if ahora - _con_zona(sesion.ultima_actividad) >= INTERVALO_DE_ACTIVIDAD:
        sesion.ultima_actividad = ahora
        db.commit()
    return usuario


# --- cupos (RF-J06) ------------------------------------------------------


def cupos_de_filas() -> dict[type, tuple[str, int]]:
    """Maximo de filas por tabla dentro de un sandbox.

    Los que pide el requerimiento se configuran por entorno. El resto
    son topes de seguridad: sin ellos, un visitante podria llenar la base
    compartida por una tabla que nadie penso en acotar.
    """
    ajustes = get_settings()
    return {
        Producto: ("productos", ajustes.demo_max_productos),
        Venta: ("ventas", ajustes.demo_max_ventas),
        VentaItem: ("lineas de venta", 4000),
        Compra: ("compras", 200),
        CompraItem: ("lineas de compra", 3000),
        MovimientoStock: ("movimientos de stock", 8000),
        BajaProducto: ("bajas", 500),
        Cliente: ("clientes", 300),
        Proveedor: ("proveedores", 100),
        Categoria: ("categorias", 60),
        MedioPago: ("medios de pago", 20),
        Usuario: ("usuarios", 15),
        Auditoria: ("lineas de auditoria", 2000),
        Configuracion: ("parametros", 50),
    }


def consumir_cupo(db: Session, id_sesion: str, recurso: str) -> None:
    """Descuenta un uso de un recurso contado, o corta si no quedan.

    Un solo UPDATE condicional hace la cuenta y el control a la vez: dos
    peticiones simultaneas no pueden pasar las dos con el ultimo lugar.
    Se confirma en el acto para que un rollback posterior de la
    operacion no devuelva el uso.
    """
    if recurso not in RECURSOS_CONTADOS:
        raise ValueError(f"El recurso {recurso!r} no tiene cupo contado.")

    maximo = getattr(get_settings(), f"demo_max_{recurso}")
    columna = getattr(SesionDemo, recurso)
    resultado = db.execute(
        update(SesionDemo)
        .where(SesionDemo.id == id_sesion, columna < maximo)
        .values({columna: columna + 1})
        .execution_options(synchronize_session=False)
    )
    if not resultado.rowcount:
        db.rollback()
        raise CupoAgotado(recurso, maximo)
    db.commit()


def estado_de_cupos(
    db: Session, sesion: SesionDemo
) -> dict[str, dict[str, int]]:
    """Uso y maximo de los cupos que ve el visitante."""
    ajustes = get_settings()
    db.refresh(sesion)

    def contar(modelo: type) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(modelo)
                .where(modelo.id_sesion_demo == sesion.id)
            )
            or 0
        )

    return {
        "productos": {
            "usados": contar(Producto),
            "maximo": ajustes.demo_max_productos,
        },
        "ventas": {"usados": contar(Venta), "maximo": ajustes.demo_max_ventas},
        "importaciones": {
            "usados": sesion.importaciones,
            "maximo": ajustes.demo_max_importaciones,
        },
        "exportaciones": {
            "usados": sesion.exportaciones,
            "maximo": ajustes.demo_max_exportaciones,
        },
    }


@event.listens_for(Session, "before_flush")
def _controlar_cupos(sesion: Session, _contexto, _instancias) -> None:
    """Corta cualquier escritura que pase un tope de filas del sandbox.

    Vive en el flush y no en cada endpoint: asi alcanza a todo camino que
    cree filas, incluidas las importaciones y los que se agreguen despues.
    """
    restringida, id_sesion = particion.actual(sesion)
    if not restringida or id_sesion is None:
        return
    if sesion.info.get(CLAVE_SEMBRANDO):
        return

    nuevos = Counter(type(fila) for fila in sesion.new)
    if not nuevos:
        return

    cupos = cupos_de_filas()
    for modelo, cantidad in nuevos.items():
        if modelo not in cupos:
            continue
        nombre, maximo = cupos[modelo]
        existentes = (
            sesion.scalar(
                select(func.count())
                .select_from(modelo)
                .where(modelo.id_sesion_demo == id_sesion)
            )
            or 0
        )
        if existentes + cantidad > maximo:
            raise CupoAgotado(nombre, maximo)
