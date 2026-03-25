"""Persistencia de sesión local en disco."""

import json
import os
import Sesion

ARCHIVO_SESION = "sesion.json"


def guardar_sesion(usuario):
    """Guarda el usuario autenticado en un archivo JSON."""
    with open(ARCHIVO_SESION, "w", encoding="utf-8") as f:
        json.dump(usuario, f)


def cargar_sesion():
    """Carga la sesión desde disco si existe."""
    if not os.path.exists(ARCHIVO_SESION):
        return None

    try:
        with open(ARCHIVO_SESION, "r", encoding="utf-8") as f:
            Sesion.usuario_actual = json.load(f)
            return Sesion.usuario_actual
    except:
        return None


def cerrar_sesion():
    """Elimina la sesión persistente y limpia el estado global."""
    if os.path.exists(ARCHIVO_SESION):
        os.remove(ARCHIVO_SESION)

    Sesion.usuario_actual = None
    return True
