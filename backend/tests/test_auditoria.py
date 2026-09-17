"""Registro de auditoria: que guarda y como filtra (RF-I04)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core import tiempo
from app.core.security import hash_opaco
from app.models import Auditoria, Rol, Usuario
from app.services import auditoria

IP = "203.0.113.7"
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def _usuario(db):
    usuario = Usuario(
        email="propietario@stockarg.com.ar",
        nombre="Propietaria",
        rol=Rol.PROPIETARIO,
        verificado=True,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    return usuario


def _anotar(db, usuario, **extra):
    linea = auditoria.registrar(
        db,
        usuario=usuario,
        accion="usuario.crear",
        entidad="usuario",
        id_entidad=1,
        **extra,
    )
    db.commit()
    return linea


def test_la_auditoria_guarda_la_huella_de_la_ip_y_no_la_ip(db):
    """Tambien anota lo que hace un visitante anonimo de la demo."""
    usuario = _usuario(db)

    linea = _anotar(db, usuario, ip=IP)

    assert linea.ip_hash == hash_opaco(IP)
    assert IP not in (linea.ip_hash or "")
    guardado = db.query(Auditoria).one()
    assert guardado.ip_hash == hash_opaco(IP)


def test_dos_acciones_del_mismo_lugar_comparten_huella(db):
    """La huella sirve para agrupar sin saber de donde se conectan."""
    usuario = _usuario(db)

    primera = _anotar(db, usuario, ip=IP)
    segunda = _anotar(db, usuario, ip=IP)
    otra = _anotar(db, usuario, ip="203.0.113.99")

    assert primera.ip_hash == segunda.ip_hash
    assert otra.ip_hash != primera.ip_hash


def test_sin_direccion_la_linea_queda_sin_huella(db):
    usuario = _usuario(db)

    linea = _anotar(db, usuario)

    assert linea.ip_hash is None


def test_el_filtro_por_fecha_usa_el_dia_del_comercio(db):
    """Una accion de las 23:30 en UTC ya figura como de manana."""
    usuario = _usuario(db)
    hoy = tiempo.hoy()
    linea = _anotar(db, usuario, ip=IP)
    linea.fecha_hora = datetime.combine(
        hoy, time(23, 30), tzinfo=ZONA
    ).astimezone(UTC)
    db.commit()

    de_hoy, total = auditoria.listar(db, desde=hoy, hasta=hoy)
    de_ayer, _ = auditoria.listar(
        db, desde=hoy - timedelta(days=1), hasta=hoy - timedelta(days=1)
    )

    assert total == 1
    assert [f.id for f in de_hoy] == [linea.id]
    assert de_ayer == []
