"""Envio de correo por SMTP.

SMTP y no la API de un proveedor: cualquier servicio lo habla (Resend,
Cloudflare Email Service, Brevo, Gmail), asi que cambiar de proveedor
es cambiar variables de entorno, no codigo.

En desarrollo no se envia nada: el mensaje se escribe en el log para
poder seguir el flujo sin una cuenta. En produccion eso seria poner un
codigo de acceso en un archivo, asi que el volcado al log esta cerrado
por entorno y no por una variable que alguien pueda encender sin darse
cuenta.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.core.config import get_settings

registro = logging.getLogger("stockarg.correo")

# Un servidor que no contesta no puede dejar colgado el pedido de alta.
ESPERA_SEGUNDOS = 15


class ErrorDeEnvio(Exception):
    """No se pudo entregar el mensaje."""


def _armar(destinatario: str, asunto: str, cuerpo: str) -> EmailMessage:
    ajustes = get_settings()
    mensaje = EmailMessage()
    mensaje["From"] = formataddr(
        (ajustes.email_from_nombre, ajustes.email_from)
    )
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje["Date"] = formatdate(localtime=False)
    mensaje["Message-ID"] = make_msgid(domain=ajustes.email_from.split("@")[-1])
    mensaje.set_content(cuerpo)
    return mensaje


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

    clave = ajustes.smtp_contrasena
    if not ajustes.smtp_host or not ajustes.smtp_usuario or clave is None:
        raise ErrorDeEnvio("El envio de correo no esta configurado.")

    mensaje = _armar(destinatario, asunto, cuerpo)
    contexto = ssl.create_default_context()
    try:
        # 465 es TLS desde el primer byte; cualquier otro puerto (587)
        # arranca en claro y tiene que pasar a TLS antes del login. Si
        # el servidor no ofrece STARTTLS, starttls() falla y la clave no
        # viaja sin cifrar.
        conexion: smtplib.SMTP
        if ajustes.smtp_puerto == 465:
            conexion = smtplib.SMTP_SSL(
                ajustes.smtp_host,
                ajustes.smtp_puerto,
                timeout=ESPERA_SEGUNDOS,
                context=contexto,
            )
        else:
            conexion = smtplib.SMTP(
                ajustes.smtp_host, ajustes.smtp_puerto, timeout=ESPERA_SEGUNDOS
            )
        with conexion:
            if ajustes.smtp_puerto != 465:
                conexion.starttls(context=contexto)
            conexion.login(ajustes.smtp_usuario, clave.get_secret_value())
            conexion.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as error:
        # El detalle del servidor puede repetir datos de la sesion: se
        # registra solo el tipo de falla, nunca el mensaje completo.
        registro.error(
            "Fallo el envio de correo a %s (%s)",
            destinatario,
            type(error).__name__,
        )
        raise ErrorDeEnvio("No se pudo enviar el correo.") from error


def enviar_codigo_de_verificacion(destinatario: str, codigo: str) -> None:
    """Manda el codigo de alta de cuenta (RF-A01)."""
    _enviar(
        destinatario,
        "Tu código de verificación de StockARG",
        f"Tu código es {codigo}. Vence en 30 minutos.\n"
        "Si no creaste una cuenta, ignorá este mensaje.",
    )


def enviar_enlace_de_recuperacion(destinatario: str, token: str) -> None:
    """Manda el enlace para restablecer la contrasena (RF-A04)."""
    ajustes = get_settings()
    enlace = f"{ajustes.frontend_url}/restablecer?token={token}"
    _enviar(
        destinatario,
        "Restablecer tu contraseña de StockARG",
        f"Para elegir una contraseña nueva entrá a:\n{enlace}\n\n"
        "El enlace vence en una hora y sirve una sola vez.\n"
        "Si no pediste esto, ignorá el mensaje: tu contraseña no cambió.",
    )
