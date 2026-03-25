"""Envío de emails de verificación vía SendGrid."""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv("email.env", override=False)
except Exception:
    load_dotenv = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    _SENDGRID_OK = True
except Exception:
    _SENDGRID_OK = False
from Logger import log_error, log_warning

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


def enviar_codigo(destinatario, codigo):
    """Envía un código de verificación al email indicado."""
    if not _SENDGRID_OK:
        log_warning("SendGrid no está instalado")
        return False
    if not SENDGRID_API_KEY:
        log_warning("SENDGRID_API_KEY no configurada")
        return False
    mensaje = Mail(
        from_email="sstock.arg@gmail.com",
        to_emails=destinatario,
        subject="Código de verificación",
        html_content=f"""
        <h2>Verificación de cuenta</h2>
        <p>Tu código es:</p>
        <h1>{codigo}</h1>
        <p>Este código vence en 10 minutos.</p>
        """
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(mensaje)
        return True
    except Exception as e:
        log_error(f"Error enviando email: {e}")
        return False
