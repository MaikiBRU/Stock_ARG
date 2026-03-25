"""Menú principal de navegación."""

import tkinter as tk
import os
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False
import Clientes
import Proveedores
import Productos
import Ventas
import Stock
import Sesion
from AdminUsuarios import admin_panel
from SesionPersistente import cerrar_sesion
from Dialogs import centrar_ventana
from Logger import log_info, LOG_FILE
from Theme import (
    BG_MAIN,
    BG_CARD,
    BG_GRADIENT,
    BG_BUTTON,
    BG_BUTTON_HOVER,
    ACCENT,
    ACCENT_HOVER,
    FG_TEXT,
    FG_MUTED,
    BORDER,
    FONT_TITLE,
    FONT_SECTION,
    FONT_LABEL,
    FONT_BODY,
    FONT_SUBTITLE,
    FONT_BUTTON,
    TITLE_BG,
    CLOSE_BG_NORMAL,
    CLOSE_BG_HOVER,
    CLOSE_BG_ACTIVE,
    CLOSE_FG,
    BTN_DANGER,
    BTN_DANGER_HOVER,
    dark_button,
    apply_chrome,
    apply_ttk_style,
)
from Utils import schedule_autorefresh, register_activity, bring_to_front
root = None

def menu_item(parent, title, subtitle, command, icon_img, accent=False, danger=False):
    """Crea un item de menú clickeable con icono."""
    if danger:
        bg = BTN_DANGER
        hover = BTN_DANGER_HOVER
        icon_bg = BTN_DANGER
    else:
        bg = BG_BUTTON
        hover = BG_BUTTON_HOVER
        icon_bg = ACCENT if accent else BG_BUTTON

    wrapper = tk.Frame(parent, bg=bg, highlightbackground=BORDER, highlightthickness=1)
    wrapper.pack_propagate(False)
    wrapper.configure(height=72)
    wrapper.pack(fill="x", pady=(0, 12))

    inner = tk.Frame(wrapper, bg=bg)
    inner.pack(fill="x", expand=True, pady=12)

    inner.grid_columnconfigure(0, weight=0, minsize=60)
    inner.grid_columnconfigure(1, weight=1)
    inner.grid_columnconfigure(2, weight=0, minsize=60)

    icon_wrap = tk.Frame(inner, bg=icon_bg, width=40, height=40)
    icon_wrap.pack_propagate(False)
    icon_wrap.grid(row=0, column=0, padx=(12, 8))

    icon = tk.Label(
        icon_wrap,
        image=icon_img,
        bg=icon_bg
    )
    icon.pack(expand=True)

    text_box = tk.Frame(inner, bg=bg)
    text_box.grid(row=0, column=1, sticky="n")

    title_lbl = tk.Label(
        text_box,
        text=title,
        bg=bg,
        fg=FG_TEXT,
        font=FONT_LABEL,
        justify="center",
        anchor="center"
    )
    title_lbl.pack()

    subtitle_lbl = tk.Label(
        text_box,
        text=subtitle,
        bg=bg,
        fg=FG_MUTED,
        font=FONT_SUBTITLE,
        justify="center",
        anchor="center"
    )
    subtitle_lbl.pack()

    spacer = tk.Frame(inner, bg=bg)
    spacer.grid(row=0, column=2, sticky="nsew")

    def _blend(c1, c2, t):
        def to_rgb(c):
            c = c.lstrip("#")
            return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
        r1, g1, b1 = to_rgb(c1)
        r2, g2, b2 = to_rgb(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _animate_bg(targets, to_color, steps=6, delay=12):
        start = wrapper.cget("bg")
        if getattr(wrapper, "_bg_after", None):
            try:
                wrapper.after_cancel(wrapper._bg_after)
            except Exception:
                pass
        def step(i=0):
            t = i / steps
            color = _blend(start, to_color, t)
            for w in targets:
                w.config(bg=color)
            if i < steps:
                wrapper._bg_after = wrapper.after(delay, lambda: step(i + 1))
        step()

    def on_enter(_):
        _animate_bg([wrapper, inner, text_box, spacer, title_lbl, subtitle_lbl], hover)
        wrapper.config(highlightbackground=ACCENT if accent else BG_BUTTON_HOVER)

    def on_leave(_):
        _animate_bg([wrapper, inner, text_box, spacer, title_lbl, subtitle_lbl], bg)
        wrapper.config(highlightbackground=BORDER)

    def on_click(_):
        command()

    for widget in (wrapper, inner, icon, text_box, spacer, title_lbl, subtitle_lbl):
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
        widget.bind("<Button-1>", on_click)
    for child in text_box.winfo_children():
        child.bind("<Enter>", on_enter)
        child.bind("<Leave>", on_leave)
        child.bind("<Button-1>", on_click)

    return wrapper


def load_icon(path, target_h=22):
    """Carga y redimensiona un icono."""
    if _PIL_OK:
        img = Image.open(path)
        if img.height > target_h:
            ratio = target_h / img.height
            new_w = max(1, int(img.width * ratio))
            img = img.resize((new_w, target_h), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    img = tk.PhotoImage(file=path)
    if img.height() > target_h:
        factor = max(1, int(round(img.height() / target_h)))
        img = img.subsample(factor, factor)
    return img


def draw_gradient(canvas, color1, color2):
    """Dibuja un gradiente vertical en el canvas."""
    if not canvas.winfo_exists():
        return
    canvas.delete("gradient")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1 or h <= 1:
        return

    r1, g1, b1 = [v // 256 for v in canvas.winfo_rgb(color1)]
    r2, g2, b2 = [v // 256 for v in canvas.winfo_rgb(color2)]

    for y in range(h):
        ratio = y / (h - 1)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        color = f"#{r:02x}{g:02x}{b:02x}"
        canvas.create_line(0, y, w, y, fill=color, tags="gradient")

    canvas.lower("gradient")


def attach_gradient(parent):
    """Crea un canvas de gradiente como fondo del contenedor."""
    canvas = tk.Canvas(parent, highlightthickness=0, bd=0, bg=BG_MAIN)
    canvas.place(x=0, y=0, relwidth=1, relheight=1)
    parent.bind("<Map>", lambda e: draw_gradient(canvas, BG_MAIN, BG_GRADIENT), add=True)
    parent.bind("<Visibility>", lambda e: draw_gradient(canvas, BG_MAIN, BG_GRADIENT), add=True)

    top = parent.winfo_toplevel()
    if not hasattr(top, "_gradients"):
        top._gradients = []
    top._gradients.append(canvas)
    if not getattr(top, "_gradient_bound", False):
        def _on_root_resize(_):
            for c in list(top._gradients):
                if c.winfo_exists():
                    draw_gradient(c, BG_MAIN, BG_GRADIENT)
        top.bind("<Configure>", _on_root_resize, add=True)
        top._gradient_bound = True

    def _draw_when_ready():
        try:
            if not canvas.winfo_exists():
                return
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w <= 1 or h <= 1:
                if parent.winfo_exists():
                    canvas._grad_after = parent.after(30, _draw_when_ready)
                return
            draw_gradient(canvas, BG_MAIN, BG_GRADIENT)
        except Exception:
            return

    canvas._grad_after = parent.after(0, _draw_when_ready)
    parent._gradient_canvas = canvas
    def _cleanup(_=None):
        try:
            if getattr(canvas, "_grad_after", None):
                parent.after_cancel(canvas._grad_after)
        except Exception:
            pass
    parent.bind("<Destroy>", _cleanup, add=True)
    return canvas


def cerrar_sesion_menu():
    """Cierra sesión y vuelve al login."""
    from SesionPersistente import cerrar_sesion
    from Login import login

    cerrar_sesion()
    root.destroy()
    login()



def crear_menu():
    """Construye la ventana principal del menú."""
    global root
    root = tk.Tk()
    apply_chrome(root, "StockARG", 1320, 800, min_w=1100, min_h=650, state_key="menu")
    centrar_ventana(root, 1200, 740)
    apply_ttk_style(root)
    bring_to_front(root)

    content = tk.Frame(root, bg=BG_MAIN)
    content.pack(fill="both", expand=True)

    menu_view = tk.Frame(content, bg=BG_MAIN)
    menu_view.pack(fill="both", expand=True)
    attach_gradient(menu_view)
    root.after(60, lambda: draw_gradient(menu_view._gradient_canvas, BG_MAIN, BG_GRADIENT))

    card = tk.Frame(
        menu_view,
        bg=BG_CARD,
        padx=34,
        pady=30,
        highlightbackground=BORDER,
        highlightthickness=1
    )
    card.place(relx=0.5, rely=0.5, anchor="center")
    card.pack_propagate(False)

    inner = tk.Frame(card, bg=BG_CARD)
    inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.94, relheight=0.92)
    inner.grid_columnconfigure(0, weight=1)
    inner.grid_rowconfigure(1, weight=1)

    header = tk.Frame(inner, bg=BG_CARD)
    header.grid(row=0, column=0, sticky="ew")

    encabezado = tk.Label(
        header,
        text="Menu Principal",
        font=FONT_TITLE,
        bg=BG_CARD,
        fg=FG_TEXT
    )
    encabezado.pack(pady=(0, 4))

    sub = tk.Label(
        header,
        text="Elegi una seccion para continuar",
        font=FONT_SUBTITLE,
        bg=BG_CARD,
        fg=FG_MUTED
    )
    sub.pack(pady=(0, 18))

    list_canvas = tk.Canvas(inner, bg=BG_CARD, highlightthickness=0, bd=0)
    list_canvas.grid(row=1, column=0, sticky="nsew")
    list_frame = tk.Frame(list_canvas, bg=BG_CARD)
    list_window = list_canvas.create_window((0, 0), window=list_frame, anchor="n")

    def _sync_list(_=None):
        list_canvas.update_idletasks()
        cw = list_canvas.winfo_width()
        ch = list_canvas.winfo_height()
        target_w = min(cw, 980)
        list_canvas.itemconfigure(list_window, width=target_w)
        fh = list_frame.winfo_reqheight()
        y = 0
        if fh < ch:
            y = (ch - fh) // 2
        list_canvas.coords(list_window, cw // 2, y)
        list_canvas.configure(scrollregion=list_canvas.bbox("all") or (0, 0, cw, ch))

    def _on_mousewheel(e):
        if list_frame.winfo_reqheight() <= list_canvas.winfo_height():
            return
        delta = -1 if e.delta > 0 else 1
        list_canvas.yview_scroll(delta, "units")

    list_canvas.bind("<Configure>", _sync_list)
    list_frame.bind("<Configure>", _sync_list)
    list_canvas.bind("<Enter>", lambda e: list_canvas.bind_all("<MouseWheel>", _on_mousewheel))
    list_canvas.bind("<Leave>", lambda e: list_canvas.unbind_all("<MouseWheel>"))

    panels = []

    def _apply_menu_layout():
        if not root.winfo_exists():
            return
        w = root.winfo_width()
        h = root.winfo_height()
        if w <= 1 or h <= 1:
            return
        card_w = max(780, int(w * 0.70))
        card_h = max(560, int(h * 0.85))
        card_w = min(card_w, 1100)
        card_h = min(card_h, 900)
        card.place_configure(width=card_w, height=card_h)
        panel_w = max(980, int(w * 0.90))
        panel_h = max(560, int(h * 0.85))
        panel_w = min(panel_w, 1300)
        panel_h = min(panel_h, 900)
        for p in panels:
            try:
                p.place_configure(width=panel_w, height=panel_h)
            except Exception:
                pass

    def _debounced_layout(_=None):
        if not root.winfo_exists():
            return
        if hasattr(root, "_menu_layout_after"):
            try:
                root.after_cancel(root._menu_layout_after)
            except Exception:
                pass
        root._menu_layout_after = root.after(40, _apply_menu_layout)

    root.bind("<Configure>", _debounced_layout, add=True)
    _apply_menu_layout()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icons = {
        "admin": load_icon(os.path.join(base_dir, "Assets", "administrar-usuario.png"), target_h=28),
        "clientes": load_icon(os.path.join(base_dir, "Assets", "cliente.png"), target_h=28),
        "proveedores": load_icon(os.path.join(base_dir, "Assets", "proveedores.png"), target_h=28),
        "productos": load_icon(os.path.join(base_dir, "Assets", "producto.png"), target_h=28),
        "stock": load_icon(os.path.join(base_dir, "Assets", "stock.png"), target_h=28),
        "ventas": load_icon(os.path.join(base_dir, "Assets", "venta.png"), target_h=28),
        "cerrar": load_icon(os.path.join(base_dir, "Assets", "cerrar-sesion.png"), target_h=28),
        "estado": load_icon(os.path.join(base_dir, "Assets", "estado.png"), target_h=28),
    }
    root._menu_icons = list(icons.values())

    views = [menu_view]

    def show_view(view):
        for v in views:
            v.pack_forget()
        view.pack(fill="both", expand=True)
        if getattr(view, "_build_func", None) and not getattr(view, "_built", False):
            try:
                view._build_func()
            finally:
                view._built = True
        try:
            canvas = getattr(view, "_gradient_canvas", None)
            if canvas:
                draw_gradient(canvas, BG_MAIN, BG_GRADIENT)
        except Exception:
            pass
        try:
            root.attributes("-alpha", 0.96)
            root.after(80, lambda: root.attributes("-alpha", 1.0))
        except Exception:
            pass

    def make_view(title, build_func, lazy=False):
        view = tk.Frame(content, bg=BG_MAIN)
        attach_gradient(view)
        panel = tk.Frame(
            view,
            bg=BG_CARD,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        panel.place(relx=0.5, rely=0.5, anchor="center")
        panels.append(panel)

        header = tk.Frame(panel, bg=BG_CARD)
        header.pack(fill="x", padx=16, pady=(12, 0))
        dark_button(header, "Volver", lambda: show_view(menu_view)).pack(side="left")
        tk.Label(
            header,
            text=title,
            bg=BG_CARD,
            fg=FG_TEXT,
            font=FONT_SECTION
        ).pack(side="left", padx=12)
        body = tk.Frame(panel, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=6, pady=(6, 12))
        if lazy:
            view._built = False
            view._build_func = lambda: build_func(body)
        else:
            build_func(body)
        views.append(view)
        return view

    def logs_panel(parent):
        card_logs = tk.LabelFrame(
            parent,
            text="Estado del sistema",
            padx=12,
            pady=12,
            bg=BG_CARD,
            fg=FG_TEXT,
            font=FONT_LABEL,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0
        )
        card_logs.pack(fill="both", expand=True, padx=16, pady=16)

        toolbar = tk.Frame(card_logs, bg=BG_CARD)
        toolbar.pack(fill="x", pady=(0, 8))

        text_wrap = tk.Frame(card_logs, bg=BG_CARD)
        text_wrap.pack(fill="both", expand=True)
        text_wrap.grid_columnconfigure(0, weight=1)
        text_wrap.grid_rowconfigure(0, weight=1)

        log_text = tk.Text(
            text_wrap,
            bg=BG_MAIN,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
            font=FONT_BODY,
            wrap="none",
            height=18
        )
        log_text.grid(row=0, column=0, sticky="nsew")
        scroll_y = tk.Scrollbar(text_wrap, orient="vertical", command=log_text.yview)
        scroll_x = tk.Scrollbar(text_wrap, orient="horizontal", command=log_text.xview)
        log_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        def _load_logs():
            try:
                if not os.path.exists(LOG_FILE):
                    content_txt = "Sin logs disponibles."
                else:
                    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    tail = lines[-200:] if lines else []
                    content_txt = "".join(tail) if tail else "Sin logs disponibles."
                log_text.config(state="normal")
                log_text.delete("1.0", tk.END)
                log_text.insert(tk.END, content_txt)
                log_text.config(state="disabled")
            except Exception as exc:
                log_text.config(state="normal")
                log_text.delete("1.0", tk.END)
                log_text.insert(tk.END, f"No se pudieron cargar logs: {exc}")
                log_text.config(state="disabled")

        dark_button(toolbar, "Actualizar", _load_logs, primary=True).pack(side="right")
        _load_logs()
        schedule_autorefresh(card_logs, _load_logs, interval_ms=4000)
        register_activity(card_logs)

    clientes_view = make_view("Clientes", Clientes.clientes_panel)
    proveedores_view = make_view("Proveedores", Proveedores.proveedores_panel)
    productos_view = make_view("Productos", Productos.productos_panel)
    stock_view = make_view("Stock", Stock.stock_panel)
    ventas_view = make_view("Ventas", Ventas.ventas_panel)
    logs_view = make_view("Estado", logs_panel, lazy=True)
    admin_view = None
    if Sesion.usuario_actual and Sesion.usuario_actual.get("es_admin"):
        admin_view = make_view("Administrar usuarios", admin_panel)

    if admin_view is not None:
        menu_item(
            list_frame,
            "Administrar usuarios",
            "Altas, bajas y permisos",
            lambda v=admin_view: show_view(v),
            icons["admin"],
            danger=True
        )

    menu_item(
        list_frame,
        "Clientes",
        "Gestion de clientes y contactos",
        lambda v=clientes_view: show_view(v),
        icons["clientes"],
        accent=True
    )

    menu_item(
        list_frame,
        "Proveedores",
        "ABM de proveedores y datos",
        lambda v=proveedores_view: show_view(v),
        icons["proveedores"],
        accent=True
    )

    menu_item(
        list_frame,
        "Productos",
        "Stock, precios y catalogo",
        lambda v=productos_view: show_view(v),
        icons["productos"],
        accent=True
    )

    menu_item(
        list_frame,
        "Stock",
        "Control y alertas de inventario",
        lambda v=stock_view: show_view(v),
        icons["stock"],
        accent=True
    )

    menu_item(
        list_frame,
        "Ventas",
        "Registrar y consultar ventas",
        lambda v=ventas_view: show_view(v),
        icons["ventas"],
        accent=True
    )

    menu_item(
        list_frame,
        "Estado",
        "Logs y estado del sistema",
        lambda v=logs_view: show_view(v),
        icons["estado"],
        accent=True
    )

    menu_item(
        list_frame,
        "Cerrar sesion",
        "Salir de la cuenta actual",
        cerrar_sesion_menu,
        icons["cerrar"],
        danger=True
    )

    root.mainloop()


if __name__ == "__main__":
    crear_menu()
    log_info("Menu.py ejecutandose directamente")
