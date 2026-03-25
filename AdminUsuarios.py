"""Administración básica de usuarios."""

import tkinter as tk
from tkinter import ttk
from Dialogs import dialog_confirm, dialog_error
from Conexion import cconexion
from Theme import (
    BG_MAIN,
    BG_CARD,
    BG_BUTTON,
    BG_BUTTON_HOVER,
    ACCENT,
    ACCENT_HOVER,
    FG_TEXT,
    FG_MUTED,
    BORDER,
    FONT_TITLE,
    FONT_BUTTON,
    FONT_SUBTITLE,
    dark_button,
    apply_chrome,
    apply_ttk_style,
)
from Utils import exportar_lista_csv, schedule_autorefresh, register_activity


def admin_panel(parent):
    """Panel embebido para listar y eliminar usuarios."""
    base = parent.winfo_toplevel()
    apply_ttk_style(base)

    content = tk.Frame(parent, bg=BG_MAIN)
    content.pack(fill="both", expand=True)
    content.grid_columnconfigure(0, weight=1)
    content.grid_rowconfigure(0, weight=1)
    content.grid_rowconfigure(1, weight=1)

    card = tk.Frame(
        content,
        bg=BG_CARD,
        padx=16,
        pady=16,
        highlightbackground=BORDER,
        highlightthickness=1
    )
    card.grid(row=0, column=0, padx=16, pady=16, sticky="new")

    tk.Label(
        card,
        text="Administracion de Usuarios",
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_TITLE
    ).pack(anchor="w", pady=(0, 10))

    tk.Label(
        card,
        text="Selecciona un usuario para eliminarlo",
        bg=BG_CARD,
        fg=FG_MUTED,
        font=FONT_SUBTITLE
    ).pack(anchor="w", pady=(0, 10))

    search_row = tk.Frame(card, bg=BG_CARD)
    search_row.pack(fill="x", pady=(0, 8))
    tk.Label(search_row, text="Buscar:", bg=BG_CARD, fg=FG_MUTED, font=FONT_SUBTITLE).pack(side="left")
    search_entry = tk.Entry(search_row, bg=BG_MAIN, fg=FG_TEXT, insertbackground=FG_TEXT, relief="flat")
    search_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=2)

    list_wrap = tk.Frame(card, bg=BG_CARD)
    list_wrap.pack(fill="both", expand=True, pady=(0, 12))
    list_wrap.grid_columnconfigure(0, weight=1)
    list_wrap.grid_rowconfigure(0, weight=1)

    listbox = tk.Listbox(
        list_wrap,
        width=90,
        height=14,
        bg=BG_MAIN,
        fg=FG_TEXT,
        selectbackground=ACCENT,
        selectforeground=FG_TEXT,
        highlightbackground=BORDER,
        highlightthickness=1,
        relief="flat"
    )
    scroll_y = ttk.Scrollbar(list_wrap, orient="vertical", command=listbox.yview, style="Dark.Vertical.TScrollbar")
    listbox.configure(yscrollcommand=scroll_y.set)
    listbox.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")

    def cargar_usuarios(filtro=None, silent=False):
        seleccion = listbox.curselection()
        seleccionado = listbox.get(seleccion[0]) if seleccion else None
        listbox.delete(0, tk.END)

        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            if not silent:
                dialog_error(base, "Error", "No hay conexión a la base de datos")
            return
        cursor = cone.cursor()

        sql = """
            SELECT id, email, verificado, es_admin
            FROM usuarios_login
        """
        params = None
        if filtro:
            sql += " WHERE email LIKE %s OR id LIKE %s"
            like = f"%{filtro}%"
            params = (like, like)
        cursor.execute(sql, params or ())

        rows = cursor.fetchall()
        for u in rows:
            texto = f"ID:{u[0]} | {u[1]} | Verificado:{u[2]} | Admin:{u[3]}"
            listbox.insert(tk.END, texto)
        if not rows:
            listbox.insert(tk.END, "Sin resultados")

        cone.close()
        if seleccionado:
            for i in range(listbox.size()):
                if listbox.get(i) == seleccionado:
                    listbox.selection_set(i)
                    break

    def eliminar_usuario():
        seleccion = listbox.curselection()
        if not seleccion:
            dialog_error(base, "Atencion", "Selecciona un usuario")
            return

        seleccionado = listbox.get(seleccion[0])
        if seleccionado == "Sin resultados":
            dialog_error(base, "Atencion", "No hay usuarios")
            return
        user_id = seleccionado.split("|")[0].replace("ID:", "").strip()

        if dialog_confirm(base, "Confirmar", "Eliminar usuario definitivamente?"):
            cone = cconexion.cconexionBaseDeDatos()
            if cone is None:
                dialog_error(base, "Error", "No hay conexión a la base de datos")
                return
            cursor = cone.cursor()

            cursor.execute(
                "DELETE FROM usuarios_login WHERE id=%s",
                (user_id,)
            )

            cone.commit()
            cone.close()

            cargar_usuarios()

    btn_row = tk.Frame(card, bg=BG_CARD)
    btn_row.pack(fill="x")

    dark_button(btn_row, "Eliminar usuario", eliminar_usuario, primary=True).pack(
        side="right",
        padx=2,
        ipady=6,
        ipadx=8
    )

    def _do_search():
        cargar_usuarios(search_entry.get().strip())

    def _clear_search():
        search_entry.delete(0, tk.END)
        cargar_usuarios()

    def _export_list():
        rows = [[listbox.get(i)] for i in range(listbox.size())]
        exportar_lista_csv(rows, ["Usuarios"], "usuarios")

    dark_button(search_row, "Exportar CSV", _export_list).pack(side="right")
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
    spacer.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

    cargar_usuarios()

    def _auto_refresh():
        try:
            filtro = search_entry.get().strip()
        except Exception:
            filtro = None
        cargar_usuarios(filtro, silent=True)

    schedule_autorefresh(content, _auto_refresh, interval_ms=4000)
    register_activity(content)
    return content


def admin_usuarios():
    """Ventana para listar y eliminar usuarios."""
    win = tk.Toplevel()
    apply_chrome(win, "StockARG", 1320, 800, min_w=1100, min_h=650, state_key="admin_usuarios")
    admin_panel(win)
