# StockARG

Sistema de gestión de stock, ventas y clientes con interfaz moderna en Tkinter.

## Funcionalidades principales
- Login con email/contraseña y opción Google (si está configurado).
- ABM de Clientes, Proveedores y Productos.
- Ventas con control de stock y precios (auto y editable).
- Módulo de Stock con alertas por niveles y movimientos.
- Reportes y exportación a CSV/PDF.
- Panel de estado con logs del sistema.

## Requisitos
- Python 3.12+ (recomendado 3.13/3.14)
- MySQL 8+

Dependencias:
```
pip install -r requirements.txt
```
Opcional para PDF:
```
pip install -r requirements-optional.txt
```

## Configuración de base de datos
1. Crear la base de datos y usuario en MySQL.
2. Configurar credenciales en `Conexion.py`.
3. Ejecutar migraciones SQL ubicadas en `db_migrations/`:
   - `001_audit_and_indexes.sql` (si aplica en tu DB)
   - `002_movimientos_stock.sql`

## Configuración de correo y Google Login
- `email.env`: credenciales de envío de email (no subir a GitHub).
- `client_secret.json`: credenciales OAuth de Google (no subir a GitHub).

Se incluyen plantillas/ejemplos:
- `.env.example`

## Ejecutar la app
```
python Main.py
```

## Empaquetado (Windows)
Instalar PyInstaller:
```
pip install pyinstaller
```

Comando de build:
```
pyinstaller --noconsole --onefile --name StockARG Main.py --add-data "Assets;Assets"
```

Nota: si usás Google Login o email, agregá los archivos en el build local, pero no los subas al repo.


## Estructura
- `Main.py`: entrada principal
- `Menu.py`: navegación y vistas
- `Productos.py` / `Clientes.py` / `Proveedores.py` / `Ventas.py` / `Stock.py`
- `db_migrations/`: SQL de migraciones
