"""Módulo de clientes: datos y UI."""

from Conexion import cconexion
import mysql.connector
from Logger import log_error, log_info


class CClientes:
    @staticmethod
    def mostrarClientes(filtro=None):
        """Obtiene lista de clientes."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return []
            cursor = cone.cursor()
            sql = "SELECT id, nombres, apellidos, sexo FROM usuarios"
            params = None
            if filtro:
                sql += " WHERE id LIKE %s OR nombres LIKE %s OR apellidos LIKE %s"
                like = f"%{filtro}%"
                params = (like, like, like)
            sql += ";"
            cursor.execute(sql, params or ())
            miResultado = cursor.fetchall()
            cone.commit()
            cone.close()
            return miResultado
        except mysql.connector.Error as error:
            log_error(f"Clientes.mostrarClientes: {error}")
            return []

    def existeCliente(idUsuario):
        """Valida si un cliente ya existe por ID."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False
            cursor = cone.cursor()
            cursor.execute("SELECT 1 FROM usuarios WHERE id=%s", (idUsuario,))
            existe = cursor.fetchone() is not None
            cone.close()
            return existe
        except mysql.connector.Error as error:
            log_error(f"Clientes.existeCliente: {error}")
            return False

    def ingresarClientes(idUsuario, nombres, apellidos, sexo):
        """Inserta un cliente en la base."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            sql = "insert into usuarios values(%s,%s,%s,%s)"
            valores = (idUsuario, nombres, apellidos, sexo)
            cursor.execute(sql, valores)
            cone.commit()
            log_info(f"Clientes.ingresarClientes: {cursor.rowcount} registro(s)")
            cone.close()
            return True, None
        except mysql.connector.Error as error:
            log_error(f"Clientes.ingresarClientes: {error}")
            return False, "Error al guardar el cliente"

    def modificarClientes(idUsuario, nombres, apellidos, sexo):
        """Actualiza un cliente existente."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            sql = "UPDATE usuarios set usuarios.nombres =%s, usuarios.apellidos =%s, usuarios.sexo =%s Where usuarios.id =%s;"
            valores = (nombres, apellidos, sexo, idUsuario)
            cursor.execute(sql, valores)
            cone.commit()
            log_info(f"Clientes.modificarClientes: {cursor.rowcount} registro(s)")
            cone.close()
            return True, None
        except mysql.connector.Error as error:
            log_error(f"Clientes.modificarClientes: {error}")
            return False, "Error al actualizar el cliente"

    def eliminarClientes(idUsuario):
        """Elimina un cliente por ID."""
        try:
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                return False, "No hay conexion a la base de datos"
            cursor = cone.cursor()
            sql = "DELETE from usuarios WHERE usuarios.id=%s;"
            valores = (idUsuario,)
            cursor.execute(sql, valores)
            cone.commit()
            log_info(f"Clientes.eliminarClientes: {cursor.rowcount} registro(s)")
            cone.close()
            return True, None
        except mysql.connector.Error as error:
            log_error(f"Clientes.eliminarClientes: {error}")
            return False, "Error al eliminar el cliente"


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
    exportar_treeview_csv,
    exportar_treeview_pdf,
    configurar_orden_treeview,
    treeview_set_empty,
    run_with_loading,
    schedule_autorefresh,
    importar_csv,
    validar_id,
    widget_alive,
    register_activity,
)


class FormularioClientes:
    global texboxId
    texboxId = None

    global texboxNombre
    texboxNombre = None

    global texboxApellido
    texboxApellido = None

    global base
    base = None

    global combo
    combo = None

    global groupbox
    groupbox = None

    global tree
    tree = None

    global lbl_total_clientes
    lbl_total_clientes = None

    import tkinter as tk


def clientes_panel(parent):
    """Construye el panel de clientes dentro de un contenedor."""
    global texboxId
    global texboxNombre
    global texboxApellido
    global groupbox
    global tree
    global combo
    global base
    global lbl_total_clientes

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
        text="Datos de los clientes",
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

    labelId = Label(groupbox, text="Id Cliente:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    labelId.grid(row=0, column=0, sticky="w", pady=4)
    texboxId = Entry(
        groupbox,
        bg=BG_INPUT,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT,
        readonlybackground=BG_INPUT,
        disabledforeground=FG_TEXT
    )
    texboxId.grid(row=0, column=1, pady=4, ipadx=6, ipady=4)

    labelNombre = Label(groupbox, text="Nombre:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    labelNombre.grid(row=1, column=0, sticky="w", pady=4)
    texboxNombre = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxNombre.grid(row=1, column=1, pady=4, ipadx=6, ipady=4)

    labelApellido = Label(groupbox, text="Apellido:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    labelApellido.grid(row=2, column=0, sticky="w", pady=4)
    texboxApellido = Entry(groupbox, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat", font=FONT_INPUT)
    texboxApellido.grid(row=2, column=1, pady=4, ipadx=6, ipady=4)

    labelSexo = Label(groupbox, text="Sexo:", width=15, font=FONT_LABEL, bg=BG_CARD, fg=FG_MUTED)
    labelSexo.grid(row=3, column=0, sticky="w", pady=4)
    seleccionSexo = tk.StringVar()
    combo = ttk.Combobox(
        groupbox,
        values=["Masculino", "Femenino"],
        textvariable=seleccionSexo,
        style="Dark.TCombobox"
    )
    combo.grid(row=3, column=1, pady=4, ipadx=6, ipady=2, sticky="ew")
    seleccionSexo.set("Masculino")

    btn_row = tk.Frame(groupbox, bg=BG_CARD)
    btn_row.grid(row=4, column=0, columnspan=2, pady=(10, 0))


    def _limpiar_form():
        texboxId.config(state="normal")
        texboxId.delete(0, END)
        texboxNombre.delete(0, END)
        texboxApellido.delete(0, END)
        combo.set("Masculino")
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
            id_txt = texboxId.get().strip()
            nombre_txt = texboxNombre.get().strip()
            apellido_txt = texboxApellido.get().strip()
            sexo_txt = combo.get().strip()
            is_selected = texboxId.cget("state") == "readonly"
            required_ok = all([id_txt, nombre_txt, apellido_txt, sexo_txt])
            _set_guardar_state((not is_selected and required_ok))
            btn_editar.config(state="normal" if (is_selected and required_ok) else "disabled")
            btn_eliminar.config(state="normal" if (is_selected and id_txt) else "disabled")
        except Exception:
            pass

    for w in (texboxId, texboxNombre, texboxApellido):
        w.bind("<KeyRelease>", lambda e: _update_buttons())
    combo.bind("<<ComboboxSelected>>", lambda e: _update_buttons())

    groupbox = LabelFrame(
        content,
        text="Lista de clientes",
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
    lbl_total_clientes = tk.Label(summary_row, text="Clientes: 0", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE)
    lbl_total_clientes.pack(side="left")

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
        columns=("Id Cliente", "Nombre", "Apellido", "Sexo"),
        show="headings",
        height=8,
        style="Dark.Treeview"
    )
    tree.column("# 1", anchor=CENTER, stretch=True)
    tree.heading("# 1", text="Id Cliente")
    tree.column("# 2", anchor=CENTER, stretch=True)
    tree.heading("# 2", text="Nombre")
    tree.column("# 3", anchor=CENTER, stretch=True)
    tree.heading("# 3", text="Apellido")
    tree.column("# 4", anchor=CENTER, stretch=True)
    tree.heading("# 4", text="Sexo")
    tree.tag_configure("empty", foreground=FG_MUTED)
    configurar_orden_treeview(tree, numeric_cols={"Id Cliente"})

    tree.bind("<<TreeviewSelect>>", seleccionarRegistro)
    scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview, style="Dark.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")

    headers = ["Id Cliente", "Nombre", "Apellido", "Sexo"]
    dark_button(search_row, "Exportar CSV", lambda: exportar_treeview_csv(tree, headers, "clientes")).pack(side="right")
    def _export_pdf():
        ok, msg = exportar_treeview_pdf(tree, headers, "Reporte de Clientes", "clientes")
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
                cid, nombre, apellido, sexo = row[0], row[1], row[2], row[3]
                if CClientes.existeCliente(cid):
                    skipped += 1
                    errors.append(f"Fila {idx}: id duplicado")
                    continue
                ok, msg = CClientes.ingresarClientes(cid, nombre, apellido, sexo)
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

    spacer = tk.Frame(content, bg=BG_MAIN)
    spacer.grid(row=1, column=1, padx=16, pady=(0, 16), sticky="nsew")

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
        global texboxId, texboxNombre, texboxApellido, combo, groupbox, tree, base, lbl_total_clientes
        texboxId = None
        texboxNombre = None
        texboxApellido = None
        combo = None
        groupbox = None
        tree = None
        base = None
        lbl_total_clientes = None
    content.bind("<Destroy>", _cleanup)
    return content


def clientesFormulario():
    """Construye la ventana de clientes."""
    global base
    try:
        base = Toplevel()
        apply_chrome(base, "StockARG", 1320, 800, min_w=1100, min_h=650, state_key="clientes")
        apply_ttk_style(base)
        clientes_panel(base)
        return
    except ValueError as error:
        log_error(f"Clientes.clientesFormulario: {error}")


def guardarRegistros():
    """Guarda un cliente nuevo."""
    def _work():
        global texboxId, texboxNombre, texboxApellido, combo, groupbox
        try:
            if texboxId is None or texboxNombre is None or texboxApellido is None or combo is None:
                log_error("Clientes.guardarRegistros: widgets no inicializados")
                return
            idUsuario = texboxId.get().strip()
            nombre = texboxNombre.get().strip()
            apellido = texboxApellido.get().strip()
            sexo = combo.get().strip()
            ok_id, msg_id = validar_id(idUsuario, "Id Cliente")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(id=idUsuario, nombre=nombre, apellido=apellido, sexo=sexo)
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            if CClientes.existeCliente(idUsuario):
                dialog_error(base, "Error", "El Id ya existe")
                return
            ok, msg = CClientes.ingresarClientes(idUsuario, nombre, apellido, sexo)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo guardar el cliente")
                return
            dialog_info(base, "Informacion", "Los datos fueron guardados")

            actualizarTreeView()

            texboxNombre.delete(0, END)
            texboxApellido.delete(0, END)
            texboxId.config(state="normal")
        except ValueError as error:
            log_error(f"Clientes.guardarRegistros: {error}")

    return run_with_loading(base, "Guardando...", _work)


def actualizarTreeView(filtro=None, silent=False):
    """Refresca el listado de clientes."""
    def _work():
        global tree
        try:
            if tree is None or (hasattr(tree, "winfo_exists") and not tree.winfo_exists()):
                return
            selected = tree.item(tree.focus(), "values")
            selected_id = selected[0] if selected else None
            tree.delete(*tree.get_children())
            rows = CClientes.mostrarClientes(filtro) or []
            count = 0
            for row in rows:
                item = tree.insert("", "end", values=row)
                count += 1
                if selected_id is not None and str(row[0]) == str(selected_id):
                    tree.selection_set(item)
                    tree.focus(item)
                    tree.see(item)
            if count == 0:
                treeview_set_empty(tree)
            try:
                if lbl_total_clientes is not None:
                    lbl_total_clientes.config(text=f"Clientes: {count}")
            except Exception:
                pass
        except ValueError as error:
            log_error(f"Clientes.actualizarTreeView: {error}")

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
                texboxId.config(state="normal")
                try:
                    _update_buttons()
                except Exception:
                    pass
                return

            texboxId.delete(0, END)
            texboxId.insert(0, values[0])
            texboxId.config(state="readonly")
            texboxNombre.delete(0, END)
            texboxNombre.insert(0, values[1])
            texboxApellido.delete(0, END)
            texboxApellido.insert(0, values[2])
            combo.set(values[3])
            try:
                _update_buttons()
            except Exception:
                pass
    except ValueError as error:
        log_error(f"Clientes.seleccionarRegistro: {error}")


def modificarRegistros():
    """Edita un cliente existente."""
    def _work():
        global texboxId, texboxNombre, texboxApellido, combo, groupbox
        try:
            if texboxId is None or texboxNombre is None or texboxApellido is None or combo is None:
                log_error("Clientes.modificarRegistros: widgets no inicializados")
                return
            idUsuario = texboxId.get().strip()
            nombre = texboxNombre.get().strip()
            apellido = texboxApellido.get().strip()
            sexo = combo.get().strip()
            ok_id, msg_id = validar_id(idUsuario, "Id Cliente")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(id=idUsuario, nombre=nombre, apellido=apellido, sexo=sexo)
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            ok, msg = CClientes.modificarClientes(idUsuario, nombre, apellido, sexo, )
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo actualizar el cliente")
                return
            dialog_info(base, "Informacion", "Los datos fueron actualizados")

            actualizarTreeView()

            texboxId.config(state="normal")
            texboxId.delete(0, END)
            texboxNombre.delete(0, END)
            texboxApellido.delete(0, END)
        except ValueError as error:
            log_error(f"Clientes.modificarRegistros: {error}")

    return run_with_loading(base, "Actualizando...", _work)


def eliminarRegistros():
    """Elimina el cliente indicado."""
    def _work():
        global texboxId, texboxNombre, texboxApellido
        try:
            if texboxId is None:
                log_error("Clientes.eliminarRegistros: widgets no inicializados")
                return
            idUsuario = texboxId.get().strip()
            ok_id, msg_id = validar_id(idUsuario, "Id Cliente")
            if not ok_id:
                dialog_error(base, "Error", msg_id)
                return
            ok, _ = campos_requeridos(id=idUsuario)
            if not ok:
                dialog_error(base, "Error", "Por favor completar todos los campos")
                return
            ok, msg = CClientes.eliminarClientes(idUsuario)
            if not ok:
                dialog_error(base, "Error", msg or "No se pudo eliminar el cliente")
                return
            dialog_info(base, "Informacion", "Los datos fueron eliminados")

            actualizarTreeView()

            texboxId.config(state="normal")
            texboxId.delete(0, END)
            texboxNombre.delete(0, END)
            texboxApellido.delete(0, END)
        except ValueError as error:
            log_error(f"Clientes.eliminarRegistros: {error}")

    return run_with_loading(base, "Eliminando...", _work)


if __name__ == "__main__":
    clientesFormulario()
    tk.mainloop()
