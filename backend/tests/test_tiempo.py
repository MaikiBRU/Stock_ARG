"""El dia del comercio es el de Buenos Aires, no el de UTC (RNF-15).

El caso que importa es el de la noche: a las 23:30 de Argentina en UTC
ya es manana. Calcular la jornada en UTC dejaba el panel en blanco justo
en el horario de mas movimiento de un kiosco.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.core import tiempo
from app.core.config import Settings
from app.models import EstadoVenta, MedioPago, Rol, Usuario, Venta
from app.services import reportes

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def _en_argentina(dia: date, hora: time) -> datetime:
    """Un instante del reloj argentino, guardado como UTC."""
    return datetime.combine(dia, hora, tzinfo=ZONA).astimezone(UTC)


def test_el_dia_del_comercio_arranca_tres_horas_despues_que_el_utc():
    dia = date(2026, 9, 17)

    assert tiempo.inicio_del_dia(dia) == datetime(2026, 9, 17, 3, tzinfo=UTC)
    assert tiempo.fin_del_dia(dia).astimezone(UTC).date() == date(2026, 9, 18)


def test_una_fecha_sin_zona_se_lee_como_utc():
    """SQLite devuelve las fechas sin zona; se guardaron en UTC."""
    guardado = datetime(2026, 9, 18, 1, 30)

    local = tiempo.en_zona(guardado)

    assert local.date() == date(2026, 9, 17)
    assert local.hour == 22


def test_una_zona_desconocida_no_deja_arrancar(monkeypatch):
    monkeypatch.setenv("ZONA_HORARIA", "Marte/Olympus")

    with pytest.raises(ValueError, match="zona_horaria"):
        Settings()


def _comercio(db):
    usuario = Usuario(
        email="propietario@stockarg.com.ar",
        nombre="Propietaria",
        rol=Rol.PROPIETARIO,
        verificado=True,
        activo=True,
    )
    medio = MedioPago(nombre="Efectivo", es_efectivo=True)
    db.add_all([usuario, medio])
    db.commit()
    return usuario, medio


def _venta(db, usuario, medio, momento):
    venta = Venta(
        fecha_hora=momento,
        id_usuario=usuario.id,
        id_medio_pago=medio.id,
        estado=EstadoVenta.REGISTRADA,
        total=Decimal("1000.00"),
        descuento=Decimal("0.00"),
    )
    db.add(venta)
    db.commit()
    return venta


def test_la_venta_de_las_once_de_la_noche_entra_en_el_dia_del_comercio(db):
    usuario, medio = _comercio(db)
    hoy = tiempo.hoy()
    # 23:30 de hoy en Argentina: en UTC ya es manana.
    _venta(db, usuario, medio, _en_argentina(hoy, time(23, 30)))

    datos = reportes.ventas_por_periodo(db, periodo="hoy")

    assert datos["cantidad_ventas"] == 1


def test_la_venta_de_anoche_no_se_cuenta_como_de_hoy(db):
    usuario, medio = _comercio(db)
    ayer = tiempo.hoy() - timedelta(days=1)
    # 21:30 de ayer en Argentina: en UTC ya figura como hoy.
    _venta(db, usuario, medio, _en_argentina(ayer, time(21, 30)))

    datos = reportes.ventas_por_periodo(db, periodo="hoy")

    assert datos["cantidad_ventas"] == 0
    assert datos["sin_datos"] is True


def test_la_serie_diaria_agrupa_por_el_dia_del_comercio(db):
    usuario, medio = _comercio(db)
    hoy = tiempo.hoy()
    ayer = hoy - timedelta(days=1)
    _venta(db, usuario, medio, _en_argentina(hoy, time(23, 30)))
    _venta(db, usuario, medio, _en_argentina(ayer, time(21, 30)))

    serie = {
        punto["fecha"]: punto["cantidad_ventas"]
        for punto in reportes.serie_diaria(db, periodo="semana")
    }

    assert serie[hoy] == 1
    assert serie[ayer] == 1
