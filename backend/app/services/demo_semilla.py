"""Datos de ejemplo de un sandbox de la demo (RF-J02).

Un kiosco verosimil: categorias, productos con precios en pesos,
proveedores, clientes y tres semanas de compras y ventas. Todo pasa por
los mismos servicios que usa la aplicacion, asi que el stock, los
movimientos y los reportes cuadran igual que en un comercio real.

Los nombres son genericos a proposito: ninguna marca, empresa ni persona
real. Los codigos de barra usan el prefijo 200, que GS1 reserva para uso
interno de cada comercio, asi que no coinciden con productos reales.
"""

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, select, update
from sqlalchemy.orm import Session

from app.core import tiempo
from app.models import (
    Categoria,
    Cliente,
    MedioPago,
    MovimientoStock,
    Producto,
    Proveedor,
    Rol,
    Usuario,
    Venta,
)
from app.services import clientes as servicio_clientes
from app.services import compras as servicio_compras
from app.services import medios_pago as servicio_medios
from app.services import productos as servicio_productos
from app.services import proveedores as servicio_proveedores
from app.services import ventas as servicio_ventas

# Mas de un mes: el reporte mensual queda lleno de dias con ventas, y
# la carga inicial del local cae fuera de el, asi el gasto en compras
# del mes muestra reposiciones y no el surtido completo del estante.
DIAS_DE_HISTORIA = 31
# Dias, contados hacia atras desde hoy, en que entra mercaderia. El
# primero es la carga inicial del local; despues, una vez por semana.
DIAS_DE_REPOSICION = (DIAS_DE_HISTORIA - 1, 21, 14, 7, 2)
CENTAVO = Decimal("0.01")

# Horarios del comercio, en su propia zona: abre de 8 a 21 y la
# mercaderia llega antes de abrir, asi el stock de cada movimiento sigue
# el orden del reloj.
HORA_DE_ENTREGA = time(8, 30)
APERTURA = time(9, 0)
CIERRE = time(20, 50)

# Quien cobra, en este orden: el mostrador lo atiende sobre todo la
# vendedora.
USUARIOS = (
    (Rol.PROPIETARIO, "Valeria (propietaria)"),
    (Rol.ENCARGADO, "Diego (encargado)"),
    (Rol.VENDEDOR, "Camila (vendedora)"),
)
PESOS_DE_CAJA = (10, 30, 60)

PESOS_DE_MEDIOS = {
    "Efectivo": 40,
    "Débito": 25,
    "QR": 15,
    "Transferencia": 12,
    "Crédito": 8,
}

CATEGORIAS = {
    "bebidas": ("Bebidas", "Gaseosas, aguas, jugos y energizantes."),
    "golosinas": ("Golosinas", "Alfajores, chocolates y caramelos."),
    "snacks": ("Snacks", "Papas, palitos y frutos secos."),
    "almacen": ("Almacén", "Productos secos de consumo diario."),
    "lacteos": ("Lácteos", "Refrigerados de vencimiento corto."),
    "panaderia": ("Panadería", "Pan y facturas del día."),
    "limpieza": ("Limpieza", "Artículos de limpieza del hogar."),
}

PROVEEDORES = {
    "bebidas": "Bebidas Río Sur Mayorista",
    "golosinas": "Golosinas del Centro",
    "almacen": "Distribuidora La Esquina",
    "lacteos": "Lácteos La Pradera",
    "panaderia": "Panificadora El Horno",
    "limpieza": "Limpieza Integral Mayorista",
}
# Rubros que no tienen proveedor propio.
PROVEEDOR_DEL_RUBRO = {"snacks": "golosinas"}

CLIENTES = (
    ("Lucía", "Fernández"),
    ("Martín", "Gómez"),
    ("Sofía", "Rodríguez"),
    ("Joaquín", "López"),
    ("Valentina", "Díaz"),
    ("Tomás", "Martínez"),
    ("Micaela", "Pérez"),
    ("Nicolás", "Romero"),
    ("Agustina", "Sosa"),
    ("Facundo", "Álvarez"),
    ("Florencia", "Torres"),
    ("Bruno", "Ruiz"),
)
LOCALIDADES = ("Rosario", "Funes", "Villa Gobernador Gálvez")


@dataclass(frozen=True)
class Articulo:
    """Un producto del catalogo de ejemplo."""

    rubro: str
    nombre: str
    precio: int
    stock: int
    minimo: int
    vence_en: int | None = None
    popularidad: int = 3
    # Los que no se reponen terminan por debajo del minimo: son los que
    # llenan las alertas del panel.
    reponer: bool = True


CATALOGO = (
    Articulo("bebidas", "Gaseosa cola 500 ml", 1500, 72, 24, popularidad=9),
    Articulo(
        "bebidas", "Gaseosa lima limón 500 ml", 1400, 48, 18, popularidad=5
    ),
    Articulo("bebidas", "Agua mineral 500 ml", 900, 60, 24, popularidad=8),
    Articulo("bebidas", "Agua saborizada 500 ml", 1200, 36, 12, popularidad=5),
    Articulo("bebidas", "Jugo en caja 1 L", 1800, 24, 8, vence_en=90),
    Articulo(
        "bebidas", "Bebida energizante 473 ml", 2600, 30, 10, popularidad=4
    ),
    Articulo(
        "golosinas", "Alfajor triple de chocolate", 1100, 80, 30, popularidad=9
    ),
    Articulo("golosinas", "Alfajor simple", 700, 60, 24, popularidad=6),
    Articulo(
        "golosinas", "Chocolate con leche 80 g", 2300, 25, 10, vence_en=120
    ),
    Articulo("golosinas", "Chicles de menta", 600, 40, 15, popularidad=5),
    Articulo("golosinas", "Barra de cereal", 800, 30, 12, popularidad=4),
    Articulo(
        "golosinas", "Turrón de maní", 500, 10, 15, popularidad=4, reponer=False
    ),
    Articulo("snacks", "Papas fritas 150 g", 2800, 24, 8, popularidad=5),
    Articulo("snacks", "Palitos salados 100 g", 1500, 20, 8),
    Articulo("snacks", "Maní salado 200 g", 1700, 18, 6),
    Articulo("almacen", "Yerba mate 500 g", 3200, 20, 8, popularidad=5),
    Articulo("almacen", "Azúcar 1 kg", 1500, 15, 6),
    Articulo("almacen", "Fideos secos 500 g", 1400, 18, 6),
    Articulo("almacen", "Arroz 1 kg", 1900, 12, 6, popularidad=2),
    Articulo(
        "almacen",
        "Aceite de girasol 900 ml",
        3000,
        7,
        6,
        popularidad=2,
        reponer=False,
    ),
    Articulo("almacen", "Galletitas de agua 250 g", 1300, 22, 8, popularidad=4),
    Articulo("almacen", "Galletitas dulces 300 g", 1600, 20, 8, popularidad=4),
    Articulo(
        "lacteos", "Leche entera 1 L", 1500, 30, 12, vence_en=6, popularidad=6
    ),
    Articulo("lacteos", "Yogur bebible 1 L", 2400, 14, 6, vence_en=4),
    Articulo(
        "lacteos",
        "Queso untable 290 g",
        2700,
        10,
        4,
        vence_en=12,
        popularidad=2,
    ),
    Articulo(
        "lacteos", "Manteca 200 g", 2600, 8, 4, vence_en=25, popularidad=2
    ),
    Articulo("panaderia", "Pan lactal", 2100, 12, 5, vence_en=3, popularidad=4),
    Articulo(
        "panaderia", "Medialunas x 6", 3000, 10, 4, vence_en=-1, popularidad=4
    ),
    Articulo(
        "panaderia", "Budín de vainilla", 1900, 9, 4, vence_en=15, popularidad=2
    ),
    Articulo("limpieza", "Lavandina 1 L", 1300, 14, 5, popularidad=2),
    Articulo("limpieza", "Detergente 500 ml", 1600, 12, 5, popularidad=2),
    Articulo(
        "limpieza",
        "Papel higiénico x 4",
        2900,
        8,
        6,
        popularidad=2,
        reponer=False,
    ),
    Articulo("limpieza", "Esponja de cocina", 800, 15, 5, popularidad=1),
)

Existencia = tuple[Articulo, Producto, Decimal]


def _momento(dia: date, hora: time) -> datetime:
    """Una hora del comercio de ese dia, expresada en UTC."""
    return datetime.combine(dia, hora, tzinfo=tiempo.zona()).astimezone(UTC)


def sembrar(db: Session, id_sesion_demo: str, rng: random.Random) -> Usuario:
    """Llena el sandbox y devuelve a su propietaria."""
    ahora = tiempo.ahora()
    hoy = tiempo.hoy()

    usuarios = _crear_usuarios(db, id_sesion_demo)
    cajeros = tuple(usuarios[rol] for rol, _ in USUARIOS)
    encargado = usuarios[Rol.ENCARGADO]

    medios = {
        medio.nombre: medio
        for medio in servicio_medios.sembrar_iniciales(db, id_sesion_demo)
    }
    categorias = {
        clave: servicio_productos.crear_categoria(
            db, nombre, descripcion, id_sesion_demo=id_sesion_demo
        )
        for clave, (nombre, descripcion) in CATEGORIAS.items()
    }
    proveedores = {
        clave: servicio_proveedores.crear(
            db, _datos_de_proveedor(razon_social), id_sesion_demo
        )
        for clave, razon_social in PROVEEDORES.items()
    }
    clientes = [
        servicio_clientes.crear(
            db, _datos_de_cliente(nombre, apellido, rng), id_sesion_demo
        )
        for nombre, apellido in CLIENTES
    ]
    existencias = _crear_productos(
        db, id_sesion_demo, rng, hoy, categorias, proveedores
    )

    for dias_atras in range(DIAS_DE_HISTORIA - 1, -1, -1):
        dia = hoy - timedelta(days=dias_atras)
        if dias_atras in DIAS_DE_REPOSICION:
            _reponer(
                db,
                id_sesion_demo,
                rng,
                dia,
                existencias,
                proveedores,
                encargado,
                inicial=dias_atras == DIAS_DE_HISTORIA - 1,
            )
        _vender_un_dia(
            db,
            id_sesion_demo,
            rng,
            dia,
            ahora,
            existencias,
            medios,
            clientes,
            cajeros,
        )

    _anular_una_venta(db, id_sesion_demo, rng, ahora, encargado)
    db.flush()
    return usuarios[Rol.PROPIETARIO]


# --- catalogo ------------------------------------------------------------


def _crear_usuarios(db: Session, id_sesion_demo: str) -> dict[Rol, Usuario]:
    """Una persona por rol, sin contrasena: a la demo se entra por token."""
    creados = {}
    for rol, nombre in USUARIOS:
        usuario = Usuario(
            email=f"{rol.value}@demo.stockarg.com.ar",
            nombre=nombre,
            rol=rol,
            password_hash=None,
            verificado=True,
            activo=True,
            id_sesion_demo=id_sesion_demo,
        )
        db.add(usuario)
        creados[rol] = usuario
    db.flush()
    return creados


def _datos_de_proveedor(razon_social: str) -> dict:
    return {
        "razon_social": razon_social,
        "cuit": None,
        "contacto": None,
        "telefono": None,
        "email": None,
        "direccion": None,
        "localidad": "Rosario",
        "notas": "Proveedor de ejemplo de la demo.",
    }


def _datos_de_cliente(nombre: str, apellido: str, rng: random.Random) -> dict:
    return {
        "nombre": nombre,
        "apellido": apellido,
        "documento": None,
        "cuit": None,
        "telefono": None,
        "email": None,
        "direccion": None,
        "localidad": rng.choice(LOCALIDADES),
        "notas": None,
    }


def _proveedor_de(rubro: str) -> str:
    return PROVEEDOR_DEL_RUBRO.get(rubro, rubro)


def _codigo_de_barras(rng: random.Random, indice: int) -> str:
    """EAN-13 valido con prefijo de uso interno."""
    cuerpo = f"200{rng.randrange(10**6):06d}{indice:03d}"
    suma = sum(
        int(digito) * (3 if posicion % 2 else 1)
        for posicion, digito in enumerate(cuerpo)
    )
    return cuerpo + str((10 - suma % 10) % 10)


def _redondear(valor: Decimal, paso: int = 10) -> Decimal:
    """Precio redondeado a la decena, como se ve en una gondola."""
    return (
        (valor / paso).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * paso
    ).quantize(CENTAVO)


def _crear_productos(
    db: Session,
    id_sesion_demo: str,
    rng: random.Random,
    hoy: date,
    categorias: dict[str, Categoria],
    proveedores: dict[str, Proveedor],
) -> list[Existencia]:
    """Alta del catalogo sin stock: todo lo que hay entra por compras."""
    existencias = []
    for indice, articulo in enumerate(CATALOGO, start=1):
        margen = Decimal(str(round(rng.uniform(0.58, 0.70), 3)))
        costo = _redondear(Decimal(articulo.precio) * margen)
        producto = servicio_productos.crear_producto(
            db,
            {
                "nombre": articulo.nombre,
                "codigo_barra": _codigo_de_barras(rng, indice),
                "descripcion": None,
                "precio_venta": Decimal(articulo.precio).quantize(CENTAVO),
                "precio_costo": costo,
                "stock_actual": 0,
                "stock_minimo": articulo.minimo,
                # La referencia del porcentaje es la carga inicial.
                "stock_inicial": articulo.stock,
                "fecha_vencimiento": (
                    hoy + timedelta(days=articulo.vence_en)
                    if articulo.vence_en is not None
                    else None
                ),
                "id_categoria": categorias[articulo.rubro].id,
                "id_proveedor": proveedores[_proveedor_de(articulo.rubro)].id,
            },
            id_sesion_demo=id_sesion_demo,
        )
        existencias.append((articulo, producto, costo))
    return existencias


# --- movimiento ----------------------------------------------------------


def _fechar_movimientos(
    db: Session, condicion: ColumnElement[bool], momento: datetime
) -> None:
    """Lleva al pasado los movimientos de una operacion retrofechada."""
    db.execute(
        update(MovimientoStock).where(condicion).values(fecha_hora=momento)
    )


def _reponer(
    db: Session,
    id_sesion_demo: str,
    rng: random.Random,
    dia: date,
    existencias: list[Existencia],
    proveedores: dict[str, Proveedor],
    usuario: Usuario,
    *,
    inicial: bool,
) -> None:
    """Una compra por proveedor con lo que hace falta ese dia."""
    pedidos: dict[str, list[servicio_compras.LineaComprada]] = {}
    for articulo, producto, costo in existencias:
        if inicial:
            cantidad = articulo.stock
            costo_del_dia = costo
        else:
            if not articulo.reponer:
                continue
            if producto.stock_actual >= articulo.minimo * 2:
                continue
            cantidad = max(
                articulo.stock - producto.stock_actual, articulo.minimo
            )
            # Cada reposicion llega un poco mas cara que la anterior.
            aumento = Decimal(str(round(rng.uniform(1.01, 1.05), 3)))
            costo_del_dia = _redondear(costo * aumento)
        pedidos.setdefault(_proveedor_de(articulo.rubro), []).append(
            servicio_compras.LineaComprada(
                id_producto=producto.id,
                cantidad=cantidad,
                costo_unitario=costo_del_dia,
            )
        )

    momento = _momento(dia, HORA_DE_ENTREGA)
    for clave, lineas in pedidos.items():
        compra = servicio_compras.registrar(
            db,
            lineas=lineas,
            id_proveedor=proveedores[clave].id,
            usuario=usuario,
            fecha=dia,
            comprobante=f"Remito 0001-{rng.randrange(10**8):08d}",
            actualizar_costo=True,
            id_sesion_demo=id_sesion_demo,
        )
        compra.registrada_en = momento
        _fechar_movimientos(db, MovimientoStock.id_compra == compra.id, momento)


def _vender_un_dia(
    db: Session,
    id_sesion_demo: str,
    rng: random.Random,
    dia: date,
    ahora: datetime,
    existencias: list[Existencia],
    medios: dict[str, MedioPago],
    clientes: list[Cliente],
    cajeros: tuple[Usuario, ...],
) -> None:
    """Las ventas de un dia, en orden de reloj."""
    apertura = _momento(dia, APERTURA)
    cierre = _momento(dia, CIERRE)
    # Mas movimiento de viernes a domingo.
    cantidad = rng.randint(5, 9) + (2 if dia.weekday() >= 4 else 0)

    if dia == tiempo.hoy():
        # Hoy solo hay ventas hasta hace un momento: ninguna en el futuro.
        jornada = cierre - apertura
        cierre = min(cierre, ahora - timedelta(minutes=2))
        if cierre <= apertura:
            return
        cantidad = max(1, round(cantidad * ((cierre - apertura) / jornada)))

    segundos = int((cierre - apertura).total_seconds())
    if segundos < 1:
        return
    momentos = sorted(
        apertura + timedelta(seconds=rng.randrange(segundos))
        for _ in range(cantidad)
    )
    for momento in momentos:
        _vender(
            db,
            id_sesion_demo,
            rng,
            momento,
            existencias,
            medios,
            clientes,
            cajeros,
        )


def _vender(
    db: Session,
    id_sesion_demo: str,
    rng: random.Random,
    momento: datetime,
    existencias: list[Existencia],
    medios: dict[str, MedioPago],
    clientes: list[Cliente],
    cajeros: tuple[Usuario, ...],
) -> None:
    """Un ticket con lo que suele llevarse la gente."""
    candidatos = [(a, p) for a, p, _ in existencias if p.stock_actual > 0]
    if not candidatos:
        return

    buscadas = min(
        len(candidatos), rng.choices((1, 2, 3, 4), weights=(45, 30, 17, 8))[0]
    )
    pesos = [articulo.popularidad for articulo, _ in candidatos]
    elegidos: dict[int, Producto] = {}
    for _ in range(buscadas * 4):
        if len(elegidos) == buscadas:
            break
        _, producto = rng.choices(candidatos, weights=pesos)[0]
        elegidos[producto.id] = producto

    lineas = []
    bruto = Decimal("0.00")
    for producto in elegidos.values():
        unidades = min(
            producto.stock_actual,
            rng.choices((1, 2, 3), weights=(75, 20, 5))[0],
        )
        lineas.append(
            servicio_ventas.LineaPedida(
                id_producto=producto.id, cantidad=unidades
            )
        )
        bruto += producto.precio_venta * unidades

    cajero = rng.choices(cajeros, weights=PESOS_DE_CAJA)[0]
    descuento = Decimal("0.00")
    if cajero.puede_gestionar and rng.random() < 0.1:
        descuento = (bruto * Decimal("0.05")).quantize(CENTAVO)
    total = bruto - descuento

    medio = medios[
        rng.choices(
            tuple(PESOS_DE_MEDIOS), weights=tuple(PESOS_DE_MEDIOS.values())
        )[0]
    ]
    recibido = None
    if medio.es_efectivo:
        # Se paga con billetes redondos y hay que dar vuelto.
        billete = Decimal(rng.choice((500, 1000, 2000)))
        recibido = (total / billete).to_integral_value(
            rounding=ROUND_CEILING
        ) * billete

    id_cliente = rng.choice(clientes).id if rng.random() < 0.25 else None

    try:
        venta = servicio_ventas.registrar(
            db,
            lineas=lineas,
            id_medio_pago=medio.id,
            usuario=cajero,
            id_cliente=id_cliente,
            recibido=recibido,
            descuento_general=descuento,
            id_sesion_demo=id_sesion_demo,
        )
    except servicio_ventas.StockInsuficiente:
        # No deberia pasar, porque se eligen productos con stock, pero
        # si pasa se saltea el ticket: la venta se rechaza antes de
        # escribir nada.
        return

    venta.fecha_hora = momento
    _fechar_movimientos(db, MovimientoStock.id_venta == venta.id, momento)


def _anular_una_venta(
    db: Session,
    id_sesion_demo: str,
    rng: random.Random,
    ahora: datetime,
    usuario: Usuario,
) -> None:
    """Un ticket anulado, para que el historial muestre ese caso."""
    db.flush()
    candidatas = db.scalars(
        select(Venta.id)
        .where(
            Venta.id_sesion_demo == id_sesion_demo,
            Venta.fecha_hora <= ahora - timedelta(days=3),
            Venta.fecha_hora >= ahora - timedelta(days=10),
        )
        .order_by(Venta.id)
    ).all()
    if not candidatas:
        return
    servicio_ventas.anular(
        db,
        rng.choice(candidatas),
        usuario,
        "Se cobro dos veces el mismo ticket.",
        id_sesion_demo=id_sesion_demo,
    )
