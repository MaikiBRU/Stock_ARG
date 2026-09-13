"""Usuarios y configuracion del comercio (modulo I)."""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core import ajustes_vivos
from app.core.security import hash_contrasena
from app.models import Configuracion, Rol, Usuario
from app.services.productos import ErrorDeProducto, NoEncontrado

# Parametros que la pantalla de configuracion puede tocar, con su valor
# de partida. Cualquier clave fuera de esta lista se rechaza: si no, la
# tabla se llena de claves sueltas que nadie lee.
CLAVES = {
    "nombre_comercio": "Mi comercio",
    "dias_aviso_vencimiento": "30",
    "stock_umbral_bajo": "30",
    "stock_umbral_medio": "54",
    "descuento_max_vendedor": "10",
}
NUMERICAS = {
    "dias_aviso_vencimiento": (1, 365),
    "stock_umbral_bajo": (0, 99),
    "stock_umbral_medio": (1, 100),
    "descuento_max_vendedor": (0, 100),
}


# --- usuarios (RF-I01 a RF-I03) ------------------------------------------


def _base_usuarios(id_sesion_demo: str | None) -> Select:
    """Usuarios de la particion."""
    return select(Usuario).where(
        Usuario.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Usuario.id_sesion_demo == id_sesion_demo
    )


def obtener_usuario(
    db: Session, id_usuario: int, id_sesion_demo: str | None = None
) -> Usuario:
    """Un usuario de la particion, o error si no esta."""
    usuario = db.scalars(
        _base_usuarios(id_sesion_demo).where(Usuario.id == id_usuario)
    ).first()
    if usuario is None:
        raise NoEncontrado("No existe el usuario.", "no_encontrado")
    return usuario


def listar_usuarios(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    incluir_inactivos: bool = True,
    desplazamiento: int = 0,
    limite: int = 25,
) -> tuple[list[Usuario], int]:
    """Listado de usuarios (RF-I01)."""
    consulta = _base_usuarios(id_sesion_demo)
    if not incluir_inactivos:
        consulta = consulta.where(Usuario.activo.is_(True))

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    pagina = db.scalars(
        consulta.order_by(Usuario.nombre, Usuario.id)
        .offset(desplazamiento)
        .limit(limite)
    ).all()
    return list(pagina), total or 0


def _propietarios_activos(
    db: Session, id_sesion_demo: str | None, excluir: int | None = None
) -> int:
    """Cuantos propietarios activos quedan, sin contar a uno dado."""
    consulta = _base_usuarios(id_sesion_demo).where(
        Usuario.rol == Rol.PROPIETARIO, Usuario.activo.is_(True)
    )
    if excluir is not None:
        consulta = consulta.where(Usuario.id != excluir)
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    return total or 0


def crear_usuario(
    db: Session,
    *,
    email: str,
    nombre: str,
    contrasena: str,
    rol: Rol,
    id_sesion_demo: str | None = None,
) -> Usuario:
    """Alta de usuario desde la administracion (RF-I01).

    Nace verificado: lo crea alguien que ya entro al sistema, asi que no
    hace falta comprobar que el correo existe para habilitarlo.
    """
    email = email.strip().lower()
    existente = db.scalars(
        _base_usuarios(id_sesion_demo).where(func.lower(Usuario.email) == email)
    ).first()
    if existente is not None:
        raise ErrorDeProducto(
            "Ya existe una cuenta con ese correo.", "email_en_uso"
        )

    usuario = Usuario(
        email=email,
        nombre=nombre.strip(),
        password_hash=hash_contrasena(contrasena),
        rol=rol,
        verificado=True,
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(usuario)
    db.flush()
    return usuario


def cambiar_rol(
    db: Session,
    id_usuario: int,
    rol: Rol,
    *,
    id_sesion_demo: str | None = None,
) -> Usuario:
    """Cambia el rol de un usuario (RF-I01)."""
    usuario = obtener_usuario(db, id_usuario, id_sesion_demo)

    if (
        usuario.rol is Rol.PROPIETARIO
        and rol is not Rol.PROPIETARIO
        and not _propietarios_activos(db, id_sesion_demo, excluir=id_usuario)
    ):
        # RF-I03. Sin ningun propietario nadie puede administrar usuarios
        # ni configuracion, y el sistema queda trabado sin salida.
        raise ErrorDeProducto(
            "Es el unico propietario activo. Promueva a otro antes de "
            "cambiarle el rol.",
            "ultimo_propietario",
        )

    usuario.rol = rol
    db.flush()
    return usuario


def cambiar_estado(
    db: Session,
    id_usuario: int,
    activo: bool,
    *,
    ejecutor: Usuario,
    id_sesion_demo: str | None = None,
) -> Usuario:
    """Habilita o deshabilita una cuenta (RF-I02, RF-I03).

    Nunca se borra: sus ventas y movimientos tienen que seguir diciendo
    quien los hizo.
    """
    usuario = obtener_usuario(db, id_usuario, id_sesion_demo)

    if not activo:
        if usuario.id == ejecutor.id:
            # Darse de baja a si mismo cierra la sesion en el acto y, si
            # era el unico propietario, deja el sistema sin administrador.
            raise ErrorDeProducto(
                "No puede darse de baja a si mismo.", "auto_baja"
            )
        if usuario.rol is Rol.PROPIETARIO and not _propietarios_activos(
            db, id_sesion_demo, excluir=id_usuario
        ):
            raise ErrorDeProducto(
                "Es el unico propietario activo. Promueva a otro antes de "
                "darlo de baja.",
                "ultimo_propietario",
            )

    usuario.activo = activo
    if activo:
        # Reactivar destraba: si quedo bloqueada por intentos fallidos,
        # volver a habilitarla sin limpiar el bloqueo no serviria.
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
    db.flush()
    return usuario


# --- configuracion (RF-I06) ----------------------------------------------


def _base_config(id_sesion_demo: str | None) -> Select:
    """Configuracion de la particion."""
    return select(Configuracion).where(
        Configuracion.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Configuracion.id_sesion_demo == id_sesion_demo
    )


def leer_configuracion(
    db: Session, id_sesion_demo: str | None = None
) -> dict[str, str]:
    """Todos los parametros, con sus valores de partida si faltan."""
    guardados = {
        fila.clave: fila.valor
        for fila in db.scalars(_base_config(id_sesion_demo))
    }
    return {
        clave: guardados.get(clave, valor) for clave, valor in CLAVES.items()
    }


def _validar(clave: str, valor: str) -> str:
    """Comprueba que el valor sirva para esa clave."""
    if clave not in CLAVES:
        admitidas = ", ".join(sorted(CLAVES))
        raise ErrorDeProducto(
            f'"{clave}" no es un parametro configurable. '
            f"Admitidos: {admitidas}.",
            "clave_desconocida",
        )

    valor = valor.strip()
    if not valor:
        raise ErrorDeProducto(
            f'"{clave}" no puede quedar vacio.', "valor_vacio"
        )

    if clave in NUMERICAS:
        minimo, maximo = NUMERICAS[clave]
        try:
            numero = int(valor)
        except ValueError as error:
            raise ErrorDeProducto(
                f'"{clave}" tiene que ser un numero entero.', "valor_invalido"
            ) from error
        if not minimo <= numero <= maximo:
            raise ErrorDeProducto(
                f'"{clave}" tiene que estar entre {minimo} y {maximo}.',
                "valor_fuera_de_rango",
            )
    return valor


def guardar_configuracion(
    db: Session,
    cambios: dict[str, str],
    id_sesion_demo: str | None = None,
) -> dict[str, str]:
    """Guarda los parametros que se pasen (RF-I06)."""
    limpios = {
        clave: _validar(clave, valor) for clave, valor in cambios.items()
    }

    # Los umbrales se validan juntos: por separado, cada uno puede ser
    # valido y la pareja quedar invertida, que es lo que deja un estado
    # de stock inalcanzable.
    final = leer_configuracion(db, id_sesion_demo) | limpios
    bajo = int(final["stock_umbral_bajo"])
    medio = int(final["stock_umbral_medio"])
    if bajo >= medio:
        raise ErrorDeProducto(
            "El umbral bajo tiene que ser menor que el medio.",
            "umbrales_invertidos",
        )

    existentes = {
        fila.clave: fila for fila in db.scalars(_base_config(id_sesion_demo))
    }
    for clave, valor in limpios.items():
        fila = existentes.get(clave)
        if fila is None:
            db.add(
                Configuracion(
                    clave=clave, valor=valor, id_sesion_demo=id_sesion_demo
                )
            )
        else:
            fila.valor = valor

    db.flush()

    vigentes = leer_configuracion(db, id_sesion_demo)
    ajustes_vivos.fijar(vigentes)
    return vigentes
