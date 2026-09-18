"""Reglas de las cuentas: alta, verificacion, ingreso y contrasena."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    comparar_seguro,
    crear_token,
    generar_codigo_numerico,
    generar_token_urlsafe,
    hash_contrasena,
    hash_opaco,
    verificar_contrasena,
)
from app.models import CodigoUnico, Rol, TipoCodigo, Usuario

MINUTOS_CODIGO_VERIFICACION = 30
MINUTOS_TOKEN_RECUPERACION = 60
MAX_INTENTOS_POR_CODIGO = 5

# Mismo texto para correo inexistente y contrasena incorrecta: decir
# cual de las dos fallo confirma que cuentas existen.
CREDENCIALES_INCORRECTAS = "Usuario o contrasena incorrectos."


class ErrorDeAutenticacion(Exception):
    """Falla esperable de una operacion de cuentas."""

    def __init__(self, mensaje: str, codigo: str = "credenciales") -> None:
        """Guarda el mensaje visible y un codigo para el frontend."""
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class CuentaBloqueada(ErrorDeAutenticacion):
    """La cuenta esta bloqueada por intentos fallidos."""


def _normalizar_email(email: str) -> str:
    """Un correo es el mismo escrito en mayusculas o con espacios."""
    return email.strip().lower()


def _ahora() -> datetime:
    """Momento actual en UTC."""
    return datetime.now(UTC)


def _con_zona(momento: datetime | None) -> datetime | None:
    """Completa la zona horaria de una fecha leida de la base.

    SQLite la devuelve sin zona; se asume UTC, que es como se guardo.
    """
    if momento is None:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    """Usuario de la aplicacion con ese correo, si existe."""
    return db.scalars(
        select(Usuario).where(
            func.lower(Usuario.email) == _normalizar_email(email),
            Usuario.id_sesion_demo.is_(None),
        )
    ).first()


def _es_el_primer_usuario(db: Session) -> bool:
    """True si todavia no hay ninguna cuenta de la aplicacion.

    El primero que se registra queda como propietario: si todos nacieran
    vendedores, nadie podria administrar el sistema y no habria forma de
    promover a nadie.
    """
    total = db.scalar(
        select(func.count(Usuario.id)).where(Usuario.id_sesion_demo.is_(None))
    )
    return not total


# --- alta y verificacion (RF-A01) ---------------------------------------


def emitir_codigo(
    db: Session, email: str, tipo: TipoCodigo
) -> tuple[CodigoUnico, str]:
    """Genera un codigo, guarda su huella y devuelve el valor en claro.

    El valor en claro se devuelve para poder enviarlo por correo y nunca
    se guarda: en la base queda solo la huella.
    """
    email = _normalizar_email(email)
    ahora = _ahora()

    # Un codigo nuevo invalida los anteriores del mismo tipo: si no, un
    # codigo viejo interceptado seguiria sirviendo.
    for previo in db.scalars(
        select(CodigoUnico).where(
            CodigoUnico.email == email,
            CodigoUnico.tipo == tipo,
            CodigoUnico.usado.is_(False),
        )
    ):
        previo.usado = True

    if tipo is TipoCodigo.VERIFICACION:
        valor = generar_codigo_numerico()
        minutos = MINUTOS_CODIGO_VERIFICACION
    else:
        valor = generar_token_urlsafe()
        minutos = MINUTOS_TOKEN_RECUPERACION

    registro = CodigoUnico(
        email=email,
        codigo_hash=hash_opaco(valor),
        tipo=tipo,
        expira_en=ahora + timedelta(minutes=minutos),
        creado_en=ahora,
    )
    db.add(registro)
    db.flush()
    return registro, valor


def registrar(
    db: Session, email: str, nombre: str, contrasena: str
) -> tuple[Usuario, str]:
    """Crea una cuenta sin verificar y devuelve su codigo."""
    email = _normalizar_email(email)

    existente = buscar_por_email(db, email)
    if existente is not None:
        if existente.verificado:
            raise ErrorDeAutenticacion(
                "Ya existe una cuenta con ese correo.", "email_en_uso"
            )
        # Registro repetido sobre una cuenta sin verificar: se manda un
        # codigo nuevo y NO se toca nada de lo ya cargado.
        #
        # Pisar la contrasena aca abriria un pre-secuestro de cuenta:
        # un tercero que conoce un correo pendiente de verificar manda
        # un alta con la clave que el elige, y cuando la duena legitima
        # verifica con el codigo que le llega a su casilla, la cuenta
        # queda abierta con la clave del tercero. Quien de verdad se
        # olvido su contrasena antes de verificar tiene el flujo de
        # recuperacion, que exige llegar al correo.
        _, valor = emitir_codigo(db, email, TipoCodigo.VERIFICACION)
        db.flush()
        return existente, valor

    usuario = Usuario(
        email=email,
        nombre=nombre,
        password_hash=hash_contrasena(contrasena),
        rol=Rol.PROPIETARIO if _es_el_primer_usuario(db) else Rol.VENDEDOR,
        verificado=False,
        activo=True,
    )
    db.add(usuario)
    _, valor = emitir_codigo(db, email, TipoCodigo.VERIFICACION)
    db.flush()
    return usuario, valor


def _canjear_codigo(
    db: Session, email: str, valor: str, tipo: TipoCodigo
) -> CodigoUnico:
    """Valida un codigo y lo marca como usado."""
    email = _normalizar_email(email)
    registro = db.scalars(
        select(CodigoUnico)
        .where(
            CodigoUnico.email == email,
            CodigoUnico.tipo == tipo,
            CodigoUnico.usado.is_(False),
        )
        .order_by(CodigoUnico.id.desc())
    ).first()

    if registro is None or not registro.esta_vigente():
        raise ErrorDeAutenticacion(
            "El codigo es invalido o expiro.", "codigo_invalido"
        )

    registro.intentos += 1
    if registro.intentos > MAX_INTENTOS_POR_CODIGO:
        # Sin tope, un codigo de seis digitos se prueba entero.
        registro.usado = True
        db.flush()
        raise ErrorDeAutenticacion(
            "Demasiados intentos. Pida un codigo nuevo.", "codigo_agotado"
        )

    if not comparar_seguro(registro.codigo_hash, hash_opaco(valor)):
        db.flush()
        raise ErrorDeAutenticacion(
            "El codigo es invalido o expiro.", "codigo_invalido"
        )

    registro.usado = True
    db.flush()
    return registro


def verificar_email(db: Session, email: str, codigo: str) -> Usuario:
    """Marca la cuenta como verificada tras canjear el codigo."""
    usuario = buscar_por_email(db, email)
    if usuario is None:
        raise ErrorDeAutenticacion(
            "El codigo es invalido o expiro.", "codigo_invalido"
        )

    _canjear_codigo(db, email, codigo, TipoCodigo.VERIFICACION)
    usuario.verificado = True
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    db.flush()
    return usuario


# --- ingreso (RF-A02, RF-A05) -------------------------------------------


def _minutos_de_bloqueo_restantes(usuario: Usuario) -> int:
    """Minutos que faltan para que se levante el bloqueo."""
    hasta = _con_zona(usuario.bloqueado_hasta)
    if hasta is None:
        return 0
    restante = (hasta - _ahora()).total_seconds()
    return max(0, int(restante // 60) + 1) if restante > 0 else 0


def autenticar(db: Session, email: str, contrasena: str) -> Usuario:
    """Valida credenciales, aplicando el bloqueo por intentos."""
    ajustes = get_settings()
    usuario = buscar_por_email(db, email)

    if usuario is None:
        raise ErrorDeAutenticacion(CREDENCIALES_INCORRECTAS)

    minutos = _minutos_de_bloqueo_restantes(usuario)
    if minutos:
        raise CuentaBloqueada(
            f"Cuenta bloqueada. Reintente en {minutos} minutos.", "bloqueada"
        )

    if not verificar_contrasena(contrasena, usuario.password_hash):
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= ajustes.login_max_intentos:
            usuario.bloqueado_hasta = _ahora() + timedelta(
                minutes=ajustes.login_bloqueo_minutos
            )
        db.flush()
        raise ErrorDeAutenticacion(CREDENCIALES_INCORRECTAS)

    if not usuario.activo:
        # Se comprueba despues de la contrasena: responder antes
        # convertiria el endpoint en un detector de cuentas dadas de baja.
        raise ErrorDeAutenticacion(
            "La cuenta esta deshabilitada.", "deshabilitada"
        )

    if not usuario.verificado:
        raise ErrorDeAutenticacion(
            "La cuenta todavia no fue verificada.", "sin_verificar"
        )

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    db.flush()
    return usuario


def revocar_sesiones(usuario: Usuario) -> None:
    """Invalida todos los tokens emitidos hasta ahora para el usuario."""
    usuario.version_sesion = (usuario.version_sesion or 0) + 1


def emitir_token_de_sesion(usuario: Usuario) -> tuple[str, int]:
    """Token de acceso del usuario, con sus minutos de vigencia."""
    ajustes = get_settings()
    token = crear_token(
        str(usuario.id),
        tipo="acceso",
        rol=usuario.rol.value,
        email=usuario.email,
        sv=usuario.version_sesion or 0,
    )
    return token, ajustes.access_token_expire_minutes


# --- ingreso con Google (RF-A03) ----------------------------------------


def ingresar_con_google(db: Session, perfil: dict) -> Usuario:
    """Entra, o crea la cuenta, con un perfil de Google ya verificado.

    Google confirmo el correo, asi que la cuenta nace verificada y sin
    contrasena. Si ya existia una cuenta con ese correo, se la vincula:
    tener dos cuentas para la misma persona segun como haya entrado es
    la forma mas rapida de perder la mitad de su historial.
    """
    email = _normalizar_email(perfil["email"])
    identificador = str(perfil.get("sub") or "") or None
    usuario = buscar_por_email(db, email)

    if usuario is None:
        usuario = Usuario(
            email=email,
            nombre=(perfil.get("name") or email.split("@")[0])[:120],
            password_hash=None,
            google_id=identificador,
            rol=Rol.PROPIETARIO if _es_el_primer_usuario(db) else Rol.VENDEDOR,
            verificado=True,
            activo=True,
        )
        db.add(usuario)
        db.flush()
        return usuario

    if not usuario.activo:
        raise ErrorDeAutenticacion(
            "La cuenta esta deshabilitada.", "deshabilitada"
        )
    if (
        usuario.google_id
        and identificador
        and usuario.google_id != identificador
    ):
        # Mismo correo, otra cuenta de Google: no se toca nada.
        raise ErrorDeAutenticacion(CREDENCIALES_INCORRECTAS)

    if identificador and not usuario.google_id:
        usuario.google_id = identificador
    # Si la cuenta estaba pendiente de verificar, Google ya hizo esa
    # comprobacion.
    usuario.verificado = True
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    db.flush()
    return usuario


# --- contrasena (RF-A04, RF-A07) ----------------------------------------


def solicitar_recuperacion(db: Session, email: str) -> tuple[str, str] | None:
    """Emite un token de restablecimiento, si la cuenta existe.

    Devuelve None cuando no existe. Quien llama responde lo mismo en los
    dos casos: la respuesta no puede decir que correos estan registrados.
    """
    usuario = buscar_por_email(db, email)
    if usuario is None or not usuario.activo:
        return None
    _, valor = emitir_codigo(db, email, TipoCodigo.RECUPERACION)
    return usuario.email, valor


def restablecer_contrasena(
    db: Session, token: str, contrasena_nueva: str
) -> Usuario:
    """Fija una contrasena nueva canjeando el token del correo."""
    registro = db.scalars(
        select(CodigoUnico)
        .where(
            CodigoUnico.tipo == TipoCodigo.RECUPERACION,
            CodigoUnico.codigo_hash == hash_opaco(token),
            CodigoUnico.usado.is_(False),
        )
        .order_by(CodigoUnico.id.desc())
    ).first()

    if registro is None or not registro.esta_vigente():
        raise ErrorDeAutenticacion(
            "El enlace es invalido o expiro.", "token_invalido"
        )

    usuario = buscar_por_email(db, registro.email)
    if usuario is None:
        raise ErrorDeAutenticacion(
            "El enlace es invalido o expiro.", "token_invalido"
        )

    registro.usado = True
    usuario.password_hash = hash_contrasena(contrasena_nueva)
    # Quien recupera la clave suele sospechar que otro la conoce: toda
    # sesion abierta con la clave vieja deja de valer.
    revocar_sesiones(usuario)
    # Recuperar la clave tambien destraba la cuenta: quien llego al
    # correo demostro ser su duena.
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.verificado = True
    db.flush()
    return usuario


def cambiar_contrasena(
    db: Session, usuario: Usuario, actual: str, nueva: str
) -> Usuario:
    """Cambia la contrasena desde el perfil, pidiendo la anterior."""
    if usuario.password_hash and not verificar_contrasena(
        actual, usuario.password_hash
    ):
        raise ErrorDeAutenticacion(
            "La contrasena actual no es correcta.", "credenciales"
        )
    usuario.password_hash = hash_contrasena(nueva)
    # Cierra las demas sesiones; quien la cambio recibe un token nuevo.
    revocar_sesiones(usuario)
    db.flush()
    return usuario
