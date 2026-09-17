"""Fechas y horas en la zona del comercio (RNF-15).

Los instantes se guardan siempre en UTC, que es lo unico que no se
mueve. Pero "hoy", "esta semana" y "vence manana" son preguntas del
comercio, y el comercio vive en Buenos Aires: entre las 21 y la
medianoche de Argentina en UTC ya es el dia siguiente, asi que calcular
el dia en UTC hace que el panel muestre una jornada vacia justo cuando
el local todavia esta vendiendo.

Todo lo que sale de aca hacia una consulta esta convertido a UTC. Es a
proposito: SQLite guarda la hora sin zona, asi que comparar contra una
fecha con otro huso escribiria la hora equivocada en el WHERE.
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def zona() -> ZoneInfo:
    """Zona horaria del comercio."""
    return ZoneInfo(get_settings().zona_horaria)


def ahora() -> datetime:
    """Instante actual, en UTC."""
    return datetime.now(UTC)


def hoy() -> date:
    """Dia en curso segun el reloj del comercio."""
    return datetime.now(zona()).date()


def inicio_del_dia(dia: date) -> datetime:
    """Primer instante de ese dia local, expresado en UTC."""
    return datetime.combine(dia, time.min, tzinfo=zona()).astimezone(UTC)


def fin_del_dia(dia: date) -> datetime:
    """Ultimo instante de ese dia local, expresado en UTC."""
    return datetime.combine(dia, time.max, tzinfo=zona()).astimezone(UTC)


def en_zona(momento: datetime) -> datetime:
    """Pasa a la zona del comercio un instante guardado en UTC.

    Una fecha leida de SQLite viene sin zona; se asume UTC, que es como
    se guardo.
    """
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(zona())
