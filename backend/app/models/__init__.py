"""Modelos de dominio de StockARG.

Se importan todos aca para que Alembic vea el metadata completo al
autogenerar migraciones.
"""

from app.models.auditoria import Auditoria
from app.models.catalogo import Categoria, Cliente, MedioPago, Proveedor
from app.models.compra import Compra, CompraItem
from app.models.demo_session import SesionDemo
from app.models.inventario import (
    BajaProducto,
    MotivoBaja,
    MovimientoStock,
    TipoMovimiento,
)
from app.models.producto import Producto
from app.models.usuario import Rol, Usuario
from app.models.venta import EstadoVenta, Venta, VentaItem

__all__ = [
    "Auditoria",
    "BajaProducto",
    "Categoria",
    "Cliente",
    "Compra",
    "CompraItem",
    "EstadoVenta",
    "MedioPago",
    "MotivoBaja",
    "MovimientoStock",
    "Producto",
    "Proveedor",
    "Rol",
    "SesionDemo",
    "TipoMovimiento",
    "Usuario",
    "Venta",
    "VentaItem",
]
