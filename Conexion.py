"""Conexión a la base de datos mediante variables de entorno."""

import os
import mysql.connector
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None
from Logger import log_error, log_warning

class cconexion:
    @staticmethod
    def cconexionBaseDeDatos():
        """Crea y devuelve una conexión a MySQL o None si falla."""
        try:
            if load_dotenv:
                load_dotenv()
                load_dotenv("email.env", override=False)

            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            db_host = os.getenv("DB_HOST")
            db_name = os.getenv("DB_NAME")
            db_port = os.getenv("DB_PORT", "3306")

            if not all([db_user, db_password, db_host, db_name]):
                log_warning("Error DB: variables de entorno no configuradas (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME)")
                return None

            conexion = mysql.connector.connect(
                user=db_user,
                password=db_password,
                host=db_host,
                database=db_name,
                port=db_port,
                connection_timeout=8,
                use_pure=True
            )
            return conexion
        except mysql.connector.Error as error:
            log_error(f"Error DB: {error}")
            return None
