"""Tema visual compartido para la UI."""

import os
import json
import tkinter as tk
from tkinter import ttk
try:
    import ctypes
except Exception:
    ctypes = None

BG_MAIN = "#0b0f14"
BG_CARD = "#121826"
BG_GRADIENT = "#1a2233"
BG_INPUT = "#1a2030"
BG_BUTTON = "#1f2937"
BG_BUTTON_HOVER = "#2b374d"

ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"

FG_TEXT = "#e5e7eb"
FG_MUTED = "#9ca3af"
INPUT_LINE = "#334155"
BORDER = "#1f2937"

TITLE_BG = "#010413"

CLOSE_BG_NORMAL = TITLE_BG
CLOSE_BG_HOVER = "#7f1d1d"
CLOSE_BG_ACTIVE = "#991b1b"
CLOSE_FG = "#e5e7eb"

BTN_DANGER = "#dc2626"
BTN_DANGER_HOVER = "#b91c1c"

FONT_FAMILY = "Bahnschrift"
FONT_BODY = (FONT_FAMILY, 10)
FONT_LABEL = (FONT_FAMILY, 10, "bold")
FONT_INPUT = (FONT_FAMILY, 10)
FONT_BUTTON = (FONT_FAMILY, 10, "bold")
FONT_TITLE = (FONT_FAMILY, 18, "bold")
FONT_SECTION = (FONT_FAMILY, 14, "bold")
FONT_H1 = (FONT_FAMILY, 20, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 9)
FONT_TITLEBAR = (FONT_FAMILY, 10, "bold")
APP_ID = "StockARG"
APP_ICON_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Assets", "StockARG_icon.png")
APP_ICON_FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Assets", "stock.png")
APP_ICON_ICO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Assets", "StockARG.ico")


def init_app_identity():
    """Configura AppUserModelID (taskbar icon en Windows)."""
    try:
        if ctypes:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def dark_button(parent, text, command, primary=False, variant=None):
    """Botón oscuro con hover y variantes."""
    if variant == "danger":
        bg = BTN_DANGER
        hover = BTN_DANGER_HOVER
    else:
        bg = ACCENT if primary else BG_BUTTON
        hover = ACCENT_HOVER if primary else BG_BUTTON_HOVER

    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=FG_TEXT,
        activebackground=hover,
        activeforeground=FG_TEXT,
        disabledforeground=FG_MUTED,
        bd=0,
        font=FONT_BUTTON,
        cursor="hand2",
        relief="flat"
    )
    btn._bg = bg
    btn._hover = hover

    def on_enter(_):
        if btn.cget("state") != "disabled":
            btn.configure(bg=getattr(btn, "_hover", hover))

    def on_leave(_):
        btn.configure(bg=getattr(btn, "_bg", bg))

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def _set_app_icon(root):
    try:
        if os.path.exists(APP_ICON_ICO):
            try:
                root.iconbitmap(APP_ICON_ICO)
            except Exception:
                pass
        icon_path = APP_ICON_PNG if os.path.exists(APP_ICON_PNG) else APP_ICON_FALLBACK
        if os.path.exists(icon_path):
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, img)
            root._app_icon = img
    except Exception:
        pass


def _force_taskbar(root):
    """Fuerza a mostrar el icono en la barra de tareas (Windows)."""
    if not ctypes:
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            return
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style = ex_style | WS_EX_APPWINDOW
        ex_style = ex_style & ~WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        ctypes.windll.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                          SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass


def _center_window(root, width, height):
    try:
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = max(0, int((sw - width) / 2))
        y = max(0, int((sh - height) / 2))
        root.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        root.geometry(f"{width}x{height}")


def _ensure_on_screen(root, fallback_w, fallback_h):
    try:
        root.update_idletasks()
        geo = root.geometry().split("+")
        size = geo[0]
        x = int(geo[1]) if len(geo) > 1 else 0
        y = int(geo[2]) if len(geo) > 2 else 0
        w, h = size.split("x")
        w = int(w)
        h = int(h)
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        if w < 100 or h < 100:
            _center_window(root, fallback_w, fallback_h)
            return
        if x < 0 or y < 0 or x > (sw - 80) or y > (sh - 80):
            _center_window(root, fallback_w, fallback_h)
    except Exception:
        _center_window(root, fallback_w, fallback_h)


def _state_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "window_state.json")


def _load_window_state(key):
    try:
        path = _state_path()
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(key)
    except Exception:
        return None


def _save_window_state(key, geometry):
    try:
        path = _state_path()
        data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        data[key] = geometry
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2)
    except Exception:
        pass
    try:
        if ctypes:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _fade_in(win, duration=180, steps=12):
    try:
        win.attributes("-alpha", 0.0)
    except Exception:
        return

    delay = max(1, int(duration / steps))

    def step(i=0):
        if i >= steps:
            try:
                win.attributes("-alpha", 1.0)
            except Exception:
                pass
            return
        try:
            win.attributes("-alpha", (i + 1) / steps)
        except Exception:
            return
        win.after(delay, lambda: step(i + 1))

    win.after(0, step)


def apply_chrome(root, title_text, width, height, min_w=420, min_h=300, fade=True, state_key=None):
    """Aplica barra custom con min/max/close y resize libre."""
    root.overrideredirect(True)
    root.resizable(False, False)
    root.configure(bg=BG_MAIN)
    key = state_key or title_text
    saved = _load_window_state(key)
    if saved:
        root.geometry(saved)
        _ensure_on_screen(root, width, height)
    else:
        _center_window(root, width, height)
    root.minsize(min_w, min_h)
    _set_app_icon(root)
    root._taskbar_fix_done = False

    title_bar = tk.Frame(root, bg=TITLE_BG, height=34)
    title_bar.pack(fill="x")

    def start_move(e):
        root._drag_x = e.x_root
        root._drag_y = e.y_root

    def do_move(e):
        x = root.winfo_x() + (e.x_root - root._drag_x)
        y = root.winfo_y() + (e.y_root - root._drag_y)
        root.geometry(f"+{x}+{y}")
        root._drag_x = e.x_root
        root._drag_y = e.y_root

    title_bar.bind("<Button-1>", start_move)
    title_bar.bind("<B1-Motion>", do_move)

    title_label = tk.Label(
        title_bar,
        text=title_text,
        bg=TITLE_BG,
        fg=FG_TEXT,
        font=FONT_TITLEBAR
    )
    title_label.pack(side="left", padx=10)
    title_label.bind("<Button-1>", start_move)
    title_label.bind("<B1-Motion>", do_move)

    root._is_maximized = False
    root._normal_geometry = root.geometry()
    root._restore_override = False

    def toggle_maximize(_=None):
        if not root._is_maximized:
            root._normal_geometry = root.geometry()
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")
            root._is_maximized = True
        else:
            root.geometry(root._normal_geometry)
            root._is_maximized = False
        root.after(0, root.update_idletasks)
        _update_max_button()

    def minimize():
        root._restore_override = True
        root.overrideredirect(False)
        root.iconify()

    def _on_map(_):
        if getattr(root, "_restore_override", False):
            root.after(0, lambda: root.overrideredirect(True))
            root._restore_override = False
        if not getattr(root, "_taskbar_fix_done", False):
            root._taskbar_fix_done = True
            try:
                root.after(10, lambda: root.overrideredirect(False))
                root.after(30, lambda: root.overrideredirect(True))
            except Exception:
                pass
            root.after(80, lambda: _force_taskbar(root))

    root.bind("<Map>", _on_map)
    title_bar.bind("<Double-Button-1>", toggle_maximize)

    def _title_btn(text, command, hover_bg=BG_BUTTON_HOVER, active_bg=None):
        btn = tk.Label(
            title_bar,
            text=text,
            bg=TITLE_BG,
            fg=FG_TEXT,
            font=FONT_TITLEBAR,
            cursor="hand2",
            width=4
        )
        def on_enter(_):
            btn.config(bg=hover_bg)
        def on_leave(_):
            btn.config(bg=TITLE_BG)
        def on_press(_):
            if active_bg:
                btn.config(bg=active_bg)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<ButtonPress-1>", on_press)
        btn.bind("<ButtonRelease-1>", lambda e: command())
        return btn

    btn_close = _title_btn("x", root.destroy, hover_bg=CLOSE_BG_HOVER, active_bg=CLOSE_BG_ACTIVE)
    btn_max = _title_btn("□", toggle_maximize)
    btn_min = _title_btn("–", minimize)
    btn_close.pack(side="right", padx=(0, 4), pady=2)
    btn_max.pack(side="right", padx=(0, 2), pady=2)
    btn_min.pack(side="right", padx=(0, 2), pady=2)

    def _update_max_button():
        btn_max.config(text="❐" if root._is_maximized else "□")

    def _track_geometry(_):
        if not root.winfo_exists():
            return
        if not root._is_maximized:
            root._normal_geometry = root.geometry()
        if getattr(root, "_state_after", None):
            try:
                root.after_cancel(root._state_after)
            except Exception:
                pass
        def _persist():
            if not root.winfo_exists():
                return
            if not root._is_maximized:
                _save_window_state(key, root.geometry())
        root._state_after = root.after(200, _persist)

    root.bind("<Configure>", _track_geometry)
    if fade:
        _fade_in(root)

    return title_bar


def apply_ttk_style(root):
    """Configura estilos ttk en modo oscuro."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "Dark.TFrame",
        background=BG_MAIN
    )
    style.configure(
        "Dark.Treeview",
        background=BG_CARD,
        fieldbackground=BG_CARD,
        foreground=FG_TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        rowheight=26
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", FG_TEXT)]
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=BG_BUTTON,
        foreground=FG_TEXT,
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padding=(6, 4)
    )
    style.map(
        "Dark.Treeview.Heading",
        background=[("active", BG_BUTTON_HOVER)]
    )
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=BG_BUTTON,
        troughcolor=BG_MAIN,
        bordercolor=BORDER,
        lightcolor=BG_BUTTON,
        darkcolor=BG_BUTTON,
        arrowcolor=FG_MUTED
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", BG_BUTTON_HOVER)],
        arrowcolor=[("active", FG_TEXT)]
    )
    style.configure(
        "Dark.Horizontal.TScrollbar",
        background=BG_BUTTON,
        troughcolor=BG_MAIN,
        bordercolor=BORDER,
        lightcolor=BG_BUTTON,
        darkcolor=BG_BUTTON,
        arrowcolor=FG_MUTED
    )
    style.map(
        "Dark.Horizontal.TScrollbar",
        background=[("active", BG_BUTTON_HOVER)],
        arrowcolor=[("active", FG_TEXT)]
    )
    style.configure(
        "Dark.TCombobox",
        fieldbackground=BG_CARD,
        background=BG_CARD,
        foreground=FG_TEXT,
        arrowcolor=FG_MUTED
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", BG_CARD), ("active", BG_CARD)],
        foreground=[("readonly", FG_TEXT)],
        arrowcolor=[("active", FG_TEXT)]
    )
    # Combobox dropdown list colors
    try:
        root.option_add("*TCombobox*Listbox.background", BG_CARD)
        root.option_add("*TCombobox*Listbox.foreground", FG_TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", FG_TEXT)
    except Exception:
        pass

    style.configure(
        "Dark.TNotebook",
        background=BG_MAIN,
        borderwidth=0
    )
    style.configure(
        "Dark.TNotebook.Tab",
        background=BG_CARD,
        foreground=FG_TEXT,
        padding=(12, 6),
        font=FONT_LABEL,
        borderwidth=0,
        focuscolor=BG_MAIN
    )
    style.map(
        "Dark.TNotebook.Tab",
        background=[("selected", BG_BUTTON), ("active", BG_BUTTON_HOVER)],
        foreground=[("selected", FG_TEXT), ("active", FG_TEXT)]
    )
