"""Endpoints de cuentas (modulo A)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import ip_del_cliente, obtener_usuario_actual, rechazar_demo
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import TipoCodigo, Usuario
from app.schemas.auth import (
    CambioContrasenaEntrada,
    LoginEntrada,
    MensajeSalida,
    PerfilEntrada,
    RecuperacionEntrada,
    ReenvioEntrada,
    RegistroEntrada,
    RestablecerEntrada,
    TokenSalida,
    UsuarioSalida,
    VerificacionEntrada,
)
from app.services import auth as servicio
from app.services import correo
from app.services.limites import clave_de_ip, limitador

router = APIRouter(prefix="/auth", tags=["cuentas"])

# Respuesta unica para el alta y la recuperacion: sale igual exista o no
# la cuenta, para que nadie pueda usar estos endpoints como buscador de
# correos registrados.
AVISO_CORREO_ENVIADO = (
    "Si el correo corresponde a una cuenta, va a recibir un mensaje."
)

DEMASIADOS_INTENTOS = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Demasiados intentos. Espere unos minutos.",
)


def _limitar(request: Request, accion: str, maximo: int, ventana: int) -> None:
    """Aplica el limite por IP o corta la peticion."""
    clave = clave_de_ip(ip_del_cliente(request), accion)
    if not limitador.permitido(clave, maximo, ventana):
        raise DEMASIADOS_INTENTOS


@router.post(
    "/registro",
    response_model=MensajeSalida,
    status_code=status.HTTP_201_CREATED,
)
def registro(
    datos: RegistroEntrada,
    request: Request,
    db: Session = Depends(get_db),
    ajustes: Settings = Depends(get_settings),
) -> MensajeSalida:
    """Crea una cuenta y envia el codigo de verificacion (RF-A01)."""
    _limitar(
        request,
        "registro",
        ajustes.login_max_intentos_por_ip,
        ajustes.login_ventana_ip_segundos,
    )

    try:
        _, codigo = servicio.registrar(
            db, datos.email, datos.nombre, datos.contrasena
        )
    except servicio.ErrorDeAutenticacion:
        # Un correo ya registrado devuelve el mismo texto que uno nuevo.
        # Sin esto, el formulario de alta enumera cuentas.
        db.rollback()
        return MensajeSalida(mensaje=AVISO_CORREO_ENVIADO)

    try:
        correo.enviar_codigo_de_verificacion(datos.email, codigo)
    except correo.ErrorDeEnvio as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo enviar el correo. Intente mas tarde.",
        ) from error

    db.commit()
    return MensajeSalida(mensaje=AVISO_CORREO_ENVIADO)


@router.post("/verificar", response_model=TokenSalida)
def verificar(
    datos: VerificacionEntrada,
    request: Request,
    db: Session = Depends(get_db),
    ajustes: Settings = Depends(get_settings),
) -> TokenSalida:
    """Canjea el codigo y deja la sesion iniciada (RF-A01)."""
    _limitar(
        request,
        "verificar",
        ajustes.login_max_intentos_por_ip,
        ajustes.login_ventana_ip_segundos,
    )

    try:
        usuario = servicio.verificar_email(db, datos.email, datos.codigo)
    except servicio.ErrorDeAutenticacion as error:
        db.commit()  # conserva el conteo de intentos del codigo
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.mensaje
        ) from error

    token, minutos = servicio.emitir_token_de_sesion(usuario)
    db.commit()
    return TokenSalida(
        access_token=token,
        expira_en_minutos=minutos,
        usuario=UsuarioSalida.model_validate(usuario),
    )


@router.post("/reenviar", response_model=MensajeSalida)
def reenviar(
    datos: ReenvioEntrada,
    request: Request,
    db: Session = Depends(get_db),
    ajustes: Settings = Depends(get_settings),
) -> MensajeSalida:
    """Manda un codigo nuevo a una cuenta sin verificar."""
    _limitar(request, "reenviar", 5, ajustes.login_ventana_ip_segundos)

    usuario = servicio.buscar_por_email(db, datos.email)
    if usuario is not None and not usuario.verificado:
        _, codigo = servicio.emitir_codigo(
            db, datos.email, TipoCodigo.VERIFICACION
        )
        try:
            correo.enviar_codigo_de_verificacion(datos.email, codigo)
            db.commit()
        except correo.ErrorDeEnvio:
            db.rollback()

    return MensajeSalida(mensaje=AVISO_CORREO_ENVIADO)


@router.post("/login", response_model=TokenSalida)
def login(
    datos: LoginEntrada,
    request: Request,
    db: Session = Depends(get_db),
    ajustes: Settings = Depends(get_settings),
) -> TokenSalida:
    """Inicia sesion (RF-A02, RF-A05)."""
    _limitar(
        request,
        "login",
        ajustes.login_max_intentos_por_ip,
        ajustes.login_ventana_ip_segundos,
    )

    try:
        usuario = servicio.autenticar(db, datos.email, datos.contrasena)
    except servicio.CuentaBloqueada as error:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error.mensaje,
        ) from error
    except servicio.ErrorDeAutenticacion as error:
        db.commit()  # conserva el conteo de intentos fallidos
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=error.mensaje
        ) from error

    token, minutos = servicio.emitir_token_de_sesion(usuario)
    db.commit()
    return TokenSalida(
        access_token=token,
        expira_en_minutos=minutos,
        usuario=UsuarioSalida.model_validate(usuario),
    )


@router.post("/recuperar", response_model=MensajeSalida)
def recuperar(
    datos: RecuperacionEntrada,
    request: Request,
    db: Session = Depends(get_db),
) -> MensajeSalida:
    """Envia el enlace para elegir una contrasena nueva (RF-A04)."""
    _limitar(request, "recuperar", 5, 3600)

    resultado = servicio.solicitar_recuperacion(db, datos.email)
    if resultado is not None:
        destinatario, token = resultado
        try:
            correo.enviar_enlace_de_recuperacion(destinatario, token)
            db.commit()
        except correo.ErrorDeEnvio:
            db.rollback()

    return MensajeSalida(mensaje=AVISO_CORREO_ENVIADO)


@router.post("/restablecer", response_model=MensajeSalida)
def restablecer(
    datos: RestablecerEntrada,
    request: Request,
    db: Session = Depends(get_db),
) -> MensajeSalida:
    """Fija la contrasena nueva con el token del correo (RF-A04)."""
    _limitar(request, "restablecer", 10, 3600)

    try:
        servicio.restablecer_contrasena(db, datos.token, datos.contrasena)
    except servicio.ErrorDeAutenticacion as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.mensaje
        ) from error

    db.commit()
    return MensajeSalida(mensaje="La contrasena se actualizo.")


@router.get("/perfil", response_model=UsuarioSalida)
def perfil(
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> UsuarioSalida:
    """Datos de la sesion en curso."""
    return UsuarioSalida.model_validate(usuario)


@router.put("/perfil", response_model=UsuarioSalida)
def editar_perfil(
    datos: PerfilEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> UsuarioSalida:
    """Cambia el nombre propio (RF-A07)."""
    usuario.nombre = datos.nombre
    db.commit()
    return UsuarioSalida.model_validate(usuario)


@router.put("/contrasena", response_model=TokenSalida)
def cambiar_contrasena(
    datos: CambioContrasenaEntrada,
    db: Session = Depends(get_db),
    # Los usuarios de la demo no tienen contrasena y a un sandbox se
    # entra por token: ponerle una no sirve para nada.
    usuario: Usuario = Depends(rechazar_demo),
) -> TokenSalida:
    """Cambia la propia contrasena, pidiendo la anterior (RF-A07).

    Cierra toda otra sesion abierta y devuelve un token nuevo para que
    quien hizo el cambio siga adentro.
    """
    try:
        servicio.cambiar_contrasena(
            db, usuario, datos.contrasena_actual, datos.contrasena_nueva
        )
    except servicio.ErrorDeAutenticacion as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.mensaje
        ) from error

    token, minutos = servicio.emitir_token_de_sesion(usuario)
    db.commit()
    return TokenSalida(
        access_token=token,
        expira_en_minutos=minutos,
        usuario=UsuarioSalida.model_validate(usuario),
    )


@router.post("/logout", response_model=MensajeSalida)
def logout(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> MensajeSalida:
    """Cierra la sesion de verdad (RF-A06).

    No alcanza con que el navegador borre el token: si alguien lo copio,
    seguiria entrando hasta que venciera solo. Se sube la version de
    sesion del usuario y todo token emitido con la anterior queda sin
    valor, en esta sesion y en cualquier otra que tuviera abierta.
    """
    servicio.revocar_sesiones(usuario)
    db.commit()
    return MensajeSalida(mensaje="La sesion se cerro.")
