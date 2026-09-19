"""Manda un correo de prueba con la configuracion SMTP del .env.

Uso, desde backend/ (o dentro del contenedor de la API):

    python -m app.probar_correo tu-correo@ejemplo.com

Sirve para comprobar el proveedor sin crear una cuenta en la app. Usa
las mismas variables que la API (SMTP_*, EMAIL_FROM) y nunca imprime la
clave: si algo falla, muestra solo el tipo de error.
"""

import sys

from app.core.config import get_settings
from app.services import correo


def main() -> int:
    """Envia la prueba y devuelve el codigo de salida."""
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Uso: python -m app.probar_correo tu-correo@ejemplo.com")
        return 2

    # En desarrollo el envio va al log; para la prueba se fuerza el
    # camino de produccion sin tocar el .env.
    ajustes = get_settings().model_copy(update={"environment": "production"})
    correo.get_settings = lambda: ajustes  # type: ignore[assignment]

    try:
        correo._enviar(
            sys.argv[1],
            "Prueba de correo de StockARG",
            "Si leés esto, el envío de correo de StockARG funciona.",
        )
    except correo.ErrorDeEnvio as error:
        causa = type(error.__cause__).__name__ if error.__cause__ else ""
        print(f"No se pudo enviar: {error} {causa}".strip())
        return 1

    print(f"Enviado a {sys.argv[1]} desde {ajustes.email_from}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
