"""Funciones utilitarias de validación y seguridad."""

import os
import re
import sys
import time
import bcrypt
import random
import string
from Dialogs import show_loading


def resource_path(*parts):
    """Devuelve una ruta a recursos compatible con PyInstaller."""
    base_dir = getattr(sys, "_MEIPASS", None)
    if base_dir:
        path = os.path.join(base_dir, *parts)
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)
    if os.path.exists(path):
        return path
    return os.path.join(os.getcwd(), *parts)

def email_valido(email):
    """Valida el formato básico de un email."""
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def password_valida(password):
    """Valida políticas mínimas de contraseña."""
    if len(password) < 8:
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c.isalpha() for c in password):
        return False
    return True

def generar_codigo():
    """Genera un código numérico de 6 dígitos."""
    return ''.join(random.choices(string.digits, k=6))

def hash_password(password):
    """Hashea un password con bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verificar_password(password, password_hash):
    """Verifica un password contra un hash bcrypt."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def campos_requeridos(**campos):
    """Valida campos requeridos y retorna (ok, faltantes)."""
    faltantes = []
    for nombre, valor in campos.items():
        if valor is None:
            faltantes.append(nombre)
        elif isinstance(valor, str) and not valor.strip():
            faltantes.append(nombre)
    return len(faltantes) == 0, faltantes


def parse_int(valor, min_value=None, allow_zero=True):
    """Convierte a int y valida un mínimo opcional."""
    try:
        n = int(valor)
    except Exception:
        return None
    if min_value is not None and n < min_value:
        return None
    if not allow_zero and n == 0:
        return None
    return n


def parse_float(valor, min_value=None, allow_zero=True):
    """Convierte a float y valida un mínimo opcional."""
    try:
        if isinstance(valor, str):
            valor = valor.strip().replace("$", "").replace(" ", "").replace(",", ".")
        n = float(valor)
    except Exception:
        return None
    if min_value is not None and n < min_value:
        return None
    if not allow_zero and n == 0:
        return None
    return n


def validar_id(valor, campo="Id"):
    """Valida IDs simples (letras, numeros, guion y guion bajo)."""
    if valor is None:
        return False, f"{campo} requerido"
    valor = str(valor).strip()
    if not valor:
        return False, f"{campo} requerido"
    if len(valor) > 50:
        return False, f"{campo} demasiado largo"
    if not re.match(r"^[A-Za-z0-9_-]+$", valor):
        return False, f"{campo} invalido (solo letras, numeros, - y _)"
    return True, None


def exportar_treeview_csv(tree, headers, default_name="export"):
    """Exporta un Treeview a CSV."""
    try:
        from tkinter import filedialog
    except Exception:
        return False

    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
        initialfile=f"{default_name}.csv"
    )
    if not path:
        return False

    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in tree.get_children():
            tags = tree.item(item, "tags") or ()
            if "empty" in tags:
                continue
            writer.writerow(tree.item(item, "values"))
    return True


def exportar_treeview_pdf(tree, headers, title="Reporte", default_name="reporte"):
    """Exporta un Treeview a PDF (requiere reportlab)."""
    try:
        from tkinter import filedialog
    except Exception:
        return False, "No se pudo abrir el selector de archivo"
    path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF", "*.pdf")],
        initialfile=f"{default_name}.pdf"
    )
    if not path:
        return False, "Cancelado"
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        return False, "Falta instalar reportlab (pip install reportlab)"

    try:
        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4
        y = height - 50
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, title)
        y -= 24
        c.setFont("Helvetica", 9)

        # Encabezados
        header_line = " | ".join(headers)
        c.drawString(40, y, header_line[:110])
        y -= 14

        for item in tree.get_children():
            tags = tree.item(item, "tags") or ()
            if "empty" in tags:
                continue
            values = [str(v) for v in tree.item(item, "values")]
            line = " | ".join(values)
            c.drawString(40, y, line[:110])
            y -= 12
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)

        c.save()
        return True, None
    except Exception as exc:
        return False, f"No se pudo exportar PDF: {exc}"


def exportar_lista_csv(rows, headers, default_name="export"):
    """Exporta una lista de filas a CSV."""
    try:
        from tkinter import filedialog
    except Exception:
        return False
    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
        initialfile=f"{default_name}.csv"
    )
    if not path:
        return False
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    return True


def run_with_loading(parent, message, func):
    """Ejecuta una funciÃ³n mostrando un overlay de carga."""
    close = show_loading(parent, message)
    try:
        try:
            parent.update_idletasks()
        except Exception:
            pass
        return func()
    finally:
        try:
            close()
        except Exception:
            pass


def schedule_autorefresh(widget, func, interval_ms=4000):
    """Programa refresco automatico seguro (sin romper la UI)."""
    def _tick():
        try:
            if not widget.winfo_exists():
                return
            if not widget.winfo_viewable():
                widget.after(interval_ms, _tick)
                return
            if getattr(widget, "_auto_refresh_busy", False):
                widget.after(interval_ms, _tick)
                return
            if _recent_user_activity():
                widget.after(interval_ms, _tick)
                return
            widget._auto_refresh_busy = True
            func()
        except Exception:
            try:
                if widget.winfo_exists():
                    widget.after(interval_ms, _tick)
            except Exception:
                return
        else:
            try:
                widget.after(interval_ms, _tick)
            except Exception:
                return
        finally:
            try:
                if widget.winfo_exists():
                    widget._auto_refresh_busy = False
            except Exception:
                pass

    try:
        widget.after(interval_ms, _tick)
    except Exception:
        pass


def widget_alive(widget):
    """Retorna True si el widget existe y no fue destruido."""
    try:
        return widget is not None and widget.winfo_exists()
    except Exception:
        return False


_LAST_ACTIVITY_MS = 0


def _mark_activity(_=None):
    global _LAST_ACTIVITY_MS
    _LAST_ACTIVITY_MS = int(time.time() * 1000)


def _recent_user_activity(min_idle_ms=800):
    if _LAST_ACTIVITY_MS == 0:
        return False
    now = int(time.time() * 1000)
    return (now - _LAST_ACTIVITY_MS) < min_idle_ms


def register_activity(widget):
    """Registra actividad del usuario para pausar refrescos automaticos."""
    try:
        widget.bind_all("<KeyPress>", _mark_activity, add=True)
        widget.bind_all("<ButtonPress>", _mark_activity, add=True)
        widget.bind_all("<MouseWheel>", _mark_activity, add=True)
    except Exception:
        pass


def bring_to_front(win):
    """Trae la ventana al frente al iniciar."""
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.after(300, lambda: win.attributes("-topmost", False))
        win.focus_force()
    except Exception:
        pass


def importar_csv():
    """Importa filas desde CSV."""
    try:
        from tkinter import filedialog
    except Exception:
        return []
    path = filedialog.askopenfilename(
        filetypes=[("CSV", "*.csv")],
        title="Seleccionar CSV"
    )
    if not path:
        return []
    import csv
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            rows.append([c.strip() for c in row])
    return rows


def configurar_orden_treeview(tree, numeric_cols=None):
    """Habilita ordenamiento por columnas en un Treeview."""
    if numeric_cols is None:
        numeric_cols = set()
    else:
        numeric_cols = set(numeric_cols)

    def _sort(col, reverse):
        items = [(tree.set(k, col), k) for k in tree.get_children("")]
        def _key(val):
            v = val[0]
            if col in numeric_cols:
                try:
                    return float(str(v).replace("$", "").replace("%", "").strip())
                except Exception:
                    return 0
            return str(v).lower()

        items.sort(key=_key, reverse=reverse)
        for index, (_, k) in enumerate(items):
            tree.move(k, "", index)
        tree.heading(col, command=lambda: _sort(col, not reverse))

    for col in tree["columns"]:
        tree.heading(col, command=lambda c=col: _sort(c, False))


def treeview_set_empty(tree, message="Sin resultados"):
    """Muestra una fila informativa cuando el Treeview queda vacio."""
    cols = tree["columns"]
    if not cols:
        return
    values = [message] + [""] * (len(cols) - 1)
    tree.insert("", "end", values=values, tags=("empty",))
