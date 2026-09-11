"""Estado del servicio."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db

router = APIRouter(tags=["salud"])


@router.get("/salud")
def salud(
    db: Session = Depends(get_db),
    ajustes: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Informa version y si la base responde.

    No revela la cadena de conexion ni el nombre de la base: solo si la
    consulta de prueba llego a destino.
    """
    try:
        db.execute(text("SELECT 1"))
        base_ok = True
    except Exception:  # noqa: BLE001 - el detalle no se expone
        base_ok = False

    return {
        "ok": base_ok,
        "sistema": ajustes.app_name,
        "version": ajustes.app_version,
        "base_de_datos": "conectada" if base_ok else "sin conexion",
    }
