"""Acceso a datos y lógica de usuarios."""

from Conexion import cconexion
import bcrypt
from Utils import verificar_password
from Logger import log_error, log_warning


class Usuarios:

    @staticmethod
    def existe_usuario(email):
        """Devuelve True si el email ya existe."""
        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            log_warning("Usuarios.existe_usuario: sin conexión a DB")
            return False
        cursor = cone.cursor()
        cursor.execute(
            "SELECT id FROM usuarios_login WHERE email=%s",
            (email,)
        )
        existe = cursor.fetchone() is not None
        cone.close()
        return existe

    @staticmethod
    def registrar_verificado(email, password_hash):
        """Registra un usuario verificado con hash."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                log_warning("Usuarios.registrar_verificado: sin conexión a DB")
                return False
            cursor = cone.cursor()
            cursor.execute("""
                INSERT INTO usuarios_login (email, password, verificado)
                VALUES (%s, %s, 1)
            """, (email, password_hash))
            cone.commit()
            cone.close()
            return True
        except Exception as e:
            log_error(f"Usuarios.registrar_verificado: {e}")
            return False

    @staticmethod
    def registrar(email, password):
        """Registra usuario con password plano."""
        password_hash = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt()
        ).decode()
        return Usuarios.registrar_verificado(email, password_hash)

    @staticmethod
    def login(email, password):
        """Valida credenciales y retorna el usuario o None."""
        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            log_warning("Usuarios.login: sin conexión a DB")
            return None
        cursor = cone.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, email, password, verificado, es_admin
            FROM usuarios_login
            WHERE email=%s
        """, (email,))

        user = cursor.fetchone()
        cone.close()

        if not user:
            return None

        if user["password"] is None:
            return "GOOGLE_SIN_PASSWORD"

        if not verificar_password(password, user["password"]):
            return None

        return user

    @staticmethod
    def crear_password(email, password):
        """Crea/actualiza la contraseña para un email."""
        password_hash = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt()
        ).decode()

        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            log_warning("Usuarios.crear_password: sin conexión a DB")
            return False
        cursor = cone.cursor()
        cursor.execute("""
            UPDATE usuarios_login
            SET password=%s
            WHERE email=%s
        """, (password_hash, email))
        cone.commit()
        cone.close()
        return True
