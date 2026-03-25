"""Modulo de control de stock: vista, alertas y movimientos."""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk
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
    FONT_BUTTON,
    dark_button,
    apply_chrome,
    apply_ttk_style,
)
from Dialogs import dialog_error, dialog_info, dialog_confirm
from Conexion import cconexion
from Logger import log_error, log_warning, log_info
from Utils import (
    exportar_treeview_csv,
    campos_requeridos,
    parse_int,
    validar_id,
    configurar_orden_treeview,
    treeview_set_empty,
    run_with_loading,
    exportar_treeview_pdf,
    schedule_autorefresh,
    widget_alive,
    register_activity,
)
from Inventario import registrar_movimiento


def _fmt_fecha(valor):
    if valor is None:
        return ""
    try:
        return valor.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def _calc_estado(stock_actual, stock_inicial):
    if stock_inicial <= 0:
        return 0, "Sin dato"
    porcentaje = int(round((stock_actual / stock_inicial) * 100))
    if porcentaje > 100:
        porcentaje = 100
    if porcentaje <= 30:
        return porcentaje, "Bajo"
    if porcentaje <= 54:
        return porcentaje, "Medio"
    return porcentaje, "Ok"


def _load_stock(filtro=None):
    cone = cconexion.cconexionBaseDeDatos()
    if cone is None:
        log_warning("Stock._load_stock: sin conexion a DB")
        return None, "No hay conexion a la base de datos"
    cursor = cone.cursor()
    sql = "SELECT id, nombre, cantidad, stock_inicial, fecha_ingreso FROM productos"
    params = None
    if filtro:
        sql += " WHERE id LIKE %s OR nombre LIKE %s"
        like = f"%{filtro}%"
        params = (like, like)
    sql += ";"
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    cone.close()
    return rows, None


def _load_movimientos(filtro=None):
    cone = cconexion.cconexionBaseDeDatos()
    if cone is None:
        log_warning("Stock._load_movimientos: sin conexion a DB")
        return None, "No hay conexion a la base de datos"
    cursor = cone.cursor()
    sql = """
        SELECT m.id, m.producto_id, p.nombre, m.tipo, m.cantidad, m.nota, m.creado_en
        FROM movimientos_stock m
        LEFT JOIN productos p ON p.id = m.producto_id
    """
    params = None
    if filtro:
        sql += " WHERE m.producto_id LIKE %s OR p.nombre LIKE %s OR m.tipo LIKE %s"
        like = f"%{filtro}%"
        params = (like, like, like)
    sql += " ORDER BY m.id DESC;"
    try:
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cone.close()
        return rows, None
    except Exception as exc:
        cone.close()
        log_error(f"Stock._load_movimientos: {exc}")
        return None, "No se pudo cargar movimientos"


def _recalcular_stock(producto_id, cursor=None):
    """Recalcula stock desde movimientos para un producto."""
    own_conn = False
    if cursor is None:
        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            return False, "No hay conexion a la base de datos"
        cursor = cone.cursor()
        own_conn = True
    try:
        cursor.execute("SELECT stock_inicial FROM productos WHERE id=%s", (producto_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Producto no existe"
        stock = int(row[0] or 0)
        cursor.execute(
            """
            SELECT tipo, cantidad
            FROM movimientos_stock
            WHERE producto_id=%s
            ORDER BY creado_en ASC, id ASC
            """,
            (producto_id,)
        )
        for tipo, cantidad in cursor.fetchall():
            tipo = str(tipo or "").lower()
            cantidad = int(cantidad or 0)
            if tipo in ("entrada", "devolucion"):
                stock += cantidad
            elif tipo in ("salida", "venta"):
                stock -= cantidad
            elif tipo == "ajuste":
                stock = cantidad
        if stock < 0:
            stock = 0
        cursor.execute("UPDATE productos SET cantidad=%s WHERE id=%s", (stock, producto_id))
        return True, None
    except Exception as exc:
        log_error(f"Stock.recalcular_stock: {exc}")
        return False, "No se pudo recalcular stock"
    finally:
        if own_conn:
            try:
                cursor.connection.close()
            except Exception:
                pass


def _build_stock_tab(parent, base):
    groupbox = tk.LabelFrame(
        parent,
        text="Control de stock",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    groupbox.pack(fill="both", expand=True)

    header = tk.Frame(groupbox, bg=BG_CARD)
    header.pack(fill="x", pady=(0, 10))

    tk.Label(
        header,
        text="Estado del stock (verde: OK, amarillo: medio, rojo: bajo)",
        bg=BG_CARD,
        fg=FG_MUTED,
        font=("Segoe UI", 9)
    ).pack(side="left")

    summary = tk.Frame(groupbox, bg=BG_CARD)
    summary.pack(fill="x", pady=(0, 8))
    lbl_total = tk.Label(summary, text="Productos: 0", bg=BG_BUTTON, fg=FG_TEXT, font=FONT_LABEL, padx=10, pady=4)
    lbl_total.pack(side="left", padx=(0, 10))
    lbl_bajo = tk.Label(summary, text="Bajo: 0", bg="#7f1d1d", fg=FG_TEXT, font=FONT_LABEL, padx=10, pady=4)
    lbl_bajo.pack(side="left", padx=(0, 10))
    lbl_medio = tk.Label(summary, text="Medio: 0", bg="#b45309", fg=FG_TEXT, font=FONT_LABEL, padx=10, pady=4)
    lbl_medio.pack(side="left", padx=(0, 10))
    lbl_ok = tk.Label(summary, text="Ok: 0", bg="#166534", fg=FG_TEXT, font=FONT_LABEL, padx=10, pady=4)
    lbl_ok.pack(side="left")

    search_row = tk.Frame(groupbox, bg=BG_CARD)
    search_row.pack(fill="x", pady=(0, 8))
    tk.Label(search_row, text="Buscar:", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).pack(side="left")
    search_entry = tk.Entry(search_row, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat")
    search_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=2)

    tree_wrap = tk.Frame(groupbox, bg=BG_CARD)
    tree_wrap.pack(fill="both", expand=True)
    tree_wrap.grid_columnconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(1, weight=0)

    tree = ttk.Treeview(
        tree_wrap,
        columns=("Id", "Nombre", "Stock", "Inicial", "%", "Estado", "Fecha ingreso"),
        show="headings",
        height=12,
        style="Dark.Treeview"
    )
    tree.column("# 1", anchor=tk.CENTER, width=60, stretch=True)
    tree.heading("# 1", text="Id", anchor=tk.CENTER)
    tree.column("# 2", anchor=tk.CENTER, width=200, stretch=True)
    tree.heading("# 2", text="Nombre", anchor=tk.CENTER)
    tree.column("# 3", anchor=tk.CENTER, width=80, stretch=True)
    tree.heading("# 3", text="Stock", anchor=tk.CENTER)
    tree.column("# 4", anchor=tk.CENTER, width=80, stretch=True)
    tree.heading("# 4", text="Inicial", anchor=tk.CENTER)
    tree.column("# 5", anchor=tk.CENTER, width=60, stretch=True)
    tree.heading("# 5", text="%", anchor=tk.CENTER)
    tree.column("# 6", anchor=tk.CENTER, width=80, stretch=True)
    tree.heading("# 6", text="Estado", anchor=tk.CENTER)
    tree.column("# 7", anchor=tk.CENTER, width=140, stretch=True)
    tree.heading("# 7", text="Fecha ingreso", anchor=tk.CENTER)
    tree.tag_configure("empty", foreground=FG_MUTED)
    configurar_orden_treeview(tree, numeric_cols={"Id", "Stock", "Inicial", "%"})

    tree.tag_configure("low", background="#7f1d1d", foreground=FG_TEXT)
    tree.tag_configure("mid", background="#b45309", foreground=FG_TEXT)
    tree.tag_configure("ok", background="#166534", foreground=FG_TEXT)

    scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview, style="Dark.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")

    def refresh(filtro=None, silent=False):
        if tree is None or (hasattr(tree, "winfo_exists") and not tree.winfo_exists()):
            return
        selected = tree.item(tree.focus(), "values")
        selected_id = selected[0] if selected else None
        tree.delete(*tree.get_children())
        rows, err = _load_stock(filtro)
        if err:
            if not silent:
                dialog_error(base, "Error", err)
            return
        count = 0
        low = mid = ok = 0
        for row in rows:
            stock_actual = int(row[2])
            stock_inicial = int(row[3]) if row[3] is not None else 0
            porcentaje, estado = _calc_estado(stock_actual, stock_inicial)
            values = [
                row[0],
                row[1],
                stock_actual,
                stock_inicial,
                f"{porcentaje}%",
                estado,
                _fmt_fecha(row[4]),
            ]
            tag = "ok"
            if porcentaje <= 30:
                tag = "low"
                low += 1
            elif porcentaje <= 54:
                tag = "mid"
                mid += 1
            else:
                ok += 1
            item = tree.insert("", "end", values=values, tags=(tag,))
            count += 1
            if selected_id is not None and str(values[0]) == str(selected_id):
                tree.selection_set(item)
                tree.focus(item)
                tree.see(item)
        if count == 0:
            treeview_set_empty(tree)
        try:
            lbl_total.config(text=f"Productos: {count}")
            lbl_bajo.config(text=f"Bajo: {low}")
            lbl_medio.config(text=f"Medio: {mid}")
            lbl_ok.config(text=f"Ok: {ok}")
        except Exception:
            pass

    def _delete_selected():
        item = tree.focus()
        if not item:
            dialog_error(base, "Error", "Selecciona un producto")
            return
        values = tree.item(item, "values")
        if not values:
            dialog_error(base, "Error", "Selecciona un producto")
            return
        prod_id = values[0]
        if not dialog_confirm(base, "Confirmar", f"Eliminar producto {prod_id}?"):
            return
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                dialog_error(base, "Error", "No hay conexion a la base de datos")
                return
            cursor = cone.cursor()
            try:
                cone.start_transaction()
            except Exception:
                pass
            cursor.execute("DELETE FROM movimientos_stock WHERE producto_id=%s", (prod_id,))
            cursor.execute("DELETE FROM ventas WHERE id=%s", (prod_id,))
            cursor.execute("DELETE FROM productos WHERE id=%s", (prod_id,))
            cone.commit()
            cone.close()
            log_info(f"Stock.eliminar: producto {prod_id}")
            dialog_info(base, "Informacion", "Producto eliminado")
            refresh(search_entry.get().strip())
        except Exception as exc:
            log_error(f"Stock.eliminar: {exc}")
            dialog_error(base, "Error", "No se pudo eliminar el producto")

    dark_button(header, "Eliminar", _delete_selected, variant="danger").pack(side="right", padx=8)
    dark_button(header, "Actualizar", lambda: refresh(search_entry.get().strip()), primary=True).pack(side="right")

    headers = ["Id", "Nombre", "Stock", "Inicial", "%", "Estado", "Fecha ingreso"]
    dark_button(search_row, "Exportar CSV", lambda: exportar_treeview_csv(tree, headers, "stock")).pack(side="right")
    def _export_pdf_stock():
        ok, msg = exportar_treeview_pdf(tree, headers, "Reporte de Stock", "stock")
        if not ok and msg and msg != "Cancelado":
            dialog_error(base, "Error", msg)
    dark_button(search_row, "Exportar PDF", _export_pdf_stock).pack(side="right", padx=6)

    def _do_search():
        refresh(search_entry.get().strip())

    def _clear_search():
        search_entry.delete(0, tk.END)
        refresh()

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

    refresh()

    def _auto_refresh():
        try:
            filtro = search_entry.get().strip()
        except Exception:
            filtro = None
        refresh(filtro, silent=True)

    schedule_autorefresh(parent, _auto_refresh, interval_ms=4000)
    register_activity(parent)
    return refresh


def _build_movimientos_tab(parent, base, refresh_stock):
    form = tk.LabelFrame(
        parent,
        text="Registrar movimiento",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    form.pack(fill="x", padx=0, pady=(0, 12))

    tk.Label(form, text="Id Producto:", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).grid(row=0, column=0, sticky="w", pady=4)
    entry_id = tk.Entry(form, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat")
    entry_id.grid(row=0, column=1, sticky="ew", padx=6, pady=4, ipady=2)

    tk.Label(form, text="Tipo:", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).grid(row=0, column=2, sticky="w", pady=4)
    combo_tipo = ttk.Combobox(
        form,
        values=("entrada", "salida", "ajuste", "devolucion"),
        state="readonly",
        style="Dark.TCombobox"
    )
    combo_tipo.grid(row=0, column=3, sticky="ew", padx=6, pady=4)
    combo_tipo.set("entrada")

    tk.Label(form, text="Cantidad:", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).grid(row=1, column=0, sticky="w", pady=4)
    entry_cantidad = tk.Entry(form, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat")
    entry_cantidad.grid(row=1, column=1, sticky="ew", padx=6, pady=4, ipady=2)

    tk.Label(form, text="Nota:", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).grid(row=1, column=2, sticky="w", pady=4)
    entry_nota = tk.Entry(form, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat")
    entry_nota.grid(row=1, column=3, sticky="ew", padx=6, pady=4, ipady=2)

    form.grid_columnconfigure(1, weight=1)
    form.grid_columnconfigure(3, weight=1)

    btn_row = tk.Frame(form, bg=BG_CARD)
    btn_row.grid(row=2, column=0, columnspan=4, pady=(8, 0), sticky="e")

    history = tk.LabelFrame(
        parent,
        text="Historial de movimientos",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    history.pack(fill="both", expand=True)

    search_row = tk.Frame(history, bg=BG_CARD)
    search_row.pack(fill="x", pady=(0, 8))
    tk.Label(search_row, text="Buscar:", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).pack(side="left")
    search_entry = tk.Entry(search_row, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat")
    search_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=2)
    actions_row = tk.Frame(history, bg=BG_CARD)
    actions_row.pack(fill="x", pady=(0, 8))

    tree_wrap = tk.Frame(history, bg=BG_CARD)
    tree_wrap.pack(fill="both", expand=True)
    tree_wrap.grid_columnconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(1, weight=0)

    tree = ttk.Treeview(
        tree_wrap,
        columns=("Id", "Producto", "Nombre", "Tipo", "Cantidad", "Nota", "Fecha"),
        show="headings",
        height=10,
        style="Dark.Treeview"
    )
    tree.column("# 1", anchor=tk.CENTER, width=60, stretch=False)
    tree.heading("# 1", text="Id", anchor=tk.CENTER)
    tree.column("# 2", anchor=tk.CENTER, width=90, stretch=False)
    tree.heading("# 2", text="Producto", anchor=tk.CENTER)
    tree.column("# 3", anchor=tk.CENTER, width=200, stretch=True)
    tree.heading("# 3", text="Nombre", anchor=tk.CENTER)
    tree.column("# 4", anchor=tk.CENTER, width=100, stretch=False)
    tree.heading("# 4", text="Tipo", anchor=tk.CENTER)
    tree.column("# 5", anchor=tk.CENTER, width=90, stretch=False)
    tree.heading("# 5", text="Cantidad", anchor=tk.CENTER)
    tree.column("# 6", anchor=tk.CENTER, width=220, stretch=True)
    tree.heading("# 6", text="Nota", anchor=tk.CENTER)
    tree.column("# 7", anchor=tk.CENTER, width=140, stretch=False)
    tree.heading("# 7", text="Fecha", anchor=tk.CENTER)
    tree.tag_configure("empty", foreground=FG_MUTED)
    configurar_orden_treeview(tree, numeric_cols={"Id", "Producto", "Cantidad"})

    scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview, style="Dark.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")

    headers = ["Id", "Producto", "Nombre", "Tipo", "Cantidad", "Nota", "Fecha"]
    dark_button(search_row, "Exportar CSV", lambda: exportar_treeview_csv(tree, headers, "movimientos_stock")).pack(side="right")
    def _export_pdf_mov():
        ok, msg = exportar_treeview_pdf(tree, headers, "Reporte de Movimientos", "movimientos_stock")
        if not ok and msg and msg != "Cancelado":
            dialog_error(base, "Error", msg)
    dark_button(search_row, "Exportar PDF", _export_pdf_mov).pack(side="right", padx=6)

    def _delete_selected():
        item = tree.focus()
        if not item:
            dialog_error(base, "Error", "Selecciona un movimiento")
            return
        values = tree.item(item, "values")
        if not values or str(values[0]).lower() == "sin resultados":
            dialog_error(base, "Error", "Selecciona un movimiento")
            return
        mov_id = values[0]
        if not dialog_confirm(base, "Confirmar", f"Eliminar movimiento {mov_id}?"):
            return
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                dialog_error(base, "Error", "No hay conexion a la base de datos")
                return
            cursor = cone.cursor()
            try:
                cone.start_transaction()
                cursor.execute(
                    "SELECT producto_id FROM movimientos_stock WHERE id=%s",
                    (mov_id,)
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError("Movimiento no existe")
                producto_id = row[0]

                cursor.execute("DELETE FROM movimientos_stock WHERE id=%s", (mov_id,))
                ok, msg = _recalcular_stock(producto_id, cursor=cursor)
                if not ok:
                    raise ValueError(msg or "No se pudo recalcular stock")
                cone.commit()
            except ValueError as ve:
                try:
                    cone.rollback()
                except Exception:
                    pass
                dialog_error(base, "Error", str(ve))
                cone.close()
                return
            except Exception as exc:
                try:
                    cone.rollback()
                except Exception:
                    pass
                log_error(f"Stock.movimientos.eliminar: {exc}")
                dialog_error(base, "Error", "No se pudo eliminar el movimiento")
                cone.close()
                return
            cone.close()
            log_info(f"Stock.movimientos.eliminar: id={mov_id}")
            refresh_movimientos(search_entry.get().strip())
        except Exception as exc:
            log_error(f"Stock.movimientos.eliminar: {exc}")
            dialog_error(base, "Error", "No se pudo eliminar el movimiento")

    def refresh_movimientos(filtro=None, silent=False):
        if tree is None or (hasattr(tree, "winfo_exists") and not tree.winfo_exists()):
            return
        selected = tree.item(tree.focus(), "values")
        selected_id = selected[0] if selected else None
        tree.delete(*tree.get_children())
        rows, err = _load_movimientos(filtro)
        if err:
            if not silent:
                dialog_error(base, "Error", err)
            return
        count = 0
        for row in rows:
            values = [
                row[0],
                row[1],
                row[2] or "-",
                row[3],
                row[4],
                row[5] or "",
                _fmt_fecha(row[6]),
            ]
            item = tree.insert("", "end", values=values)
            count += 1
            if selected_id is not None and str(values[0]) == str(selected_id):
                tree.selection_set(item)
                tree.focus(item)
                tree.see(item)
        if count == 0:
            treeview_set_empty(tree)

    def _registrar():
        producto_id = entry_id.get().strip()
        tipo = combo_tipo.get().strip().lower()
        cantidad_txt = entry_cantidad.get().strip()
        nota = entry_nota.get().strip() or None

        ok, _ = campos_requeridos(producto_id=producto_id, tipo=tipo, cantidad=cantidad_txt)
        if not ok:
            dialog_error(base, "Error", "Por favor completar todos los campos")
            return
        ok_id, msg_id = validar_id(producto_id, "Id Producto")
        if not ok_id:
            dialog_error(base, "Error", msg_id)
            return

        if tipo == "ajuste":
            cantidad = parse_int(cantidad_txt, min_value=0, allow_zero=True)
        else:
            cantidad = parse_int(cantidad_txt, min_value=1, allow_zero=False)
        if cantidad is None:
            dialog_error(base, "Error", "Cantidad invalida")
            return

        ok, err = registrar_movimiento(producto_id, tipo, cantidad, nota=nota, aplicar_stock=True)
        if not ok:
            dialog_error(base, "Error", err or "No se pudo registrar el movimiento")
            return

        dialog_info(base, "Informacion", "Movimiento registrado")
        entry_id.delete(0, tk.END)
        entry_cantidad.delete(0, tk.END)
        entry_nota.delete(0, tk.END)
        combo_tipo.set("entrada")
        refresh_stock()
        refresh_movimientos(search_entry.get().strip())

    def _do_search():
        refresh_movimientos(search_entry.get().strip())

    def _clear_search():
        search_entry.delete(0, tk.END)
        refresh_movimientos()

    dark_button(btn_row, "Registrar", _registrar, primary=True).pack(side="right")
    dark_button(btn_row, "Limpiar", lambda: (entry_id.delete(0, tk.END), entry_cantidad.delete(0, tk.END), entry_nota.delete(0, tk.END), combo_tipo.set("entrada"))).pack(side="right", padx=6)
    dark_button(actions_row, "Eliminar seleccionado", _delete_selected, variant="danger").pack(side="right")
    dark_button(search_row, "Buscar", _do_search).pack(side="left", padx=4)
    dark_button(search_row, "Limpiar", _clear_search).pack(side="left")
    search_entry.bind("<Return>", lambda e: _do_search())

    refresh_movimientos()

    def _auto_refresh_mov():
        try:
            filtro = search_entry.get().strip()
        except Exception:
            filtro = None
        refresh_movimientos(filtro, silent=True)

    schedule_autorefresh(parent, _auto_refresh_mov, interval_ms=4000)
    register_activity(parent)
    return refresh_movimientos


def _build_reportes_tab(parent, base):
    def _badge(parent, text, bg):
        lbl = tk.Label(parent, text=text, bg=bg, fg=FG_TEXT, font=FONT_LABEL, padx=10, pady=4)
        lbl.pack(side="left", padx=(0, 10))
        return lbl

    card = tk.LabelFrame(
        parent,
        text="Reportes de stock",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    card.pack(fill="both", expand=True)

    summary = tk.Frame(card, bg=BG_CARD)
    summary.pack(fill="x", pady=(0, 10))
    lbl_total = _badge(summary, "Productos: 0", BG_BUTTON)
    lbl_low = _badge(summary, "Bajo: 0", "#7f1d1d")
    lbl_mid = _badge(summary, "Medio: 0", "#b45309")
    lbl_ok = _badge(summary, "Ok: 0", "#166534")

    tree_wrap = tk.Frame(card, bg=BG_CARD)
    tree_wrap.pack(fill="both", expand=True)
    tree_wrap.grid_columnconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_rowconfigure(1, weight=0)

    tree = ttk.Treeview(
        tree_wrap,
        columns=("Id", "Nombre", "Stock", "Inicial", "%", "Estado"),
        show="headings",
        height=12,
        style="Dark.Treeview"
    )
    tree.column("# 1", anchor=tk.CENTER, width=60, stretch=True)
    tree.heading("# 1", text="Id", anchor=tk.CENTER)
    tree.column("# 2", anchor=tk.CENTER, width=220, stretch=True)
    tree.heading("# 2", text="Nombre", anchor=tk.CENTER)
    tree.column("# 3", anchor=tk.CENTER, width=90, stretch=True)
    tree.heading("# 3", text="Stock", anchor=tk.CENTER)
    tree.column("# 4", anchor=tk.CENTER, width=90, stretch=True)
    tree.heading("# 4", text="Inicial", anchor=tk.CENTER)
    tree.column("# 5", anchor=tk.CENTER, width=60, stretch=True)
    tree.heading("# 5", text="%", anchor=tk.CENTER)
    tree.column("# 6", anchor=tk.CENTER, width=90, stretch=True)
    tree.heading("# 6", text="Estado", anchor=tk.CENTER)
    tree.tag_configure("empty", foreground=FG_MUTED)
    tree.tag_configure("low", background="#7f1d1d", foreground=FG_TEXT)
    tree.tag_configure("mid", background="#b45309", foreground=FG_TEXT)
    tree.tag_configure("ok", background="#166534", foreground=FG_TEXT)

    scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview, style="Dark.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")

    def _refresh(silent=False):
        def _work():
            tree.delete(*tree.get_children())
            rows, err = _load_stock()
            if err:
                if not silent:
                    dialog_error(base, "Error", err)
                return
            count = low = mid = ok = 0
            for row in rows or []:
                stock_actual = int(row[2])
                stock_inicial = int(row[3]) if row[3] is not None else 0
                porcentaje, estado = _calc_estado(stock_actual, stock_inicial)
                values = [row[0], row[1], stock_actual, stock_inicial, f"{porcentaje}%", estado]
                tag = "ok"
                if porcentaje <= 30:
                    tag = "low"
                    low += 1
                elif porcentaje <= 54:
                    tag = "mid"
                    mid += 1
                else:
                    ok += 1
                tree.insert("", "end", values=values, tags=(tag,))
                count += 1
            if count == 0:
                treeview_set_empty(tree)
            lbl_total.config(text=f"Productos: {count}")
            lbl_low.config(text=f"Bajo: {low}")
            lbl_mid.config(text=f"Medio: {mid}")
            lbl_ok.config(text=f"Ok: {ok}")
        if silent:
            _work()
        else:
            run_with_loading(base, "Cargando...", _work)

    btn_row = tk.Frame(card, bg=BG_CARD)
    btn_row.pack(fill="x", pady=(10, 0))
    dark_button(btn_row, "Exportar CSV", lambda: exportar_treeview_csv(tree, ["Id", "Nombre", "Stock", "Inicial", "%", "Estado"], "stock_reporte")).pack(side="right")
    def _export_pdf():
        ok, msg = exportar_treeview_pdf(tree, ["Id", "Nombre", "Stock", "Inicial", "%", "Estado"], "Reporte de Stock", "stock_reporte")
        if not ok and msg and msg != "Cancelado":
            dialog_error(base, "Error", msg)
    dark_button(btn_row, "Exportar PDF", _export_pdf).pack(side="right", padx=6)
    dark_button(btn_row, "Actualizar", _refresh, primary=True).pack(side="right", padx=6)
    _refresh()

    ventas_card = tk.LabelFrame(
        parent,
        text="Reporte de ventas",
        padx=12,
        pady=12,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    ventas_card.pack(fill="both", expand=True, pady=(16, 0))

    filtros = tk.Frame(ventas_card, bg=BG_CARD)
    filtros.pack(fill="x", pady=(0, 10))
    tk.Label(filtros, text="Desde (YYYY-MM-DD):", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).pack(side="left")
    entry_desde = tk.Entry(filtros, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", width=12)
    entry_desde.pack(side="left", padx=6, ipady=2)
    tk.Label(filtros, text="Hasta (YYYY-MM-DD):", bg=BG_CARD, fg=FG_MUTED, font=FONT_LABEL).pack(side="left", padx=(10, 0))
    entry_hasta = tk.Entry(filtros, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", width=12)
    entry_hasta.pack(side="left", padx=6, ipady=2)

    hoy = datetime.now().date()
    desde_default = hoy - timedelta(days=7)
    entry_desde.insert(0, desde_default.strftime("%Y-%m-%d"))
    entry_hasta.insert(0, hoy.strftime("%Y-%m-%d"))

    resumen_ventas = tk.Frame(ventas_card, bg=BG_CARD)
    resumen_ventas.pack(fill="x", pady=(0, 8))
    lbl_v_total = _badge(resumen_ventas, "Ventas: 0", BG_BUTTON)
    lbl_v_unidades = _badge(resumen_ventas, "Unidades: 0", ACCENT)
    lbl_v_monto = _badge(resumen_ventas, "Total: $ 0.00", "#2563eb")

    ventas_wrap = tk.Frame(ventas_card, bg=BG_CARD)
    ventas_wrap.pack(fill="both", expand=True)
    ventas_wrap.grid_columnconfigure(0, weight=1)
    ventas_wrap.grid_rowconfigure(0, weight=1)
    ventas_wrap.grid_rowconfigure(1, weight=0)

    ventas_tree = ttk.Treeview(
        ventas_wrap,
        columns=("Id", "Nombre", "Precio", "Cantidad", "Fecha"),
        show="headings",
        height=10,
        style="Dark.Treeview"
    )
    ventas_tree.column("# 1", anchor=tk.CENTER, width=80, stretch=True)
    ventas_tree.heading("# 1", text="Id", anchor=tk.CENTER)
    ventas_tree.column("# 2", anchor=tk.CENTER, width=200, stretch=True)
    ventas_tree.heading("# 2", text="Nombre", anchor=tk.CENTER)
    ventas_tree.column("# 3", anchor=tk.CENTER, width=90, stretch=True)
    ventas_tree.heading("# 3", text="Precio", anchor=tk.CENTER)
    ventas_tree.column("# 4", anchor=tk.CENTER, width=90, stretch=True)
    ventas_tree.heading("# 4", text="Cantidad", anchor=tk.CENTER)
    ventas_tree.column("# 5", anchor=tk.CENTER, width=140, stretch=True)
    ventas_tree.heading("# 5", text="Fecha", anchor=tk.CENTER)
    ventas_tree.tag_configure("empty", foreground=FG_MUTED)
    configurar_orden_treeview(ventas_tree, numeric_cols={"Id", "Precio", "Cantidad"})

    v_scroll_y = ttk.Scrollbar(ventas_wrap, orient="vertical", command=ventas_tree.yview, style="Dark.Vertical.TScrollbar")
    v_scroll_x = ttk.Scrollbar(ventas_wrap, orient="horizontal", command=ventas_tree.xview, style="Dark.Horizontal.TScrollbar")
    ventas_tree.configure(yscrollcommand=v_scroll_y.set, xscrollcommand=v_scroll_x.set)
    ventas_tree.grid(row=0, column=0, sticky="nsew")
    v_scroll_y.grid(row=0, column=1, sticky="ns")
    v_scroll_x.grid(row=1, column=0, sticky="ew")

    def _refresh_ventas(silent=False):
        def _work():
            ventas_tree.delete(*ventas_tree.get_children())
            try:
                desde = datetime.strptime(entry_desde.get().strip(), "%Y-%m-%d")
                hasta = datetime.strptime(entry_hasta.get().strip(), "%Y-%m-%d")
            except Exception:
                if not silent:
                    dialog_error(base, "Error", "Formato de fecha invalido (YYYY-MM-DD)")
                return
            hasta = hasta.replace(hour=23, minute=59, second=59)
            try:
                cone = cconexion.cconexionBaseDeDatos()
                if cone is None:
                    if not silent:
                        dialog_error(base, "Error", "No hay conexion a la base de datos")
                    return
                cursor = cone.cursor()
                cursor.execute(
                    """
                    SELECT v.id, v.nombre, COALESCE(v.precio, p.precio), v.nro_ventas, v.fecha
                    FROM ventas v
                    LEFT JOIN productos p ON p.id = v.id
                    WHERE v.fecha >= %s AND v.fecha <= %s
                    ORDER BY v.fecha DESC
                    """,
                    (desde, hasta)
                )
                rows = cursor.fetchall() or []
                cone.close()
            except Exception as exc:
                if not silent:
                    dialog_error(base, "Error", f"No se pudo cargar ventas: {exc}")
                return

            total = unidades = 0
            monto = 0.0
            for row in rows:
                precio = float(row[2] or 0)
                cantidad = int(row[3] or 0)
                total += 1
                unidades += cantidad
                monto += precio * cantidad
                values = [row[0], row[1], f"$ {precio:.2f}".rstrip("0").rstrip("."), row[3], _fmt_fecha(row[4])]
                ventas_tree.insert("", "end", values=values)
            if not rows:
                treeview_set_empty(ventas_tree)
            lbl_v_total.config(text=f"Ventas: {total}")
            lbl_v_unidades.config(text=f"Unidades: {unidades}")
            lbl_v_monto.config(text=f"Total: $ {monto:.2f}")
        if silent:
            _work()
        else:
            run_with_loading(base, "Cargando...", _work)

    btn_ventas = tk.Frame(ventas_card, bg=BG_CARD)
    btn_ventas.pack(fill="x", pady=(10, 0))
    dark_button(btn_ventas, "Exportar CSV", lambda: exportar_treeview_csv(ventas_tree, ["Id", "Nombre", "Precio", "Cantidad", "Fecha"], "ventas_reporte")).pack(side="right")
    def _export_pdf_ventas():
        ok, msg = exportar_treeview_pdf(ventas_tree, ["Id", "Nombre", "Precio", "Cantidad", "Fecha"], "Reporte de Ventas", "ventas_reporte")
        if not ok and msg and msg != "Cancelado":
            dialog_error(base, "Error", msg)
    dark_button(btn_ventas, "Exportar PDF", _export_pdf_ventas).pack(side="right", padx=6)
    dark_button(btn_ventas, "Actualizar", _refresh_ventas, primary=True).pack(side="right", padx=6)

    _refresh_ventas()

    def _auto_refresh_reportes():
        _refresh(silent=True)
        _refresh_ventas(silent=True)

    schedule_autorefresh(parent, _auto_refresh_reportes, interval_ms=4000)
    register_activity(parent)

def stock_panel(parent):
    """Construye el panel de stock dentro de un contenedor."""
    base = parent.winfo_toplevel()
    apply_ttk_style(base)

    content = tk.Frame(parent, bg=BG_MAIN)
    content.pack(fill="both", expand=True)

    notebook = ttk.Notebook(content, style="Dark.TNotebook")
    notebook.pack(fill="both", expand=True, padx=16, pady=16)

    tab_stock = tk.Frame(notebook, bg=BG_MAIN)
    tab_mov = tk.Frame(notebook, bg=BG_MAIN)
    tab_reportes = tk.Frame(notebook, bg=BG_MAIN)
    notebook.add(tab_stock, text="Stock")
    notebook.add(tab_mov, text="Movimientos")
    notebook.add(tab_reportes, text="Reportes")

    refresh_stock = _build_stock_tab(tab_stock, base)
    _build_movimientos_tab(tab_mov, base, refresh_stock)
    _build_reportes_tab(tab_reportes, base)

    def _cleanup(_=None):
        global base
        base = None
    content.bind("<Destroy>", _cleanup)
    return content


def stockFormulario():
    base = tk.Toplevel()
    apply_chrome(base, "StockARG", 1320, 800, min_w=1100, min_h=650, state_key="stock")
    apply_ttk_style(base)
    stock_panel(base)
