"""Envio de correo.

En desarrollo no se envia nada: el codigo se escribe en el log para
poder seguir el flujo sin una cuenta de SendGrid. En produccion eso
seria poner una credencial de acceso en un archivo, asi que el volcado
al log esta cerrado por entorno y no por una variable que alguien pueda
encender sin darse cuenta.
"""

import logging

from app.core.config import get_settings

registro = logging.getLogger("stockarg.correo")


class ErrorDeEnvio(Exception):
    """No se pudo entregar el mensaje."""


def _enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Entrega el mensaje por el canal que corresponda al entorno."""
    ajustes = get_settings()

    if not ajustes.es_produccion:
        registro.info(
            "Correo no enviado (entorno de desarrollo)\n"
            "  Para: %s\n  Asunto: %s\n  %s",
            destinatario,
            asunto,
            cuerpo,
        )
        return

    if not ajustes.sendgrid_api_key:
        raise ErrorDeEnvio("El envio de correo no esta configurado.")

    # Import local: en desarrollo el paquete no hace falta.
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    mensaje = Mail(
        from_email=ajustes.email_from,
        to_emails=destinatario,
        subject=asunto,
        plain_text_content=cuerpo,
    )
    try:
        SendGridAPIClient(ajustes.sendgrid_api_key).send(mensaje)
    except Exception as error:
        # El detalle puede traer la clave de la API; no se propaga.
        registro.error("Fallo el envio de correo a %s", destinatario)
        raise ErrorDeEnvio("No se pudo enviar el correo.") from error


def enviar_codigo_de_verificacion(destinatario: str, codigo: str) -> None:
    """Manda el codigo de alta de cuenta (RF-A01)."""
    _enviar(
        destinatario,
        "Tu codigo de verificacion de StockARG",
        f"Tu codigo es {codigo}. Vence en 30 minutos.\n"
        "Si no creaste una cuenta, ignora este mensaje.",
    )


def enviar_enlace_de_recuperacion(destinatario: str, token: str) -> None:
    """Manda el enlace para restablecer la contrasena (RF-A04)."""
    ajustes = get_settings()
    enlace = f"{ajustes.frontend_url}/restablecer?token={token}"
    _enviar(
        destinatario,
        "Restablecer tu contrasena de StockARG",
        f"Para elegir una contrasena nueva entra a:\n{enlace}\n\n"
        "El enlace vence en una hora y sirve una sola vez.\n"
        "Si no pediste esto, ignora el mensaje: tu contrasena no cambio.",
    )
