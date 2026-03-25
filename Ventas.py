"""Módulo de ventas: datos y UI."""

from Conexion import cconexion
import mysql.connector
from Logger import log_error, log_info, log_warning
from Inventario import registrar_movimiento


class Ventas:
    @staticmethod
    def _registrar_movimiento(cursor, producto_id, tipo, cantidad, nota=None):
        try:
            cursor.execute(
                """
                INSERT INTO movimientos_stock (producto_id, tipo, cantidad, nota)
                VALUES (%s, %s, %s, %s)
                """,
                (producto_id, tipo, cantidad, nota)
            )
        except Exception as exc:
            log_warning(f"Ventas.movimiento: no registrado: {exc}")

    @staticmethod
    def mostrarVentas(filtro=None):
        """Obtiene lista de ventas."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return []
            cursor = cone.cursor()
            sql = """
                SELECT v.venta_id, v.id, v.nombre, COALESCE(v.precio, p.precio) AS precio, v.nro_ventas, v.fecha
                FROM ventas v
                LEFT JOIN productos p ON p.id = v.id
            """
            params = None
            if filtro:
                sql += " WHERE v.venta_id LIKE %s OR v.id LIKE %s OR v.nombre LIKE %s"
                like = f"%{filtro}%"
                params = (like, like, like)
            sql += ";"
            cursor.execute(sql, params or ())
            datos = cursor.fetchall()
            cone.close()
            return datos
        except mysql.connector.Error as error:
            log_error(f"Ventas.mostrarVentas: {error}")
            return []

    @staticmethod
    def resumenVentas():
        """Obtiene resumen de ventas."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return 0, 0, 0.0
            cursor = cone.cursor()
            cursor.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(v.nro_ventas),0),
                       COALESCE(SUM(v.nro_ventas * COALESCE(v.precio, p.precio)),0)
                FROM ventas v
                LEFT JOIN productos p ON p.id = v.id
                """
            )
            row = cursor.fetchone()
            cone.close()
            return row[0] or 0, row[1] or 0, float(row[2] or 0)
        except mysql.connector.Error as error:
            log_error(f"Ventas.resumenVentas: {error}")
            return 0, 0, 0.0

    @staticmethod
    def ingresarVentas(id, nombre, nro, precio_override=None):
        """Inserta una venta en la base."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            try:
                cone.start_transaction()
                cursor.execute("SELECT nombre, precio, cantidad FROM productos WHERE id=%s", (id,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError("Producto no existe")
                nombre_db = row[0]
                precio_db = row[1]
                stock_actual = int(row[2])
                if stock_actual < int(nro):
                    raise ValueError("Stock insuficiente")
                if not nombre:
                    nombre = nombre_db
                precio_use = precio_db
                if precio_override is not None:
                    try:
                        precio_use = float(precio_override)
                    except Exception:
                        raise ValueError("Precio invalido")
                    if precio_use <= 0:
                        raise ValueError("Precio invalido")
                sql = """
                INSERT INTO ventas (id, nombre, precio, nro_ventas, fecha)
                VALUES (%s, %s, %s, %s, NOW())
                """
                cursor.execute(sql, (id, nombre, precio_use, nro))
                cursor.execute("UPDATE productos SET cantidad = cantidad - %s WHERE id=%s", (nro, id))
                Ventas._registrar_movimiento(cursor, id, "venta", int(nro), nota="Venta")
                cone.commit()
                log_info(f"Ventas.ingresarVentas: venta guardada (id={id}, nro={nro})")
                return True, None
            except ValueError as ve:
                try:
                    cone.rollback()
                except Exception:
                    pass
                return False, str(ve)
            except Exception as exc:
                try:
                    cone.rollback()
                except Exception:
                    pass
                log_error(f"Ventas.ingresarVentas: {exc}")
                return False, "Error al guardar la venta"
            finally:
                try:
                    cone.close()
                except Exception:
                    pass
        except mysql.connector.Error as error:
            log_error(f"Ventas.ingresarVentas: {error}")
            return False, "Error al guardar la venta"

    def modificarVentas(venta_id, idVentas, nombresVentas, nroVentas, precio_override=None):
        """Actualiza una venta existente."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            try:
                cone.start_transaction()
                cursor.execute("SELECT nro_ventas FROM ventas WHERE venta_id=%s", (venta_id,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError("Venta no existe")

                nro_anterior = int(row[0])
                nro_nuevo = int(nroVentas)
                delta = nro_nuevo - nro_anterior

                precio_use = None
                if precio_override is not None:
                    try:
                        precio_use = float(precio_override)
                    except Exception:
                        raise ValueError("Precio invalido")
                    if precio_use <= 0:
                        raise ValueError("Precio invalido")
                if precio_use is None:
                    sql = "UPDATE ventas set ventas.nombre =%s, ventas.nro_ventas =%s, ventas.fecha=NOW() Where ventas.venta_id =%s;"
                    valores = (nombresVentas, nro_nuevo, venta_id)
                else:
                    sql = "UPDATE ventas set ventas.nombre =%s, ventas.nro_ventas =%s, ventas.precio=%s, ventas.fecha=NOW() Where ventas.venta_id =%s;"
                    valores = (nombresVentas, nro_nuevo, precio_use, venta_id)
                cursor.execute(sql, valores)

                if delta != 0:
                    cursor.execute("SELECT cantidad FROM productos WHERE id=%s", (idVentas,))
                    row = cursor.fetchone()
                    if not row:
                        raise ValueError("Producto no existe")
                    stock_actual = int(row[0])
                    if delta > 0:
                        if stock_actual < delta:
                            raise ValueError("Stock insuficiente")
                        cursor.execute("UPDATE productos SET cantidad = cantidad - %s WHERE id=%s", (delta, idVentas))
                        Ventas._registrar_movimiento(cursor, idVentas, "venta", int(delta), nota="Ajuste venta")
                    else:
                        cursor.execute("UPDATE productos SET cantidad = cantidad + %s WHERE id=%s", (abs(delta), idVentas))
                        Ventas._registrar_movimiento(cursor, idVentas, "devolucion", int(abs(delta)), nota="Ajuste venta")
                cone.commit()
                log_info(f"Ventas.modificarVentas: {cursor.rowcount} registro(s)")
                return True, None
            except ValueError as ve:
                try:
                    cone.rollback()
                except Exception:
                    pass
                return False, str(ve)
            except Exception as exc:
                try:
                    cone.rollback()
                except Exception:
                    pass
                log_error(f"Ventas.modificarVentas: {exc}")
                return False, "Error al actualizar la venta"
            finally:
                try:
                    cone.close()
                except Exception:
                    pass
        except mysql.connector.Error as error:
            log_error(f"Ventas.modificarVentas: {error}")
            return False, "Error al actualizar la venta"

    def eliminarVentas(venta_id, idVentas):
        """Elimina una venta por ID."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            try:
                cone.start_transaction()
                cursor.execute("SELECT nro_ventas FROM ventas WHERE venta_id=%s", (venta_id,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError("Venta no existe")
                nro_ventas = int(row[0])

                cursor.execute("SELECT cantidad FROM productos WHERE id=%s", (idVentas,))
                prod = cursor.fetchone()
                if prod:
                    cursor.execute("UPDATE productos SET cantidad = cantidad + %s WHERE id=%s", (nro_ventas, idVentas))

                sql = "DELETE from ventas WHERE ventas.venta_id=%s;"
                valores = (venta_id,)
                cursor.execute(sql, valores)
                if nro_ventas > 0:
                    Ventas._registrar_movimiento(cursor, idVentas, "devolucion", int(nro_ventas), nota="Eliminacion venta")
                cone.commit()
                log_info(f"Ventas.eliminarVentas: {cursor.rowcount} registro(s)")
                return True, None
            except ValueError as ve:
                try:
                    cone.rollback()
                except Exception:
                    pass
                return False, str(ve)
            except Exception as exc:
                try:
                    cone.rollback()
                except Exception:
                    pass
                log_error(f"Ventas.eliminarVentas: {exc}")
                return False, "Error al eliminar la venta"
            finally:
                try:
                    cone.close()
                except Exception:
                    pass
        except mysql.connector.Error as error:
            log_error(f"Ventas.eliminarVentas: {error}")
            return False, "Error al eliminar la venta"


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
    widget_alive,
    register_activity,
)


class FormularioVentas:
    global texboxIdventas
    texboxIdVentas = None

    global texboxNombreVentas
    texboxNombreVentas = None

    global texboxPrecioVentas
    texboxPrecioVentas = None

    global texboxNroVentas
    texboxNroVentas = None

    global base
    base = None

    global tree
    tree = None

    global selected_venta_id
    selected_venta_id = None

    global lbl_total_ventas
    lbl_total_ventas = None

    global lbl_total_unidades
    lbl_total_unidades = None

    global lbl_total_monto
    lbl_total_monto = None

    global _update_buttons_fn
    _update_buttons_fn = None

def ventas_panel(parent):
    """Construye el panel de ventas dentro de un contenedor."""
    global texboxIdVentas
    global texboxNombreVentas
    global texboxPrecioVentas
    global texboxNroVentas
    global tree
    global base
    global lbl_total_ventas
    global lbl_total_unidades
    global lbl_total_monto
    global selected_venta_id
    global _update_buttons_fn

    base = parent.winfo_toplevel()
    apply_ttk_style(base)

    content = tk.Frame(parent, bg=BG_MAIN)
    content.pack(fill="both", expand=True)
    content.grid_columnconfigure(0, weight=0)
    content.grid_columnconfigure(1, weight=1)
    content.grid_rowconfigure(0, weight=1)
    content.grid_rowconfigure(1, weight=1)

    groupbox = LabelFrame(
        content,
        text="Datos de las Ventas",
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

    texboxIdVentas_label = Label(groupbox, text="Id Producto:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxIdVentas_label.grid(row=0, column=0, sticky="w", pady=4)
    texboxIdVentas = Entry(
        groupbox,
        bg=BG_INPUT,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT,
        readonlybackground=BG_INPUT,
        disabledforeground=FG_TEXT
    )
    texboxIdVentas.grid(row=0, column=1, pady=4, ipadx=6, ipady=4)

    texboxNombreVentas_label = Label(groupbox, text="Nombre:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxNombreVentas_label.grid(row=1, column=0, sticky="w", pady=4)
    texboxNombreVentas = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxNombreVentas.grid(row=1, column=1, pady=4, ipadx=6, ipady=4)

    texboxPrecioVentas_label = Label(groupbox, text="Precio actual:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxPrecioVentas_label.grid(row=2, column=0, sticky="w", pady=4)
    texboxPrecioVentas = Entry(
        groupbox,
        bg=BG_INPUT,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT
    )
    texboxPrecioVentas.grid(row=2, column=1, pady=4, ipadx=6, ipady=4)

    texboxNroVentas_label = Label(groupbox, text="Nro de Ventas:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    texboxNroVentas_label.grid(row=3, column=0, sticky="w", pady=4)
    texboxNroVentas = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxNroVentas.grid(row=3, column=1, pady=4, ipadx=6, ipady=4)

    estado_label = tk.Label(groupbox, text="", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    estado_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _set_estado(texto, ok=True):
        if not texto:
            estado_label.config(text="")
            return
        icon = "✅" if ok else "⚠️"
        estado_label.config(text=f"{icon} {texto}", fg=FG_MUTED if ok else "#fca5a5")

    def _set_precio(value):
        texboxPrecioVentas.delete(0, END)
        if value is not None and value != "":
            try:
                precio_txt = f"$ {float(value):.2f}".rstrip("0").rstrip(".")
            except Exception:
                precio_txt = f"$ {value}"
            texboxPrecioVentas.insert(0, precio_txt)

    def _autofill_nombre(_=None):
        prod_id = texboxIdVentas.get().strip()
        if not prod_id:
            _set_precio("")
            _set_estado("")
            return
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return
            cursor = cone.cursor()
            cursor.execute("SELECT nombre, precio FROM productos WHERE id=%s", (prod_id,))
            row = cursor.fetchone()
            cone.close()
            if row:
                if not texboxNombreVentas.get().strip():
                    texboxNombreVentas.delete(0, END)
                    texboxNombreVentas.insert(0, row[0])
                _set_precio(row[1])
                _set_estado("Producto encontrado", ok=True)
            else:
                _set_precio("")
                _set_estado("Producto no encontrado", ok=False)
        except Exception as exc:
            log_warning(f"Ventas.autofill_nombre: {exc}")

    texboxIdVentas.bind("<FocusOut>", _autofill_nombre)
    texboxIdVentas.bind("<Return>", _autofill_nombre)
    def _debounced_fill(_=None):
        if hasattr(base, "_fill_after"):
            try:
                base.after_cancel(base._fill_after)
            except Exception:
                pass
        base._fill_after = base.after(200, _autofill_nombre)
    texboxIdVentas.bind("<KeyRelease>", _debounced_fill)


    def _limpiar_form():
        texboxIdVentas.config(state="normal")
        texboxIdVentas.delete(0, END)
        texboxNombreVentas.delete(0, END)
        texboxPrecioVentas.delete(0, END)
        texboxNroVentas.delete(0, END)
        try:
            global selected_venta_id
            selected_venta_id = None
        except Exception:
            pass
        _update_buttons()

    btn_row = tk.Frame(groupbox, bg=BG_CARD)
    btn_row.grid(row=4, column=0, columnspan=2, pady=(10, 0))

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
            id_txt = texboxIdVentas.get().strip()
            nombre_txt = texboxNombreVentas.get().strip()
            nro_txt = texboxNroVentas.get().strip()
            is_selected = bool(selected_venta_id)
            if not is_selected:
                try:
                    item = tree.focus()
                    if not item:
                        sel = tree.selection()
                        item = sel[0] if sel else item
                    values = tree.item(item, "values") if item else []
                    tags = tree.item(item, "tags") if item else ()
                    first = str(values[0]).strip() if values else ""
                    if values and "empty" not in (tags or ()) and first and first.lower() != "sin resultados":
                        is_selected = True
                except Exception:
                    pass
            required_ok = all([id_txt, nombre_txt, nro_txt])
            _set_guardar_state((not is_selected and required_ok))
            btn_editar.config(state="normal" if (is_selected and required_ok) else "disabled")
            btn_eliminar.config(state="normal")
        except Exception:
            pass

    _update_buttons_fn = _update_buttons

    for w in (texboxIdVentas, texboxNombreVentas, texboxPrecioVentas, texboxNroVentas):
        w.bind("<KeyRelease>", lambda e: _update_buttons())

    groupbox = LabelFrame(
        content,
        text="Lista de Ventas",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    groupbox.grid(row=0, column=1, padx=16, pady=16, sticky="new")

    summary_row = tk.Frame(groupbox, bg=BG_CARD)
    summary_row.pack(fill="x", pady=(0, 8))
    lbl_total_ventas = tk.Label(summary_row, text="Ventas: 0", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    lbl_total_ventas.pack(side="left", padx=(0, 12))
    lbl_total_unidades = tk.Label(summary_row, text="Unidades: 0", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    lbl_total_unidades.pack(side="left", padx=(0, 12))
    lbl_total_monto = tk.Label(summary_row, text="Total: $ 0", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    lbl_total_monto.pack(side="left")

    search_row = tk.Frame(groupbox, bg=BG_CARD)
    search_row.pack(fill="x", pady=(0, 8))
    tk.Label(search_row, text="Buscar:", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE).pack(side="left")
    search_entry = tk.Entry(search_row, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    search_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=2)

    tree_wrap = tk.Frame(groupbox, bg=BG_CARD)
    tree_wrap.pack(fill="both", expand=True)
    tree_wrap.grid_columnconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(1, weight=0)

    tree = ttk.Treeview(
        tree_wrap,
        columns=("Id Venta", "Id Producto", "Nombre", "Precio", "Nro de Ventas", "Fecha"),
        show="headings",
        height=8,
        style="Dark.Treeview"
    )
    tree.column("# 1", anchor=CENTER, width=80, stretch=False)
    tree.heading("# 1", text="Id Venta")
    tree.column("# 2", anchor=CENTER, width=100, stretch=False)
    tree.heading("# 2", text="Id Producto")
    tree.column("# 3", anchor=CENTER, stretch=True)
    tree.heading("# 3", text="Nombre")
    tree.column("# 4", anchor=CENTER, stretch=False)
    tree.heading("# 4", text="Precio")
    tree.column("# 5", anchor=CENTER, stretch=False)
    tree.heading("# 5", text="Nro de Ventas")
    tree.column("# 6", anchor=CENTER, width=140, stretch=True)
    tree.heading("# 6", text="Fecha")
    tree.tag_configure("empty", foreground=FG_MUTED)
    configurar_orden_treeview(tree, numeric_cols={"Id Venta", "Id Producto", "Precio", "Nro de Ventas"})

    def _on_select(event=None):
        seleccionarRegistro(event)
        try:
            _update_buttons()
        except Exception:
            pass
    tree.bind("<<TreeviewSelect>>", _on_select)
    scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview, style="Dark.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")

    headers = ["Id Venta", "Id Producto", "Nombre", "Precio", "Nro de Ventas", "Fecha"]
    dark_button(search_row, "Exportar CSV", lambda: exportar_treeview_csv(tree, headers, "ventas")).pack(side="right")
    def _export_pdf():
        ok, msg = exportar_treeview_pdf(tree, headers, "Reporte de Ventas", "ventas")
        if not ok and msg and msg != "Cancelado":
            dialog_error(base, "Error", msg)
    dark_button(search_row, "Exportar PDF", _export_pdf).pack(side="right", padx=6)

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

    spacer = tk.Frame(content, bg=BG_MAIN)
    spacer.grid(row=1, column=1, padx=16, pady=(0, 16), sticky="nsew")

    actualizarTreeView()
    _update_buttons()
    btn_eliminar.config(state="normal")

    def _auto_refresh():
        try:
            filtro = search_entry.get().strip()
        except Exception:
            filtro = None
        actualizarTreeView(filtro, silent=True)

    schedule_autorefresh(content, _auto_refresh, interval_ms=4000)
    register_activity(content)
    def _cleanup(_=None):
        global texboxIdVentas, texboxNombreVentas, texboxPrecioVentas, texboxNroVentas
        global tree, base, lbl_total_ventas, lbl_total_unidades, lbl_total_monto
        global selected_venta_id, _update_buttons_fn
        texboxIdVentas = None
        texboxNombreVentas = None
        texboxPrecioVentas = None
        texboxNroVentas = None
        tree = None
        base = None
        lbl_total_ventas = None
        lbl_total_unidades = None
        lbl_total_monto = None
        selected_venta_id = None
        _update_buttons_fn = None
    content.bind("<Destroy>", _cleanup)
    return content


def ventasFormulario():
    """Construye la ventana de ventas."""
    global base
    try:
        base = Toplevel()
        apply_chrome(base, "StockARG", 1320, 800, min_w=1100, min_h=650, state_key="ventas")
        apply_ttk_style(base)
        ventas_panel(base)
        return
    except ValueError as error:
        log_error(f"Ventas.ventasFormulario: {error}")


def guardarRegistros():
    """Guarda una venta nueva."""
    def _work():
        global texboxIdVentas, texboxNombreVentas, texboxNroVentas, texboxPrecioVentas
        try:
            if texboxIdVentas is None or texboxNombreVentas is None or texboxNroVentas is None:
                log_error("Ventas.guardarRegistros: widgets no inicializados")
                return
            idVentas = texboxIdVentas.get().strip()
            nombreVentas = texboxNombreVentas.get().strip()
            nroVentas = texboxNroVentas.get().strip()
            precio_txt = texboxPrecioVentas.get().strip() if texboxPrecioVentas is not None else ""
            ok_id, msg_id = validar_id(idVentas, "Id Producto")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(
                id=idVentas,
                nombre=nombreVentas,
                cantidad=nroVentas
            )
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            nro_int = parse_int(nroVentas, min_value=1, allow_zero=False)
            if nro_int is None:
                dialog_error(base, "Error", "Cantidad invalida")
                return
            precio_val = None
            if precio_txt:
                precio_val = parse_float(precio_txt, min_value=0, allow_zero=False)
                if precio_val is None:
                    dialog_error(base, "Error", "Precio invalido")
                    return

            ok, msg = Ventas.ingresarVentas(idVentas, nombreVentas, nro_int, precio_val)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo guardar la venta")
                return
            dialog_info(base, "Informacion", "Los datos fueron guardados")

            actualizarTreeView()

            texboxNombreVentas.delete(0, END)
            texboxNroVentas.delete(0, END)
            texboxPrecioVentas.delete(0, END)
            texboxIdVentas.config(state="normal")
            # fecha es automatica
        except ValueError as error:
            log_error(f"Ventas.guardarRegistros: {error}")

    return run_with_loading(base, "Guardando...", _work)


def _fmt_fecha(valor):
    if valor is None:
        return ""
    try:
        return valor.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def actualizarTreeView(filtro=None, silent=False):
    """Refresca el listado de ventas."""
    def _work():
        global tree, selected_venta_id
        try:
            if tree is None or (hasattr(tree, "winfo_exists") and not tree.winfo_exists()):
                return
            selected = tree.item(tree.focus(), "values")
            selected_venta = selected[0] if selected else None
            if selected_venta_id:
                selected_venta = selected_venta_id
            tree.delete(*tree.get_children())
            rows = Ventas.mostrarVentas(filtro) or []
            count = 0
            for row in rows:
                row = list(row)
                if len(row) >= 6:
                    try:
                        precio_txt = f"$ {float(row[3]):.2f}".rstrip("0").rstrip(".")
                    except Exception:
                        precio_txt = f"$ {row[3]}"
                    row[3] = precio_txt
                    row[5] = _fmt_fecha(row[5])
                item = tree.insert("", "end", values=row)
                count += 1
                if selected_venta is not None and str(row[0]) == str(selected_venta):
                    tree.selection_set(item)
                    tree.focus(item)
                    tree.see(item)
            if count == 0:
                treeview_set_empty(tree)
            try:
                total, unidades, monto = Ventas.resumenVentas()
                if lbl_total_ventas is not None:
                    lbl_total_ventas.config(text=f"Ventas: {total}")
                if lbl_total_unidades is not None:
                    lbl_total_unidades.config(text=f"Unidades: {unidades}")
                if lbl_total_monto is not None:
                    lbl_total_monto.config(text=f"Total: $ {monto:.2f}")
                try:
                    if _update_buttons_fn:
                        _update_buttons_fn()
                except Exception:
                    pass
            except Exception:
                pass
        except ValueError as error:
            log_error(f"Ventas.actualizarTreeView: {error}")

    if base is None or silent:
        return _work()
    return run_with_loading(base, "Cargando...", _work)


def seleccionarRegistro(event):
    """Carga la fila seleccionada en el formulario."""
    global selected_venta_id
    global _update_buttons_fn
    try:
        itemSeleccionado = tree.focus()
        if not itemSeleccionado:
            try:
                sel = tree.selection()
                itemSeleccionado = sel[0] if sel else itemSeleccionado
            except Exception:
                pass
        if itemSeleccionado:
            values = tree.item(itemSeleccionado)["values"]
            tags = tree.item(itemSeleccionado, "tags") or ()
            first = str(values[0]).strip() if values else ""
            if (not values) or ("empty" in tags) or (not first) or (first.lower() == "sin resultados"):
                texboxIdVentas.config(state="normal")
                selected_venta_id = None
                try:
                    if _update_buttons_fn:
                        _update_buttons_fn()
                except Exception:
                    pass
                return

            selected_venta_id = values[0]

            texboxIdVentas.delete(0, END)
            texboxIdVentas.insert(0, values[1])
            texboxIdVentas.config(state="readonly")
            texboxNombreVentas.delete(0, END)
            texboxNombreVentas.insert(0, values[2])
            try:
                # precio en vivo desde la fila
                precio_val = values[3]
                texboxPrecioVentas.delete(0, END)
                texboxPrecioVentas.insert(0, str(precio_val))
            except Exception:
                pass
            texboxNroVentas.delete(0, END)
            texboxNroVentas.insert(0, values[4])
            # fecha es automatica, no editable
            try:
                if _update_buttons_fn:
                    _update_buttons_fn()
            except Exception:
                pass
    except ValueError as error:
        log_error(f"Ventas.seleccionarRegistro: {error}")


def modificarRegistros():
    """Edita una venta existente."""
    def _work():
        global texboxIdVentas, texboxNombreVentas, texboxNroVentas, texboxPrecioVentas, selected_venta_id
        try:
            if texboxIdVentas is None or texboxNombreVentas is None or texboxNroVentas is None:
                log_error("Ventas.modificarRegistros: widgets no inicializados")
                return
            if not selected_venta_id:
                try:
                    item = tree.focus()
                    if not item:
                        sel = tree.selection()
                        item = sel[0] if sel else item
                    values = tree.item(item, "values") if item else []
                    tags = tree.item(item, "tags") if item else ()
                    first = str(values[0]).strip() if values else ""
                    if values and "empty" not in (tags or ()) and first and first.lower() != "sin resultados":
                        selected_venta_id = values[0]
                except Exception:
                    selected_venta_id = None
            if not selected_venta_id:
                dialog_error(base, "Error", "Selecciona una venta")
                return
            idVentas = texboxIdVentas.get().strip()
            nombreVentas = texboxNombreVentas.get().strip()
            nroVentas = texboxNroVentas.get().strip()
            precio_txt = texboxPrecioVentas.get().strip() if texboxPrecioVentas is not None else ""
            ok_id, msg_id = validar_id(idVentas, "Id Producto")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(
                id=idVentas,
                nombre=nombreVentas,
                cantidad=nroVentas
            )
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            nro_int = parse_int(nroVentas, min_value=1, allow_zero=False)
            if nro_int is None:
                dialog_error(base, "Error", "Cantidad invalida")
                return
            precio_val = None
            if precio_txt:
                precio_val = parse_float(precio_txt, min_value=0, allow_zero=False)
                if precio_val is None:
                    dialog_error(base, "Error", "Precio invalido")
                    return
            ok, msg = Ventas.modificarVentas(selected_venta_id, idVentas, nombreVentas, nro_int, precio_val)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo actualizar la venta")
                return
            dialog_info(base, "Informacion", "Los datos fueron actualizados")
            actualizarTreeView()

            texboxIdVentas.config(state="normal")
            texboxIdVentas.delete(0, END)
            texboxNombreVentas.delete(0, END)
            texboxNroVentas.delete(0, END)
            texboxPrecioVentas.delete(0, END)
            selected_venta_id = None
            # fecha es automatica
        except ValueError as error:
            log_error(f"Ventas.modificarRegistros: {error}")

    return run_with_loading(base, "Actualizando...", _work)


def eliminarRegistros():
    """Elimina la venta indicada."""
    def _work():
        global texboxIdVentas, texboxNombreVentas, texboxNroVentas, texboxPrecioVentas, selected_venta_id
        try:
            if texboxIdVentas is None:
                log_error("Ventas.eliminarRegistros: widgets no inicializados")
                return
            if not selected_venta_id:
                try:
                    item = tree.focus()
                    if not item:
                        sel = tree.selection()
                        item = sel[0] if sel else item
                    values = tree.item(item, "values") if item else []
                    tags = tree.item(item, "tags") if item else ()
                    first = str(values[0]).strip() if values else ""
                    if values and "empty" not in (tags or ()) and first and first.lower() != "sin resultados":
                        selected_venta_id = values[0]
                except Exception:
                    selected_venta_id = None
            if not selected_venta_id:
                dialog_error(base, "Error", "Selecciona una venta")
                return
            id_producto = texboxIdVentas.get().strip()
            ok_id, msg_id = validar_id(id_producto, "Id Producto")
            if not ok_id:
                dialog_error(base, "Error", "Selecciona una venta válida")
                return
            ok, msg = Ventas.eliminarVentas(selected_venta_id, id_producto)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo eliminar la venta")
                return
            dialog_info(base, "Informacion", "Los datos fueron eliminados")

            actualizarTreeView()

            texboxIdVentas.config(state="normal")
            texboxIdVentas.delete(0, END)
            texboxNombreVentas.delete(0, END)
            texboxNroVentas.delete(0, END)
            if texboxPrecioVentas is not None:
                texboxPrecioVentas.delete(0, END)
            selected_venta_id = None
        except ValueError as error:
            log_error(f"Ventas.eliminarRegistros: {error}")

    return run_with_loading(base, "Eliminando...", _work)


if __name__ == "__main__":
    ventasFormulario()
    tk.mainloop()
