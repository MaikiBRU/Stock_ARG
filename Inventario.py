"""Operaciones de movimientos de stock."""

from Conexion import cconexion
from Logger import log_error, log_info


def registrar_movimiento(producto_id, tipo, cantidad, nota=None, aplicar_stock=True):
    """
    Registra un movimiento de stock.
    - tipo: entrada | salida | ajuste | devolucion | venta
    - cantidad: int (>= 0)
    - aplicar_stock: si True, actualiza productos.cantidad
    """
    try:
        try:
            cantidad = int(cantidad)
        except Exception:
            return False, "Cantidad invalida"
        if cantidad < 0:
            return False, "Cantidad invalida"
        tipo = str(tipo or "").strip().lower()

        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            return False, "No hay conexion a la base de datos"
        cursor = cone.cursor()

        if aplicar_stock:
            cursor.execute("SELECT cantidad FROM productos WHERE id=%s", (producto_id,))
            row = cursor.fetchone()
            if not row:
                cone.close()
                return False, "Producto no existe"
            actual = int(row[0])

            if tipo in ("entrada", "devolucion"):
                nuevo = actual + cantidad
            elif tipo in ("salida", "venta"):
                if actual < cantidad:
                    cone.close()
                    return False, "Stock insuficiente"
                nuevo = actual - cantidad
            elif tipo == "ajuste":
                nuevo = cantidad
            else:
                cone.close()
                return False, "Tipo invalido"

            cursor.execute("UPDATE productos SET cantidad=%s WHERE id=%s", (nuevo, producto_id))

        cursor.execute(
            """
            INSERT INTO movimientos_stock (producto_id, tipo, cantidad, nota)
            VALUES (%s, %s, %s, %s)
            """,
            (producto_id, tipo, cantidad, nota)
        )
        cone.commit()
        cone.close()
        log_info(f"Inventario.movimiento: {tipo} producto={producto_id} cant={cantidad}")
        return True, None
    except Exception as exc:
        log_error(f"Inventario.registrar_movimiento: {exc}")
        return False, "No se pudo registrar el movimiento"
