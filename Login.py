"""Pantalla de login y registro."""

from Logger import log_info, log_error
log_info("Login.py cargado")

import os
import time
import threading
try:
    import requests
    _REQUESTS_OK = True
except Exception:
    requests = None
    _REQUESTS_OK = False
import tkinter as tk
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    _GOOGLE_OK = True
except Exception:
    InstalledAppFlow = None
    _GOOGLE_OK = False

from Utils import email_valido, password_valida, generar_codigo, hash_password, bring_to_front, resource_path
from EmailSender import enviar_codigo
from Usuarios import Usuarios
from Conexion import cconexion
from SesionPersistente import guardar_sesion
import Sesion

from Dialogs import dialog_error, dialog_info, dialog_confirm, centrar_ventana
from Theme import (
    BG_MAIN,
    BG_CARD,
    BG_GRADIENT,
    BG_INPUT,
    BG_BUTTON,
    BG_BUTTON_HOVER,
    ACCENT,
    ACCENT_HOVER,
    FG_TEXT,
    FG_MUTED,
    INPUT_LINE,
    BORDER,
    TITLE_BG,
    CLOSE_BG_NORMAL,
    CLOSE_BG_HOVER,
    CLOSE_BG_ACTIVE,
    CLOSE_FG,
    FONT_H1,
    FONT_SUBTITLE,
    FONT_BUTTON,
    FONT_INPUT,
    FONT_SECTION,
    dark_button,
    apply_chrome,
)


def draw_gradient(canvas, color1, color2):
    """Dibuja un gradiente vertical en un canvas."""
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



def dark_entry(parent):
    """Entry oscuro con estilo."""
    entry = tk.Entry(
        parent,
        bg=BG_INPUT,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT
    )
    entry.pack(pady=6, ipady=6, fill="x")
    return entry


def dark_entry_with_icon(parent, icon_img):
    """Entry oscuro con icono a la izquierda."""
    row = tk.Frame(parent, bg=BG_CARD)
    row.pack(fill="x", pady=8)

    icon_wrap = tk.Frame(row, bg=BG_CARD, width=30, height=30)
    icon_wrap.pack_propagate(False)
    icon_wrap.pack(side="left", padx=(0, 12), pady=2)

    icon = tk.Label(icon_wrap, image=icon_img, bg=BG_CARD)
    icon.pack(expand=True)

    entry_col = tk.Frame(row, bg=BG_CARD)
    entry_col.pack(side="left", fill="x", expand=True)

    entry = tk.Entry(
        entry_col,
        bg=BG_CARD,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT
    )
    entry.pack(fill="x", pady=(0, 4))

    underline = tk.Frame(entry_col, bg=INPUT_LINE, height=1)
    underline.pack(fill="x")
    return entry


def load_icon(path, target_h=24):
    """Carga y redimensiona iconos."""
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


def splash_screen(work_fn=None, on_done=None, message="Cargando aplicación...", message_fn=None, min_duration=1200):
    """Pantalla de carga inicial."""
    splash = tk.Tk()
    splash.overrideredirect(True)
    centrar_ventana(splash, 350, 300)
    splash.configure(bg=BG_MAIN)
    splash.update_idletasks()
    try:
        splash.deiconify()
        splash.lift()
        splash.attributes("-topmost", True)
        splash.after(200, lambda: splash.attributes("-topmost", False))
    except Exception:
        pass

    canvas = tk.Canvas(splash, width=100, height=100, bg=BG_MAIN, highlightthickness=0)
    canvas.pack(pady=(40, 0))

    arc = canvas.create_arc(
        10, 10, 90, 90,
        start=0,
        extent=120,
        outline=ACCENT,
        style="arc",
        width=4
    )

    percent_label = tk.Label(
        splash,
        text="",
        fg=FG_MUTED,
        bg=BG_MAIN,
        font=FONT_SECTION
    )
    percent_label.pack(pady=10)

    progress = {"angle": 0, "tick": 0}
    done = {"value": False, "result": None, "error": None}
    start_ts = time.perf_counter()

    def worker():
        if work_fn:
            try:
                done["result"] = work_fn()
            except Exception as exc:
                done["error"] = exc
                done["result"] = None
        done["value"] = True

    if work_fn:
        threading.Thread(target=worker, daemon=True).start()
    else:
        splash.after(900, lambda: done.update(value=True))

    def animate():
        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        if done["value"] and elapsed_ms >= min_duration:
            if done.get("error"):
                log_error(f"Error inicializando: {done['error']}")
            splash.destroy()
            if on_done:
                on_done(done["result"])
            else:
                login()
            return

        progress["angle"] = (progress["angle"] + 15) % 360
        progress["tick"] = (progress["tick"] + 1) % 12
        canvas.itemconfig(arc, start=progress["angle"])
        dots = "." * ((progress["tick"] // 3) + 1)
        base_msg = message
        if message_fn:
            try:
                base_msg = message_fn(done["result"], done["value"])
            except Exception:
                base_msg = message
        percent_label.config(text=f"{base_msg}{dots}")

        splash.after(35, animate)

    animate()
    splash.mainloop()


# ======================================================
# FINALIZAR LOGIN
# ======================================================
def finalizar_login(root, user):
    """Guarda sesión y abre el menú."""
    from Menu import crear_menu
    Sesion.usuario_actual = user
    try:
        if isinstance(user, dict):
            user.pop("password", None)
    except Exception:
        pass
    guardar_sesion(user)
    root.destroy()
    crear_menu()


# ======================================================
# LOGIN GOOGLE
# ======================================================
def login_google_proceso(root):
    """Proceso de login con Google (hilo)."""
    try:
        if not _REQUESTS_OK:
            root.after(0, lambda: dialog_error(root, "Error", "Requests no está disponible."))
            return
        if not _GOOGLE_OK:
            root.after(0, lambda: dialog_error(root, "Error", "Google Login no está disponible."))
            return
        CLIENT_SECRET_PATH = resource_path("client_secret.json")
        if not os.path.exists(CLIENT_SECRET_PATH):
            log_error(f"client_secret.json no encontrado en: {CLIENT_SECRET_PATH}")
            root.after(0, lambda: dialog_error(root, "Error", "No se encontro client_secret.json. Reinstala el .exe."))
            return

        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_PATH,
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email",
                "openid"
            ]
        )

        creds = flow.run_local_server(port=0)

        resp = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            params={"access_token": creds.token}
        )
        try:
            log_info(f"Google userinfo status={resp.status_code} text={resp.text[:200]}")
        except Exception:
            pass
        try:
            userinfo = resp.json()
        except Exception:
            userinfo = {}

        email = userinfo["email"]
        google_id = userinfo["id"]

        cone = cconexion.cconexionBaseDeDatos()
        if cone is None:
            root.after(0, lambda: dialog_error(root, "Error", "No se pudo conectar a la base de datos."))
            return
        cursor = cone.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, email, es_admin, verificado
            FROM usuarios_login
            WHERE email = %s
        """, (email,))
        user = cursor.fetchone()

        if not user:
            cursor.execute("""
                INSERT INTO usuarios_login (email, google_id, verificado)
                VALUES (%s, %s, 1)
            """, (email, google_id))
            cone.commit()
            user = {
                "id": cursor.lastrowid,
                "email": email,
                "es_admin": 0,
                "verificado": 1
            }

        cone.close()
        root.after(0, lambda: finalizar_login(root, user))

    except Exception as e:
        try:
            import traceback
            log_error(f"Error login Google: {e}")
            log_error(traceback.format_exc())
        except Exception:
            log_error(f"Error login Google: {e}")
        root.after(0, lambda: dialog_error(root, "Error", "No se pudo iniciar sesion con Google."))
        


def login_google(root):
    """Lanza el login con Google en segundo plano."""
    if not _GOOGLE_OK:
        dialog_error(root, "Error", "Google Login no está disponible.")
        return
    threading.Thread(
        target=login_google_proceso,
        args=(root,),
        daemon=True
    ).start()


# ======================================================
# VERIFICACIÓN EMAIL (AISLADA Y SEGURA)
# ======================================================
def abrir_ventana_verificacion(root, email, password_hash, codigo):
    """Ventana para verificar el código de email."""
    codigo = str(codigo)
    from Dialogs import dialog_error, dialog_info
    win = tk.Toplevel(root)
    apply_chrome(win, "Verificación", 360, 230, min_w=320, min_h=210, state_key="verificacion")
    centrar_ventana(win, 360, 230)

    content = tk.Frame(win, bg=BG_MAIN)
    content.pack(fill="both", expand=True)

    gradient = tk.Canvas(content, highlightthickness=0, bd=0)
    gradient.place(x=0, y=0, relwidth=1, relheight=1)
    win.bind("<Configure>", lambda e: draw_gradient(gradient, BG_MAIN, BG_GRADIENT))

    card = tk.Frame(
        content,
        bg=BG_CARD,
        padx=22,
        pady=18,
        highlightbackground=BORDER,
        highlightthickness=1
    )
    card.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(
        card,
        text="Ingresá el código enviado a tu email",
        bg=BG_CARD,
        fg=FG_TEXT,
        font=FONT_SUBTITLE,
        wraplength=260,
        justify="center"
    ).pack(pady=(0, 10))

    entry = tk.Entry(
        card,
        justify="center",
        bg=BG_INPUT,
        fg=FG_TEXT,
        insertbackground=FG_TEXT,
        relief="flat",
        font=FONT_INPUT
    )
    entry.pack(fill="x", ipady=6, pady=(0, 12))

    def verificar():
        if entry.get().strip() != codigo:
            dialog_error(root, "Error", "Código incorrecto")
            return

        if Usuarios.existe_usuario(email):
            dialog_error(root, "Error", "La cuenta ya existe")
            win.destroy()
            return

        if not Usuarios.registrar_verificado(email, password_hash):
            dialog_error(root, "Error", "No se pudo crear la cuenta")
            
            return
        
        dialog_info(root, "Registro exitoso", "Cuenta creada correctamente")
        
        win.destroy()

    dark_button(card, "Verificar", verificar, primary=True).pack(fill="x", ipady=6)


# ======================================================
# LOGIN UI
# ======================================================
def login():
    """Construye la UI de login."""

    root = tk.Tk()
    apply_chrome(root, "StockARG", 420, 550, min_w=380, min_h=500, state_key="login")
    centrar_ventana(root, 420, 550)
    bring_to_front(root)

    # =========================
    # CONTENT
    # =========================
    content = tk.Frame(root, bg=BG_MAIN)
    content.pack(fill="both", expand=True)

    gradient = tk.Canvas(content, highlightthickness=0, bd=0)
    gradient.place(x=0, y=0, relwidth=1, relheight=1)
    root.bind("<Configure>", lambda e: draw_gradient(gradient, BG_MAIN, BG_GRADIENT))

    card = tk.Frame(
        content,
        bg=BG_CARD,
        padx=30,
        pady=30,
        highlightbackground=BORDER,
        highlightthickness=1
    )
    card.place(relx=0.5, rely=0.5, anchor="center")

    # =========================
    # TEXT
    # =========================
    tk.Label(
        card,
        text="Bienvenido a StockARG",
        font=FONT_H1,
        bg=BG_CARD,
        fg=FG_TEXT
    ).pack(pady=(0, 5))
    # =========================
    # ENTRIES
    # =========================
    user_icon = load_icon(resource_path("Assets", "usuario.png"))
    pass_icon = load_icon(resource_path("Assets", "proteger.png"))
    root._login_icons = [user_icon, pass_icon]

    tk.Label(card, text="Email", fg=FG_MUTED, bg=BG_CARD, font=FONT_SUBTITLE).pack(anchor="w")
    email_entry = dark_entry_with_icon(card, user_icon)

    tk.Label(card, text="Contraseña", fg=FG_MUTED, bg=BG_CARD, font=FONT_SUBTITLE).pack(anchor="w", pady=(6, 0))
    password_entry = dark_entry_with_icon(card, pass_icon)
    password_entry.config(show="*")

    # =========================
    # ACTIONS
    # =========================
    def iniciar():
        if not email_entry.get().strip() or not password_entry.get().strip():
            dialog_error(root, "Error", "Por favor completar todos los campos")
            return
        user = Usuarios.login(email_entry.get(), password_entry.get())
        if user == "GOOGLE_SIN_PASSWORD":
            dialog_error(root, "Error", "La cuenta fue creada con Google. Usá \"Continuar con Google\".")
            return
        if not user:
            dialog_error(root, "Error", "Credenciales incorrectas")
            return
        finalizar_login(root, user)

    def registrar():
        email = email_entry.get()
        password = password_entry.get()
        if not email.strip() or not password.strip():
            dialog_error(root, "Error", "Por favor completar todos los campos")
            return

        if not email_valido(email):
            dialog_error(root, "Error", "Email inválido")
            return

        if not password_valida(password):
            dialog_error(root, "Error", "La contraseña debe tener al menos 8 caracteres\ny contener letras y números")
            return

        if Usuarios.existe_usuario(email):
            dialog_error(root, "Error", "El email ya está registrado")
            return

        codigo = generar_codigo()
        password_hash = hash_password(password)

        if not enviar_codigo(email, codigo):
            dialog_error(root, "Error", "No se pudo enviar el código")
            return

        abrir_ventana_verificacion(root,email, password_hash, codigo)

    dark_button(card, "Iniciar sesión", iniciar, primary=True)\
        .pack(fill="x", pady=(0, 10), ipady=10)

    dark_button(card, "Registrarse", registrar)\
        .pack(fill="x", pady=(0, 10), ipady=8)

    dark_button(card, "Continuar con Google", lambda: login_google(root))\
        .pack(fill="x", ipady=8)

    root.mainloop()

