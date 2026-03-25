"""Diálogos modales con estilo oscuro."""

import tkinter as tk
from Theme import (
    BG_MAIN,
    BG_CARD,
    FG_TEXT,
    FG_MUTED,
    BORDER,
    ACCENT,
    ACCENT_HOVER,
    BTN_DANGER,
    BTN_DANGER_HOVER,
    FONT_BUTTON,
    FONT_LABEL,
    FONT_BODY,
)


def centrar_ventana(win, w, h, parent=None):
    """Centra una ventana respecto al padre o la pantalla."""
    win.update_idletasks()
    if parent is not None and parent.winfo_ismapped():
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw // 2) - (w // 2)
        y = py + (ph // 2) - (h // 2)
    else:
        x = (win.winfo_screenwidth() // 2) - (w // 2)
        y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


def _button(parent, text, command, bg, bg_hover):
    """Crea un botón label con hover."""
    btn = tk.Label(
        parent,
        text=text,
        bg=bg,
        fg="white",
        font=FONT_BUTTON,
        padx=14,
        pady=8,
        cursor="hand2"
    )

    def hover(_): btn.config(bg=bg_hover)
    def leave(_): btn.config(bg=bg)
    def click(_): command()

    btn.bind("<Enter>", hover)
    btn.bind("<Leave>", leave)
    btn.bind("<Button-1>", click)
    return btn


def dialog_info(parent, title, message):
    """Muestra un diálogo informativo."""
    return _dialog(parent, title, message, kind="info")


def dialog_error(parent, title, message):
    """Muestra un diálogo de error."""
    return _dialog(parent, title, message, kind="error")


def show_loading(parent, message="Cargando..."):
    """Muestra un overlay de carga y retorna un cierre."""
    existing = getattr(parent, "_active_loading", None)
    if existing is not None and existing.winfo_exists():
        return lambda: None

    win = tk.Toplevel(parent)
    win.withdraw()
    win.overrideredirect(True)
    win.configure(bg=BG_MAIN)
    win.transient(parent)
    win.grab_set()

    w, h = 260, 140
    parent._active_loading = win
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
        win.after(50, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

    card = tk.Frame(win, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="both", expand=True, padx=8, pady=8)

    tk.Label(
        card,
        text=message,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_BODY
    ).pack(expand=True)

    win.update_idletasks()
    centrar_ventana(win, w, h, parent=parent)
    win.deiconify()

    def close():
        try:
            win.grab_release()
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass
        try:
            if getattr(parent, "_active_loading", None) == win:
                parent._active_loading = None
        except Exception:
            pass

    return close


def dialog_confirm(parent, title, message):
    """Muestra un diálogo de confirmación."""
    return _dialog(parent, title, message, kind="confirm")


def _dialog(parent, title, message, kind="info"):
    """Construye y controla el diálogo modal."""
    prev_focus = None
    try:
        prev_focus = parent.focus_get()
    except Exception:
        prev_focus = None

    existing = getattr(parent, "_active_dialog", None)
    if existing is not None and existing.winfo_exists():
        try:
            existing.lift()
            existing.focus_force()
        except Exception:
            pass
        return False if kind == "confirm" else None

    win = tk.Toplevel(parent)
    win.withdraw()
    win.overrideredirect(True)
    win.configure(bg=BG_MAIN)
    win.transient(parent)
    win.grab_set()

    w, h = 380, 210
    parent._active_dialog = win
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
        win.after(50, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

    title_bar = tk.Frame(win, bg=BG_CARD, height=38)
    title_bar.pack(fill="x")

    def start_move(e):
        win._x = e.x_root
        win._y = e.y_root

    def do_move(e):
        x = win.winfo_x() + (e.x_root - win._x)
        y = win.winfo_y() + (e.y_root - win._y)
        win.geometry(f"+{x}+{y}")
        win._x = e.x_root
        win._y = e.y_root

    title_bar.bind("<Button-1>", start_move)
    title_bar.bind("<B1-Motion>", do_move)

    tk.Label(
        title_bar,
        text=title,
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_LABEL
    ).pack(side="left", padx=12)

    close = tk.Label(title_bar, text="x", bg=BG_CARD, fg=FG_TEXT, width=3, cursor="hand2")
    close.pack(side="right")

    def close_hover(_): close.config(bg=BTN_DANGER_HOVER)
    def close_leave(_): close.config(bg=BG_CARD)
    def _close():
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
        try:
            parent.focus_force()
            def _restore_focus():
                try:
                    if prev_focus is not None and prev_focus.winfo_exists():
                        prev_focus.focus_set()
                except Exception:
                    pass
            parent.after(0, _restore_focus)
        except Exception:
            pass

    def close_click(_):
        if kind == "confirm" and result["value"] is None:
            result["value"] = False
        _close()

    close.bind("<Enter>", close_hover)
    close.bind("<Leave>", close_leave)
    close.bind("<Button-1>", close_click)

    card = tk.Frame(win, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="both", expand=True, padx=12, pady=12)

    icon = "i" if kind == "info" else ("!" if kind == "confirm" else "x")
    tk.Label(
        card,
        text=f"{icon}  {message}",
        bg=BG_CARD,
        fg=FG_TEXT,
        wraplength=340,
        font=FONT_BODY
    ).pack(pady=(22, 18), padx=14)

    result = {"value": None}

    def ok():
        result["value"] = True
        _close()

    def cancel():
        result["value"] = False
        _close()

    btn_row = tk.Frame(card, bg=BG_CARD)
    btn_row.pack(pady=(0, 18))

    if kind == "confirm":
        _button(btn_row, "Cancelar", cancel, BTN_DANGER, BTN_DANGER_HOVER).pack(side="left", padx=6)
        _button(btn_row, "Aceptar", ok, ACCENT, ACCENT_HOVER).pack(side="left", padx=6)
    else:
        _button(btn_row, "Aceptar", ok, ACCENT, ACCENT_HOVER).pack()

    win.update_idletasks()
    real_w = win.winfo_reqwidth() or w
    real_h = win.winfo_reqheight() or h
    centrar_ventana(win, real_w, real_h, parent=parent)
    win.deiconify()
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
        win.after(50, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

    win.wait_window()
    try:
        if getattr(parent, "_active_dialog", None) == win:
            parent._active_dialog = None
    except Exception:
        pass
    return result["value"]
