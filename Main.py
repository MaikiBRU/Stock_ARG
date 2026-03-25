"""Punto de entrada: decide si abrir menú o login."""

from SesionPersistente import cargar_sesion
from Login import login, splash_screen
from Menu import crear_menu
from Theme import init_app_identity
import Sesion
import tkinter as tk


def main():
    init_app_identity()
    """Carga sesión persistente y abre la UI correspondiente."""
    def init_app():
        cargar_sesion()
        return Sesion.usuario_actual

    def launch_app(user):
        if user:
            crear_menu()
        else:
            login()

    def splash_msg(result, done):
        if not done:
            return "Cargando"
        return "Cargando menú" if result else "Cargando login"

    splash_screen(
        work_fn=init_app,
        on_done=launch_app,
        message="Cargando",
        message_fn=splash_msg,
        min_duration=1400
    )


if __name__ == "__main__":
    main()
