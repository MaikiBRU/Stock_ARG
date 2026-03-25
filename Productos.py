"""Módulo de productos: datos y UI."""

from Conexion import cconexion
import mysql.connector


class Productos:
    @staticmethod
    def mostrarProductos(filtro=None):
        """Obtiene lista de productos."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return []
            cursor = cone.cursor()
            sql = """
                SELECT id, nombre, precio, cantidad, stock_inicial,
                       DATE_FORMAT(fecha_ingreso, '%d/%m/%Y %H:%i') AS fecha_ingreso
                FROM productos
            """
            params = None
            if filtro:
                sql += " WHERE id LIKE %s OR nombre LIKE %s"
                like = f"%{filtro}%"
                params = (like, like)
            sql += ";"
            cursor.execute(sql, params or ())
            miResultado = cursor.fetchall()
            cone.commit()
            cone.close()
            return miResultado
        except mysql.connector.Error as error:
            log_error(f"Productos.mostrarProductos: {error}")
            return []

    def existeProducto(idProducto):
        """Valida si un producto ya existe por ID."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False
            cursor = cone.cursor()
            cursor.execute("SELECT 1 FROM productos WHERE id=%s", (idProducto,))
            existe = cursor.fetchone() is not None
            cone.close()
            return existe
        except mysql.connector.Error as error:
            log_error(f"Productos.existeProducto: {error}")
            return False

    def ingresarProductos(idProductos, nombresProductos, precioProductos, cantidad):
        """Inserta un producto en la base."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            sql = """
            INSERT INTO productos (id, nombre, precio, cantidad, stock_inicial, fecha_ingreso)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """
            valores = (idProductos, nombresProductos, precioProductos, cantidad, cantidad)
            cursor.execute(sql, valores)
            cone.commit()
            log_info(f"Productos.ingresarProductos: {cursor.rowcount} registro(s)")
            cone.close()
            return True, None
        except mysql.connector.Error as error:
            log_error(f"Productos.ingresarProductos: {error}")
            return False, "Error al guardar el producto"

    def modificarProductos(idProductos, nombresProductos, precioProductos, cantidad):
        """Actualiza un producto existente."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            sql = """
            UPDATE productos
            SET nombre=%s, precio=%s, cantidad=%s
            WHERE id=%s;
            """
            valores = (nombresProductos, precioProductos, cantidad, idProductos)
            cursor.execute(sql, valores)
            cone.commit()
            log_info(f"Productos.modificarProductos: {cursor.rowcount} registro(s)")
            cone.close()
            return True, None
        except mysql.connector.Error as error:
            log_error(f"Productos.modificarProductos: {error}")
            return False, "Error al actualizar el producto"

    def eliminarProductos(idProductos):
        """Elimina un producto por ID."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            sql = "DELETE from productos WHERE productos.id=%s;"
            valores = (idProductos,)
            cursor.execute(sql, valores)
            cone.commit()
            log_info(f"Productos.eliminarProductos: {cursor.rowcount} registro(s)")
            cone.close()
            return True, None
        except mysql.connector.Error as error:
            log_error(f"Productos.eliminarProductos: {error}")
            return False, "Error al eliminar el producto"


import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
from Theme import (
    BG_MAIN,
    BG_CARD,
    BG_INPUT,
    BG_BUTTON,
    BG_BUTTON_HOVER,
    ACCENT,
    ACCENT_HOVER,
    FG_TEXT,
    FG_MUTED,
    BORDER,
    FONT_LABEL,
    FONT_INPUT,
    FONT_BUTTON,
    FONT_SUBTITLE,
    dark_button,
    apply_chrome,
    apply_ttk_style,
)
from Dialogs import dialog_info, dialog_error
from Utils import (
    campos_requeridos,
    parse_int,
    parse_float,
    validar_id,
    exportar_treeview_csv,
    exportar_treeview_pdf,
    configurar_orden_treeview,
    treeview_set_empty,
    run_with_loading,
    schedule_autorefresh,
    importar_csv,
    widget_alive,
    register_activity,
)
from Logger import log_error, log_info


class FormularioProductos:
    global texboxIdproductos
    texboxIdproductos = None

    global texboxNombreproductos
    texboxNombreproductos = None

    global texboxPrecioproductos
    texboxPrecioproductos = None

    global texboxCantidadProductos
    texboxCantidadProductos = None

    global base
    base = None

    global tree
    tree = None

    global lbl_total_productos
    lbl_total_productos = None

    global lbl_stock_total
    lbl_stock_total = None


def productos_panel(parent):
    """Construye el panel de productos dentro de un contenedor."""
    global texboxIdproductos
    global texboxNombreproductos
    global texboxPrecioproductos
    global texboxCantidadProductos
    global tree
    global base
    global lbl_total_productos
    global lbl_stock_total

    base = parent.winfo_toplevel()

    content = tk.Frame(parent, bg=BG_MAIN)
    content.pack(fill="both", expand=True)
    content.grid_columnconfigure(0, weight=0)
    content.grid_columnconfigure(1, weight=1)
    content.grid_rowconfigure(0, weight=1)
    content.grid_rowconfigure(1, weight=1)

    groupbox = LabelFrame(
        content,
        text="Datos de los Productos",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    groupbox.grid(row=0, column=0, padx=16, pady=16, sticky="n")

    texboxIdproductos_label = Label(groupbox, text="Id Producto:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxIdproductos_label.grid(row=0, column=0, sticky="w", pady=4)
    texboxIdproductos = Entry(
        groupbox,
        bg=BG_INPUT,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT,
        readonlybackground=BG_INPUT,
        disabledforeground=FG_TEXT
    )
    texboxIdproductos.grid(row=0, column=1, pady=4, ipadx=6, ipady=4)

    texboxNombreproductos_label = Label(groupbox, text="Nombre:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxNombreproductos_label.grid(row=1, column=0, sticky="w", pady=4)
    texboxNombreproductos = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxNombreproductos.grid(row=1, column=1, pady=4, ipadx=6, ipady=4)

    texboxPrecioproductos_label = Label(groupbox, text="Precio ($):", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxPrecioproductos_label.grid(row=2, column=0, sticky="w", pady=4)
    texboxPrecioproductos = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxPrecioproductos.grid(row=2, column=1, pady=4, ipadx=6, ipady=4)

    texboxCantidad_label = Label(groupbox, text="Cantidad:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxCantidad_label.grid(row=3, column=0, sticky="w", pady=4)
    texboxCantidadProductos = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxCantidadProductos.grid(row=3, column=1, pady=4, ipadx=6, ipady=4)

    btn_row = tk.Frame(groupbox, bg=BG_CARD)
    btn_row.grid(row=5, column=0, columnspan=2, pady=(10, 0))


    def _limpiar_form():
        texboxIdproductos.config(state="normal")
        texboxIdproductos.delete(0, END)
        texboxNombreproductos.delete(0, END)
        texboxPrecioproductos.delete(0, END)
        texboxCantidadProductos.delete(0, END)
        _update_buttons()

    btn_guardar = dark_button(btn_row, "Guardar", guardarRegistros, primary=True)
    btn_guardar.grid(row=0, column=0, padx=6, ipady=4, ipadx=8)
    btn_editar = dark_button(btn_row, "Editar", modificarRegistros)
    btn_editar.grid(row=0, column=1, padx=6, ipady=4, ipadx=8)
    btn_eliminar = dark_button(btn_row, "Eliminar", eliminarRegistros)
    btn_eliminar.grid(row=0, column=2, padx=6, ipady=4, ipadx=8)
    btn_limpiar = dark_button(btn_row, "Limpiar", lambda: _limpiar_form())
    btn_limpiar.grid(row=0, column=3, padx=6, ipady=4, ipadx=8)

    def _set_guardar_state(enabled):
        if enabled:
            btn_guardar.config(state="normal", fg=FG_TEXT, bg=ACCENT, activebackground=ACCENT_HOVER)
            btn_guardar._bg = ACCENT
            btn_guardar._hover = ACCENT_HOVER
        else:
            btn_guardar.config(state="disabled", fg=FG_MUTED, bg=BG_BUTTON, activebackground=BG_BUTTON_HOVER)
            btn_guardar._bg = BG_BUTTON
            btn_guardar._hover = BG_BUTTON_HOVER

    def _update_buttons():
        try:
            id_txt = texboxIdproductos.get().strip()
            nombre_txt = texboxNombreproductos.get().strip()
            precio_txt = texboxPrecioproductos.get().strip()
            cant_txt = texboxCantidadProductos.get().strip()
            is_selected = texboxIdproductos.cget("state") == "readonly"
            required_ok = all([id_txt, nombre_txt, precio_txt, cant_txt])
            _set_guardar_state((not is_selected and required_ok))
            btn_editar.config(state="normal" if (is_selected and required_ok) else "disabled")
            btn_eliminar.config(state="normal" if (is_selected and id_txt) else "disabled")
        except Exception:
            pass

    for w in (texboxIdproductos, texboxNombreproductos, texboxPrecioproductos, texboxCantidadProductos):
        w.bind("<KeyRelease>", lambda e: _update_buttons())

    groupbox = LabelFrame(
        content,
        text="Lista de Productos",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    groupbox.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")

    summary_row = tk.Frame(groupbox, bg=BG_CARD)
    summary_row.pack(fill="x", pady=(0, 8))
    lbl_total_productos = tk.Label(summary_row, text="Productos: 0", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    lbl_total_productos.pack(side="left", padx=(0, 12))
    lbl_stock_total = tk.Label(summary_row, text="Stock total: 0", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    lbl_stock_total.pack(side="left")

    search_row = tk.Frame(groupbox, bg=BG_CARD)
    search_row.pack(fill="x", pady=(0, 8))
    tk.Label(search_row, text="Buscar:", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE).pack(side="left")
    search_entry = tk.Entry(search_row, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    search_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=2)

    spacer_right = tk.Frame(content, bg=BG_MAIN)
    spacer_right.grid(row=1, column=1, padx=16, pady=(0, 16), sticky="nsew")

    tree_wrap = tk.Frame(groupbox, bg=BG_CARD)
    tree_wrap.pack(fill="both", expand=True)
    tree_wrap.grid_columnconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(1, weight=0)

    tree = ttk.Treeview(
        tree_wrap,
        columns=("id", "nombre", "precio", "cantidad", "fecha"),
        show="headings",
        height=14,
        style="Dark.Treeview"
    )
    tree.column("id", anchor=CENTER, width=80, stretch=True)
    tree.heading("id", text="Id Producto", anchor=tk.CENTER)
    tree.column("nombre", anchor=CENTER, width=200, stretch=True)
    tree.heading("nombre", text="Nombre", anchor=tk.CENTER)
    tree.column("precio", anchor=CENTER, width=120, stretch=True)
    tree.heading("precio", text="Precio ($)", anchor=tk.CENTER)
    tree.column("cantidad", anchor=CENTER, width=90, stretch=True)
    tree.heading("cantidad", text="Cantidad", anchor=tk.CENTER)
    tree.column("fecha", anchor=CENTER, width=180, minwidth=180, stretch=True)
    tree.heading("fecha", text="Fecha ingreso", anchor=tk.CENTER)
    tree.tag_configure("empty", foreground=FG_MUTED)
    configurar_orden_treeview(tree, numeric_cols={"id", "precio", "cantidad"})

    tree.bind("<<TreeviewSelect>>", seleccionarRegistro)
    scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview, style="Dark.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")
    headers = ["Id Producto", "Nombre", "Precio", "Cantidad", "Fecha ingreso"]
    dark_button(search_row, "Exportar CSV", lambda: exportar_treeview_csv(tree, headers, "productos")).pack(side="right")
    def _export_pdf():
        ok, msg = exportar_treeview_pdf(tree, headers, "Reporte de Productos", "productos")
        if not ok and msg and msg != "Cancelado":
            dialog_error(base, "Error", msg)
    dark_button(search_row, "Exportar PDF", _export_pdf).pack(side="right", padx=6)
    def _import_csv():
        def _work():
            rows = importar_csv()
            if not rows:
                return
            inserted = skipped = 0
            errors = []
            for idx, row in enumerate(rows, start=1):
                if not row or len(row) < 4:
                    skipped += 1
                    errors.append(f"Fila {idx}: columnas insuficientes")
                    continue
                if row[0].lower().startswith("id"):
                    continue
                prod_id, nombre, precio, cantidad = row[0], row[1], row[2], row[3]
                if Productos.existeProducto(prod_id):
                    skipped += 1
                    errors.append(f"Fila {idx}: id duplicado")
                    continue
                cantidad_int = parse_int(cantidad, min_value=0, allow_zero=True)
                precio_val = parse_float(precio, min_value=0, allow_zero=False)
                if cantidad_int is None or precio_val is None:
                    skipped += 1
                    errors.append(f"Fila {idx}: datos invalidos")
                    continue
                ok, msg = Productos.ingresarProductos(prod_id, nombre, precio_val, cantidad_int)
                if ok:
                    inserted += 1
                else:
                    skipped += 1
                    errors.append(f"Fila {idx}: {msg or 'error'}")
            actualizarTreeView()
            if errors:
                resumen = "\\n".join(errors[:5])
                dialog_info(base, "Informacion", f"Importados: {inserted} | Omitidos: {skipped}\\n{resumen}")
            else:
                dialog_info(base, "Informacion", f"Importados: {inserted} | Omitidos: {skipped}")
        run_with_loading(base, "Importando...", _work)
    dark_button(search_row, "Importar CSV", _import_csv).pack(side="right", padx=6)

    def _do_search():
        actualizarTreeView(search_entry.get().strip())

    def _clear_search():
        search_entry.delete(0, END)
        actualizarTreeView()

    dark_button(search_row, "Buscar", _do_search).pack(side="left", padx=4)
    dark_button(search_row, "Limpiar", _clear_search).pack(side="left")
    search_entry.bind("<Return>", lambda e: _do_search())
    def _focus_search(_=None):
        try:
            if search_entry.winfo_exists():
                search_entry.focus_set()
        except Exception:
            pass
        return "break"
    base.bind("<Control-f>", _focus_search)
    base.bind("<Control-F>", _focus_search)
    actualizarTreeView()
    _update_buttons()

    def _auto_refresh():
        try:
            filtro = search_entry.get().strip()
        except Exception:
            filtro = None
        actualizarTreeView(filtro, silent=True)

    schedule_autorefresh(content, _auto_refresh, interval_ms=4000)
    register_activity(content)
    def _cleanup(_=None):
        global texboxIdproductos, texboxNombreproductos, texboxPrecioproductos, texboxCantidadProductos
        global tree, base, lbl_total_productos, lbl_stock_total
        texboxIdproductos = None
        texboxNombreproductos = None
        texboxPrecioproductos = None
        texboxCantidadProductos = None
        tree = None
        base = None
        lbl_total_productos = None
        lbl_stock_total = None
    content.bind("<Destroy>", _cleanup)
    return content


def productosFormulario():
    """Construye la ventana de productos."""
    global base
    try:
        base = Toplevel()
        apply_chrome(base, "StockARG", 1320, 800, min_w=1100, min_h=650, state_key="productos")
        apply_ttk_style(base)
        productos_panel(base)
        return
    except ValueError as error:
        log_error(f"Productos.productosFormulario: {error}")


def guardarRegistros():
    """Guarda un producto nuevo."""
    def _work():
        global texboxIdproductos, texboxNombreproductos, texboxPrecioproductos, texboxCantidadProductos
        try:
            if texboxIdproductos is None or texboxNombreproductos is None or texboxPrecioproductos is None or texboxCantidadProductos is None:
                log_error("Productos.guardarRegistros: widgets no inicializados")
                return
            idProductos = texboxIdproductos.get().strip()
            nombreProductos = texboxNombreproductos.get().strip()
            precioProductos = texboxPrecioproductos.get().strip()
            cantidadProductos = texboxCantidadProductos.get().strip()
            ok_id, msg_id = validar_id(idProductos, "Id Producto")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(
                id=idProductos,
                nombre=nombreProductos,
                precio=precioProductos,
                cantidad=cantidadProductos
            )
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            cantidad_int = parse_int(cantidadProductos, min_value=0, allow_zero=True)
            if cantidad_int is None:
                dialog_error(base, "Error", "Cantidad invalida")
                return
            precio_val = parse_float(precioProductos, min_value=0, allow_zero=False)
            if precio_val is None:
                dialog_error(base, "Error", "Precio invalido")
                return
            if Productos.existeProducto(idProductos):
                dialog_error(base, "Error", "El Id ya existe")
                return

            ok, msg = Productos.ingresarProductos(idProductos, nombreProductos, precio_val, cantidad_int)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo guardar el producto")
                return
            dialog_info(base, "Informacion", "Los datos fueron guardados")

            actualizarTreeView()

            texboxNombreproductos.delete(0, END)
            texboxPrecioproductos.delete(0, END)
            texboxCantidadProductos.delete(0, END)
            texboxIdproductos.config(state="normal")
        except ValueError as error:
            log_error(f"Productos.guardarRegistros: {error}")

    return run_with_loading(base, "Guardando...", _work)


def actualizarTreeView(filtro=None, silent=False):
    """Refresca el listado de productos."""
    def _work():
        global tree
        try:
            if tree is None or (hasattr(tree, "winfo_exists") and not tree.winfo_exists()):
                return
            selected = tree.item(tree.focus(), "values")
            selected_id = selected[0] if selected else None
            tree.delete(*tree.get_children())
            rows = Productos.mostrarProductos(filtro) or []
            count = 0
            total_stock = 0
            for row in rows:
                row = list(row)
                if len(row) >= 6:
                    precio_val = row[2]
                    try:
                        precio_txt = f"$ {float(precio_val):.2f}".rstrip("0").rstrip(".")
                    except Exception:
                        precio_txt = f"$ {precio_val}"
                    values = [row[0], row[1], precio_txt, row[3], row[5] or "-"]
                    try:
                        total_stock += int(row[3])
                    except Exception:
                        pass
                else:
                    values = row
                item = tree.insert("", "end", values=values)
                count += 1
                if selected_id is not None and str(values[0]) == str(selected_id):
                    tree.selection_set(item)
                    tree.focus(item)
                    tree.see(item)
            if count == 0:
                treeview_set_empty(tree)
            try:
                if lbl_total_productos is not None:
                    lbl_total_productos.config(text=f"Productos: {count}")
                if lbl_stock_total is not None:
                    lbl_stock_total.config(text=f"Stock total: {total_stock}")
            except Exception:
                pass
        except ValueError as error:
            log_error(f"Productos.actualizarTreeView: {error}")

    if base is None or silent:
        return _work()
    return run_with_loading(base, "Cargando...", _work)


def seleccionarRegistro(event):
    """Carga la fila seleccionada en el formulario."""
    try:
        itemSeleccionado = tree.focus()
        if itemSeleccionado:
            values = tree.item(itemSeleccionado)["values"]
            tags = tree.item(itemSeleccionado, "tags") or ()
            first = str(values[0]).strip() if values else ""
            if (not values) or ("empty" in tags) or (not first) or (first.lower() == "sin resultados"):
                texboxIdproductos.config(state="normal")
                try:
                    _update_buttons()
                except Exception:
                    pass
                return

            texboxIdproductos.delete(0, END)
            texboxIdproductos.insert(0, values[0])
            texboxIdproductos.config(state="readonly")
            texboxNombreproductos.delete(0, END)
            texboxNombreproductos.insert(0, values[1])
            texboxPrecioproductos.delete(0, END)
            precio_txt = str(values[2])
            if precio_txt.startswith("$"):
                precio_txt = precio_txt.replace("$", "").strip()
            texboxPrecioproductos.insert(0, precio_txt)
            texboxCantidadProductos.delete(0, END)
            texboxCantidadProductos.insert(0, values[3])
            try:
                _update_buttons()
            except Exception:
                pass
    except ValueError as error:
        log_error(f"Productos.seleccionarRegistro: {error}")


def modificarRegistros():
    """Edita un producto existente."""
    def _work():
        global texboxIdproductos, texboxNombreproductos, texboxPrecioproductos, texboxCantidadProductos
        try:
            if texboxIdproductos is None or texboxNombreproductos is None or texboxPrecioproductos is None or texboxCantidadProductos is None:
                log_error("Productos.modificarRegistros: widgets no inicializados")
                return
            idproductos = texboxIdproductos.get().strip()
            nombreproductos = texboxNombreproductos.get().strip()
            precioproductos = texboxPrecioproductos.get().strip()
            cantidadProductos = texboxCantidadProductos.get().strip()
            ok_id, msg_id = validar_id(idproductos, "Id Producto")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(
                id=idproductos,
                nombre=nombreproductos,
                precio=precioproductos,
                cantidad=cantidadProductos
            )
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            cantidad_int = parse_int(cantidadProductos, min_value=0, allow_zero=True)
            if cantidad_int is None:
                dialog_error(base, "Error", "Cantidad invalida")
                return
            precio_val = parse_float(precioproductos, min_value=0, allow_zero=False)
            if precio_val is None:
                dialog_error(base, "Error", "Precio invalido")
                return

            ok, msg = Productos.modificarProductos(idproductos, nombreproductos, precio_val, cantidad_int)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo actualizar el producto")
                return
            dialog_info(base, "Informacion", "Los datos fueron actualizados")
            actualizarTreeView()

            texboxIdproductos.config(state="normal")
            texboxIdproductos.delete(0, END)
            texboxNombreproductos.delete(0, END)
            texboxPrecioproductos.delete(0, END)
            texboxCantidadProductos.delete(0, END)
        except ValueError as error:
            log_error(f"Productos.modificarRegistros: {error}")

    return run_with_loading(base, "Actualizando...", _work)


def eliminarRegistros():
    """Elimina el producto indicado."""
    def _work():
        global texboxIdproductos, texboxNombreproductos, texboxPrecioproductos
        try:
            if texboxIdproductos is None:
                log_error("Productos.eliminarRegistros: widgets no inicializados")
                return
            idProductos = texboxIdproductos.get().strip()
            ok_id, msg_id = validar_id(idProductos, "Id Producto")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(id=idProductos)
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                dialog_error(base, "Error", "No hay conexion a la base de datos")
                return
            cursor = cone.cursor()
            try:
                cone.start_transaction()
            except Exception:
                pass
            cursor.execute("DELETE FROM movimientos_stock WHERE producto_id=%s", (idProductos,))
            cursor.execute("DELETE FROM ventas WHERE id=%s", (idProductos,))
            cursor.execute("DELETE FROM productos WHERE id=%s", (idProductos,))
            cone.commit()
            cone.close()
            dialog_info(base, "Informacion", "Los datos fueron eliminados")

            actualizarTreeView()

            texboxIdproductos.config(state="normal")
            texboxIdproductos.delete(0, END)
            texboxNombreproductos.delete(0, END)
            texboxPrecioproductos.delete(0, END)
        except ValueError as error:
            log_error(f"Productos.eliminarRegistros: {error}")

    return run_with_loading(base, "Eliminando...", _work)


if __name__ == "__main__":
    productosFormulario()
    tk.mainloop()
