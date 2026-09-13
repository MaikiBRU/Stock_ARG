"""Reglas de productos y categorias (modulo C)."""

from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    BajaProducto,
    Categoria,
    CompraItem,
    MovimientoStock,
    Producto,
    Proveedor,
    VentaItem,
)


class ErrorDeProducto(Exception):
    """Falla esperable al operar con productos o categorias."""

    def __init__(self, mensaje: str, codigo: str = "invalido") -> None:
        """Guarda el mensaje visible y un codigo para el frontend."""
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class NoEncontrado(ErrorDeProducto):
    """El registro pedido no existe en esta particion de datos."""


def _limpiar(valor: str | None) -> str | None:
    """Normaliza un texto opcional."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


# --- categorias (RF-C03) -------------------------------------------------


def _base_categorias(id_sesion_demo: str | None) -> Select:
    """Consulta de categorias acotada a su particion."""
    return select(Categoria).where(
        Categoria.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Categoria.id_sesion_demo == id_sesion_demo
    )


def listar_categorias(
    db: Session,
    id_sesion_demo: str | None = None,
    incluir_inactivas: bool = False,
) -> list[Categoria]:
    """Categorias de la particion, ordenadas por nombre."""
    consulta = _base_categorias(id_sesion_demo)
    if not incluir_inactivas:
        consulta = consulta.where(Categoria.activo.is_(True))
    return list(db.scalars(consulta.order_by(Categoria.nombre)))


def obtener_categoria(
    db: Session, id_categoria: int, id_sesion_demo: str | None = None
) -> Categoria:
    """Una categoria de la particion, o error si no esta."""
    categoria = db.scalars(
        _base_categorias(id_sesion_demo).where(Categoria.id == id_categoria)
    ).first()
    if categoria is None:
        # 404 y no 403: responder distinto confirmaria que el id existe
        # en otra particion.
        raise NoEncontrado("No existe la categoria.", "no_encontrado")
    return categoria


def _nombre_de_categoria_libre(
    db: Session,
    nombre: str,
    id_sesion_demo: str | None,
    excluir: int | None = None,
) -> None:
    """Comprueba que el nombre no este tomado en la particion."""
    consulta = _base_categorias(id_sesion_demo).where(
        func.lower(Categoria.nombre) == nombre.lower()
    )
    if excluir is not None:
        consulta = consulta.where(Categoria.id != excluir)
    if db.scalars(consulta).first() is not None:
        raise ErrorDeProducto(
            f'Ya existe una categoria llamada "{nombre}".', "nombre_en_uso"
        )


def crear_categoria(
    db: Session,
    nombre: str,
    descripcion: str | None = None,
    id_sesion_demo: str | None = None,
) -> Categoria:
    """Alta de categoria."""
    _nombre_de_categoria_libre(db, nombre, id_sesion_demo)
    categoria = Categoria(
        nombre=nombre,
        descripcion=_limpiar(descripcion),
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(categoria)
    db.flush()
    return categoria


def actualizar_categoria(
    db: Session,
    id_categoria: int,
    nombre: str,
    descripcion: str | None = None,
    id_sesion_demo: str | None = None,
) -> Categoria:
    """Edicion de categoria."""
    categoria = obtener_categoria(db, id_categoria, id_sesion_demo)
    _nombre_de_categoria_libre(db, nombre, id_sesion_demo, excluir=id_categoria)
    categoria.nombre = nombre
    categoria.descripcion = _limpiar(descripcion)
    db.flush()
    return categoria


def desactivar_categoria(
    db: Session, id_categoria: int, id_sesion_demo: str | None = None
) -> Categoria:
    """Baja logica de una categoria.

    Los productos que la usaban no se tocan: la relacion es opcional y
    quitarles la categoria cambiaria datos que nadie pidio cambiar.
    """
    categoria = obtener_categoria(db, id_categoria, id_sesion_demo)
    categoria.activo = False
    db.flush()
    return categoria


# --- productos (RF-C01 a RF-C09) -----------------------------------------


def _base_productos(id_sesion_demo: str | None) -> Select:
    """Consulta de productos acotada a su particion."""
    return select(Producto).where(
        Producto.id_sesion_demo.is_(None)
        if id_sesion_demo is None
        else Producto.id_sesion_demo == id_sesion_demo
    )


def obtener_producto(
    db: Session, id_producto: int, id_sesion_demo: str | None = None
) -> Producto:
    """Un producto de la particion, o error si no esta."""
    producto = db.scalars(
        _base_productos(id_sesion_demo).where(Producto.id == id_producto)
    ).first()
    if producto is None:
        raise NoEncontrado("No existe el producto.", "no_encontrado")
    return producto


def buscar_por_codigo(
    db: Session, codigo: str, id_sesion_demo: str | None = None
) -> Producto:
    """Producto activo con ese codigo de barras (RF-E02)."""
    producto = db.scalars(
        _base_productos(id_sesion_demo).where(
            Producto.codigo_barra == codigo.strip(),
            Producto.activo.is_(True),
        )
    ).first()
    if producto is None:
        raise NoEncontrado(
            "No hay ningun producto con ese codigo.", "no_encontrado"
        )
    return producto


def listar_productos(
    db: Session,
    *,
    id_sesion_demo: str | None = None,
    busqueda: str | None = None,
    id_categoria: int | None = None,
    solo_bajo_minimo: bool = False,
    incluir_inactivos: bool = False,
    desplazamiento: int = 0,
    limite: int = 25,
    orden: str = "nombre",
) -> tuple[list[Producto], int]:
    """Listado filtrado y paginado (RF-C08).

    Devuelve la pagina y el total de coincidencias, para que el frontend
    sepa cuantas paginas hay sin traerse la tabla entera.
    """
    consulta = _base_productos(id_sesion_demo)

    if not incluir_inactivos:
        consulta = consulta.where(Producto.activo.is_(True))

    if busqueda:
        patron = f"%{busqueda.strip().lower()}%"
        consulta = consulta.where(
            or_(
                func.lower(Producto.nombre).like(patron),
                func.lower(Producto.codigo_barra).like(patron),
            )
        )

    if id_categoria is not None:
        consulta = consulta.where(Producto.id_categoria == id_categoria)

    if solo_bajo_minimo:
        consulta = consulta.where(
            Producto.stock_actual <= Producto.stock_minimo
        )

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))

    columnas = {
        "nombre": Producto.nombre,
        "precio": Producto.precio_venta,
        "stock": Producto.stock_actual,
    }
    columna = columnas.get(orden, Producto.nombre)

    pagina = db.scalars(
        consulta.order_by(columna, Producto.id)
        .offset(desplazamiento)
        .limit(limite)
    ).all()

    return list(pagina), total or 0


def _codigo_libre(
    db: Session,
    codigo: str | None,
    id_sesion_demo: str | None,
    excluir: int | None = None,
) -> None:
    """Comprueba que el codigo de barras no este tomado (RF-C02).

    La base ya lo impide con un indice unico parcial. Esto existe para
    dar un mensaje que nombre al producto que lo esta usando, en lugar
    de dejar que salga un error de integridad.
    """
    if not codigo:
        return
    consulta = _base_productos(id_sesion_demo).where(
        Producto.codigo_barra == codigo
    )
    if excluir is not None:
        consulta = consulta.where(Producto.id != excluir)
    otro = db.scalars(consulta).first()
    if otro is not None:
        raise ErrorDeProducto(
            f'El codigo {codigo} ya lo usa "{otro.nombre}".',
            "codigo_en_uso",
        )


def _validar_relaciones(
    db: Session,
    id_categoria: int | None,
    id_proveedor: int | None,
    id_sesion_demo: str | None,
) -> None:
    """Comprueba que categoria y proveedor existan en la particion.

    Sin esto, un pedido podria apuntar a una categoria de otro sandbox y
    la clave foranea lo dejaria pasar, porque el id existe en la tabla.
    """
    if id_categoria is not None:
        obtener_categoria(db, id_categoria, id_sesion_demo)

    if id_proveedor is not None:
        proveedor = db.scalars(
            select(Proveedor).where(
                Proveedor.id == id_proveedor,
                Proveedor.id_sesion_demo.is_(None)
                if id_sesion_demo is None
                else Proveedor.id_sesion_demo == id_sesion_demo,
            )
        ).first()
        if proveedor is None:
            raise NoEncontrado("No existe el proveedor.", "no_encontrado")


def crear_producto(
    db: Session,
    datos: dict,
    id_sesion_demo: str | None = None,
) -> Producto:
    """Alta de producto (RF-C01)."""
    codigo = _limpiar(datos.get("codigo_barra"))
    _codigo_libre(db, codigo, id_sesion_demo)
    _validar_relaciones(
        db,
        datos.get("id_categoria"),
        datos.get("id_proveedor"),
        id_sesion_demo,
    )

    stock_actual = datos.get("stock_actual", 0)
    # Sin stock inicial declarado se toma el de carga: es la referencia
    # contra la que el panel calcula el porcentaje.
    stock_inicial = datos.get("stock_inicial")
    if stock_inicial is None:
        stock_inicial = stock_actual

    producto = Producto(
        nombre=datos["nombre"],
        codigo_barra=codigo,
        descripcion=_limpiar(datos.get("descripcion")),
        precio_venta=datos.get("precio_venta", Decimal("0.00")),
        precio_costo=datos.get("precio_costo", Decimal("0.00")),
        stock_actual=stock_actual,
        stock_minimo=datos.get("stock_minimo", 0),
        stock_inicial=stock_inicial,
        fecha_vencimiento=datos.get("fecha_vencimiento"),
        id_categoria=datos.get("id_categoria"),
        id_proveedor=datos.get("id_proveedor"),
        activo=True,
        id_sesion_demo=id_sesion_demo,
    )
    db.add(producto)
    db.flush()
    return producto


def actualizar_producto(
    db: Session,
    id_producto: int,
    datos: dict,
    id_sesion_demo: str | None = None,
) -> Producto:
    """Edicion de producto (RF-C01).

    El stock no se toca aca: se mueve por los caminos del modulo D, que
    dejan traza. Si la edicion pudiera fijarlo, el historial dejaria de
    explicar de donde salio el numero.
    """
    producto = obtener_producto(db, id_producto, id_sesion_demo)
    codigo = _limpiar(datos.get("codigo_barra"))
    _codigo_libre(db, codigo, id_sesion_demo, excluir=id_producto)
    _validar_relaciones(
        db,
        datos.get("id_categoria"),
        datos.get("id_proveedor"),
        id_sesion_demo,
    )

    producto.nombre = datos["nombre"]
    producto.codigo_barra = codigo
    producto.descripcion = _limpiar(datos.get("descripcion"))
    producto.precio_venta = datos.get("precio_venta", producto.precio_venta)
    producto.precio_costo = datos.get("precio_costo", producto.precio_costo)
    producto.stock_minimo = datos.get("stock_minimo", producto.stock_minimo)
    if datos.get("stock_inicial") is not None:
        producto.stock_inicial = datos["stock_inicial"]
    producto.fecha_vencimiento = datos.get("fecha_vencimiento")
    producto.id_categoria = datos.get("id_categoria")
    producto.id_proveedor = datos.get("id_proveedor")
    db.flush()
    return producto


def tiene_historial(db: Session, id_producto: int) -> bool:
    """True si el producto aparece en ventas, compras o movimientos."""
    for modelo in (VentaItem, CompraItem, MovimientoStock, BajaProducto):
        existe = db.scalars(
            select(modelo.id).where(modelo.id_producto == id_producto).limit(1)
        ).first()
        if existe is not None:
            return True
    return False


def eliminar_producto(
    db: Session, id_producto: int, id_sesion_demo: str | None = None
) -> tuple[Producto, bool]:
    """Da de baja un producto (RF-C09).

    Con historial se desactiva y nada mas: borrarlo se llevaria por
    delante las ventas y los movimientos que lo mencionan, que es
    justamente lo que hacia la version de escritorio. Sin historial, el
    borrado fisico es seguro y deja la tabla limpia.

    Devuelve el producto y si se borro de verdad.
    """
    producto = obtener_producto(db, id_producto, id_sesion_demo)

    if tiene_historial(db, id_producto):
        producto.activo = False
        db.flush()
        return producto, False

    db.delete(producto)
    db.flush()
    return producto, True


def reactivar_producto(
    db: Session, id_producto: int, id_sesion_demo: str | None = None
) -> Producto:
    """Vuelve a poner en circulacion un producto dado de baja."""
    producto = obtener_producto(db, id_producto, id_sesion_demo)
    producto.activo = True
    db.flush()
    return producto
