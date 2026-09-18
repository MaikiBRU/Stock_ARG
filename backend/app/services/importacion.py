"""Importacion masiva de productos desde CSV (RF-C10).

La importacion tiene dos pasos: primero se previsualiza y se devuelve,
fila por fila, que va a pasar y que esta mal; recien despues se confirma.
Asi nadie descubre que cargo mal doscientos precios cuando ya estan
guardados.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Categoria, Cliente, Producto, Proveedor, Usuario
from app.services import productos as servicio_productos

COLUMNAS_CONOCIDAS = {
    "nombre",
    "codigo_barra",
    "descripcion",
    "precio_venta",
    "precio_costo",
    "stock_actual",
    "stock_minimo",
    "categoria",
    "fecha_vencimiento",
}
COLUMNAS_REQUERIDAS = {"nombre", "precio_venta"}

# Formatos de fecha que puede escribir una planilla local.
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y")


@dataclass
class FilaAnalizada:
    """Que se hizo, o se haria, con una fila del archivo."""

    numero: int
    accion: str  # "crear", "actualizar" o "error"
    nombre: str | None = None
    codigo_barra: str | None = None
    errores: list[str] = field(default_factory=list)
    datos: dict = field(default_factory=dict)


@dataclass
class ResultadoImportacion:
    """Resumen de una previsualizacion o de una importacion aplicada."""

    filas: list[FilaAnalizada]
    a_crear: int
    a_actualizar: int
    con_error: int
    aplicada: bool = False


def _decimal(valor: str, campo: str, errores: list[str]) -> Decimal | None:
    """Convierte un importe escrito a mano.

    Acepta las dos convenciones que aparecen en la practica: "1200.50" y
    "1.200,50". Rechazar la segunda obligaria a reformatear el archivo
    exportado de Excel, que es justamente lo que se quiere evitar.
    """
    texto = (valor or "").strip()
    if not texto:
        return None

    limpio = texto.replace("$", "").replace(" ", "")
    if "," in limpio:
        # Coma decimal: el punto separa miles.
        limpio = limpio.replace(".", "").replace(",", ".")

    try:
        numero = Decimal(limpio)
    except InvalidOperation:
        errores.append(f"{campo}: no se entiende el importe '{texto}'.")
        return None

    if numero < 0:
        errores.append(f"{campo}: no puede ser negativo.")
        return None
    return numero.quantize(Decimal("0.01"))


def _entero(valor: str, campo: str, errores: list[str]) -> int | None:
    """Convierte una cantidad entera."""
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        numero = int(Decimal(texto.replace(".", "").replace(",", ".")))
    except (InvalidOperation, ValueError):
        errores.append(f"{campo}: no se entiende la cantidad '{texto}'.")
        return None
    if numero < 0:
        errores.append(f"{campo}: no puede ser negativo.")
        return None
    return numero


def _fecha(valor: str, campo: str, errores: list[str]) -> date | None:
    """Convierte una fecha escrita en cualquiera de los formatos usuales."""
    texto = (valor or "").strip()
    if not texto:
        return None
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    errores.append(
        f"{campo}: no se entiende la fecha '{texto}'. "
        "Use AAAA-MM-DD o DD/MM/AAAA."
    )
    return None


def columnas_faltantes(encabezados: list[str]) -> set[str]:
    """Columnas obligatorias que el archivo no trae."""
    return COLUMNAS_REQUERIDAS - set(encabezados)


def _categoria_por_nombre(
    db: Session, nombre: str, id_sesion_demo: str | None
) -> Categoria | None:
    """Busca una categoria por nombre dentro de la particion."""
    return db.scalars(
        select(Categoria).where(
            func.lower(Categoria.nombre) == nombre.strip().lower(),
            Categoria.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Categoria.id_sesion_demo == id_sesion_demo,
        )
    ).first()


def _producto_por_codigo(
    db: Session, codigo: str, id_sesion_demo: str | None
) -> Producto | None:
    """Busca un producto por codigo de barras dentro de la particion."""
    return db.scalars(
        select(Producto).where(
            Producto.codigo_barra == codigo,
            Producto.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else Producto.id_sesion_demo == id_sesion_demo,
        )
    ).first()


def analizar(
    db: Session,
    filas: list[dict[str, str]],
    *,
    id_sesion_demo: str | None = None,
    crear_categorias: bool = False,
) -> ResultadoImportacion:
    """Revisa el archivo sin escribir nada (RF-C10).

    Cuando una fila trae un codigo de barras que ya existe, la accion es
    actualizar: importar una lista de precios es el caso normal, y
    rechazarla por duplicado obligaria a borrar todo antes de cargar.
    """
    analizadas: list[FilaAnalizada] = []
    codigos_vistos: dict[str, int] = {}

    for indice, fila in enumerate(filas, start=2):  # la 1 es el encabezado
        errores: list[str] = []

        nombre = (fila.get("nombre") or "").strip()
        if not nombre:
            errores.append("nombre: es obligatorio.")

        codigo = (fila.get("codigo_barra") or "").strip() or None

        # Dos filas del mismo archivo con el mismo codigo se pisarian
        # entre si sin que nadie se entere.
        if codigo and codigo in codigos_vistos:
            errores.append(
                f"codigo_barra: repetido, ya aparece en la fila "
                f"{codigos_vistos[codigo]}."
            )
        elif codigo:
            codigos_vistos[codigo] = indice

        precio_venta = _decimal(
            fila.get("precio_venta", ""), "precio_venta", errores
        )
        if precio_venta is None and not any(
            e.startswith("precio_venta") for e in errores
        ):
            errores.append("precio_venta: es obligatorio.")

        precio_costo = _decimal(
            fila.get("precio_costo", ""), "precio_costo", errores
        )
        stock_actual = _entero(
            fila.get("stock_actual", ""), "stock_actual", errores
        )
        stock_minimo = _entero(
            fila.get("stock_minimo", ""), "stock_minimo", errores
        )
        vencimiento = _fecha(
            fila.get("fecha_vencimiento", ""), "fecha_vencimiento", errores
        )

        id_categoria = None
        nombre_categoria = (fila.get("categoria") or "").strip()
        if nombre_categoria:
            categoria = _categoria_por_nombre(
                db, nombre_categoria, id_sesion_demo
            )
            if categoria is not None:
                id_categoria = categoria.id
            elif not crear_categorias:
                errores.append(
                    f"categoria: '{nombre_categoria}' no existe. "
                    "Crearla primero o pedir que se creen solas."
                )

        existente = (
            _producto_por_codigo(db, codigo, id_sesion_demo) if codigo else None
        )

        if errores:
            accion = "error"
        elif existente is not None:
            accion = "actualizar"
        else:
            accion = "crear"

        analizadas.append(
            FilaAnalizada(
                numero=indice,
                accion=accion,
                nombre=nombre or None,
                codigo_barra=codigo,
                errores=errores,
                datos={
                    "nombre": nombre,
                    "codigo_barra": codigo,
                    "descripcion": (fila.get("descripcion") or "").strip()
                    or None,
                    "precio_venta": precio_venta,
                    "precio_costo": precio_costo,
                    "stock_actual": stock_actual,
                    "stock_minimo": stock_minimo,
                    "fecha_vencimiento": vencimiento,
                    "id_categoria": id_categoria,
                    "nombre_categoria": nombre_categoria or None,
                    "id_existente": existente.id if existente else None,
                },
            )
        )

    return ResultadoImportacion(
        filas=analizadas,
        a_crear=sum(1 for f in analizadas if f.accion == "crear"),
        a_actualizar=sum(1 for f in analizadas if f.accion == "actualizar"),
        con_error=sum(1 for f in analizadas if f.accion == "error"),
    )


def aplicar(
    db: Session,
    filas: list[dict[str, str]],
    usuario: Usuario,
    *,
    id_sesion_demo: str | None = None,
    crear_categorias: bool = False,
) -> ResultadoImportacion:
    """Importa las filas validas y saltea las que tienen errores.

    Las filas con error no detienen la carga: el resultado dice cuales
    quedaron afuera y por que, que es mas util que rechazar el archivo
    entero por una celda mal escrita.
    """
    if crear_categorias:
        # Se crean antes de analizar, asi el analisis ya las encuentra y
        # no las reporta como faltantes.
        nombres = {
            (fila.get("categoria") or "").strip()
            for fila in filas
            if (fila.get("categoria") or "").strip()
        }
        for nombre in sorted(nombres):
            if _categoria_por_nombre(db, nombre, id_sesion_demo) is None:
                servicio_productos.crear_categoria(
                    db, nombre, id_sesion_demo=id_sesion_demo
                )
        db.flush()

    resultado = analizar(
        db,
        filas,
        id_sesion_demo=id_sesion_demo,
        crear_categorias=crear_categorias,
    )

    for fila in resultado.filas:
        if fila.accion == "error":
            continue

        datos = dict(fila.datos)
        id_existente = datos.pop("id_existente")
        datos.pop("nombre_categoria", None)

        # Los campos vacios del CSV no deben pisar lo que ya esta
        # cargado: se quitan del pedido en lugar de mandar None.
        limpios = {
            clave: valor for clave, valor in datos.items() if valor is not None
        }

        if id_existente is not None:
            existente = db.get(Producto, id_existente)
            # El stock no se toca en una importacion: se mueve por el
            # modulo D, que deja traza de cada cambio.
            limpios.pop("stock_actual", None)
            if existente is not None:
                # El precio es obligatorio al actualizar: si el archivo
                # no lo trae, se conserva el que ya tenia.
                limpios.setdefault("precio_venta", existente.precio_venta)
            servicio_productos.actualizar_producto(
                db, id_existente, limpios, id_sesion_demo
            )
        else:
            servicio_productos.crear_producto(db, limpios, id_sesion_demo)

    resultado.aplicada = True
    return resultado


# --- contactos: clientes y proveedores (RF-F05, RF-G05) ------------------
#
# Clientes y proveedores comparten la forma del problema: una columna de
# nombre obligatoria, un identificador unico opcional que decide si la
# fila crea o actualiza, y varios datos de contacto. Se resuelve una vez
# y se parametriza, en lugar de escribir dos veces el mismo recorrido.

CAMPOS_CLIENTE = (
    "nombre",
    "apellido",
    "documento",
    "cuit",
    "telefono",
    "email",
    "direccion",
    "localidad",
    "notas",
)
CAMPOS_PROVEEDOR = (
    "razon_social",
    "cuit",
    "contacto",
    "telefono",
    "email",
    "direccion",
    "localidad",
    "notas",
)


def _perfil(tipo: str) -> dict:
    """Devuelve como se lee un archivo de clientes o de proveedores."""
    if tipo == "cliente":
        return {
            "campos": CAMPOS_CLIENTE,
            "obligatorio": "nombre",
            "clave": "documento",
            "modelo": Cliente,
        }
    return {
        "campos": CAMPOS_PROVEEDOR,
        "obligatorio": "razon_social",
        "clave": "cuit",
        "modelo": Proveedor,
    }


def columnas_faltantes_contacto(encabezados: list[str], tipo: str) -> set[str]:
    """Columna obligatoria que el archivo no trae."""
    return {_perfil(tipo)["obligatorio"]} - set(encabezados)


def _existente_por_clave(
    db: Session, modelo, columna: str, valor: str, id_sesion_demo: str | None
):
    """Busca un contacto por su identificador unico, en la particion."""
    return db.scalars(
        select(modelo).where(
            getattr(modelo, columna) == valor,
            modelo.id_sesion_demo.is_(None)
            if id_sesion_demo is None
            else modelo.id_sesion_demo == id_sesion_demo,
        )
    ).first()


def analizar_contactos(
    db: Session,
    filas: list[dict[str, str]],
    tipo: str,
    *,
    id_sesion_demo: str | None = None,
) -> ResultadoImportacion:
    """Revisa un archivo de clientes o proveedores sin escribir nada."""
    perfil = _perfil(tipo)
    obligatorio = perfil["obligatorio"]
    clave = perfil["clave"]

    analizadas: list[FilaAnalizada] = []
    claves_vistas: dict[str, int] = {}

    for indice, fila in enumerate(filas, start=2):
        errores: list[str] = []

        principal = (fila.get(obligatorio) or "").strip()
        if not principal:
            errores.append(f"{obligatorio}: es obligatorio.")

        identificador = (fila.get(clave) or "").strip() or None
        if identificador and identificador in claves_vistas:
            errores.append(
                f"{clave}: repetido, ya aparece en la fila "
                f"{claves_vistas[identificador]}."
            )
        elif identificador:
            claves_vistas[identificador] = indice

        correo = (fila.get("email") or "").strip()
        if correo and "@" not in correo:
            errores.append(f"email: '{correo}' no parece un correo.")

        existente = (
            _existente_por_clave(
                db, perfil["modelo"], clave, identificador, id_sesion_demo
            )
            if identificador
            else None
        )

        if errores:
            accion = "error"
        elif existente is not None:
            accion = "actualizar"
        else:
            accion = "crear"

        datos = {
            campo: (fila.get(campo) or "").strip() or None
            for campo in perfil["campos"]
        }
        datos[obligatorio] = principal
        datos["id_existente"] = existente.id if existente else None

        analizadas.append(
            FilaAnalizada(
                numero=indice,
                accion=accion,
                nombre=principal or None,
                codigo_barra=identificador,
                errores=errores,
                datos=datos,
            )
        )

    return ResultadoImportacion(
        filas=analizadas,
        a_crear=sum(1 for f in analizadas if f.accion == "crear"),
        a_actualizar=sum(1 for f in analizadas if f.accion == "actualizar"),
        con_error=sum(1 for f in analizadas if f.accion == "error"),
    )


def aplicar_contactos(
    db: Session,
    filas: list[dict[str, str]],
    tipo: str,
    *,
    id_sesion_demo: str | None = None,
) -> ResultadoImportacion:
    """Importa clientes o proveedores, salteando las filas con error."""
    from app.services import clientes as servicio_clientes
    from app.services import proveedores as servicio_proveedores

    servicio = servicio_clientes if tipo == "cliente" else servicio_proveedores
    resultado = analizar_contactos(
        db, filas, tipo, id_sesion_demo=id_sesion_demo
    )

    for fila in resultado.filas:
        if fila.accion == "error":
            continue

        datos = dict(fila.datos)
        id_existente = datos.pop("id_existente")

        if id_existente is not None:
            servicio.actualizar(db, id_existente, datos, id_sesion_demo)
        else:
            servicio.crear(db, datos, id_sesion_demo)

    resultado.aplicada = True
    return resultado
