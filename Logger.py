"""Utilidades de logging para la aplicación."""

import logging
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log_info(mensaje):
    """Registra un mensaje de información."""
    logging.info(mensaje)

def log_warning(mensaje):
    """Registra un mensaje de advertencia."""
    logging.warning(mensaje)

def log_error(mensaje):
    """Registra un mensaje de error."""
    logging.error(mensaje)
