# StockARG

Sistema de gestión de stock, ventas, clientes y proveedores para un comercio.

> Segunda versión del proyecto: nació como aplicación de escritorio y hoy es
> una aplicación web, con una demo pública para probarla sin instalar nada.

## Qué resuelve

Nació del problema real de controlar mercadería con planillas separadas: los
productos en una, las ventas en otra, y ninguna forma de saber qué pasó con el
stock entre ayer y hoy. Unifica las cuatro cosas y deja traza de cada
movimiento.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Pydantic, PostgreSQL 16
- **Migraciones**: Alembic
- **Frontend**: Next.js, React, TypeScript, Tailwind
- **Pruebas**: pytest, sin contenedores ni base externa
- **Despliegue**: frontend en Cloudflare Workers, API y base en un host propio

## Estructura

```
backend/
  app/
    core/        configuración y seguridad
    db/          base declarativa y sesión
    models/      modelo de dominio
    schemas/     entrada y salida de la API
    services/    reglas de negocio
    api/routes/  endpoints
  alembic/       migraciones de esquema
  tests/         suite de pytest
frontend/        aplicación web
docs/            documentación y diagramas
```

## Puesta en marcha

### 1. Base de datos

```bash
docker compose up -d db
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
```

`SECRET_KEY` es obligatoria y no tiene valor por defecto: la aplicación no
arranca sin ella, y rechaza valores de relleno conocidos. Generar una con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Después, aplicar el esquema y levantar la API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

La API queda en `http://127.0.0.1:8000` y `GET /salud` informa si la base
responde.

### 3. Pruebas

```bash
pytest
```

La suite usa SQLite en memoria: no necesita Docker ni PostgreSQL.

## Modelo de datos

Catorce tablas. Las entidades que puede tener un sandbox de demo llevan una
columna de partición, de modo que los datos de la aplicación y los de cada
visitante nunca se mezclan.

La unicidad de correo, código de barras, documento y CUIT se resuelve con
índices parciales: uno sobre las filas de la aplicación y otro por sesión de
demo. Un `UNIQUE` común impediría que dos visitantes recibieran el mismo
catálogo sembrado, y un `UNIQUE` compuesto con la sesión no serviría, porque
en SQL dos nulos no son iguales entre sí y la aplicación real terminaría
admitiendo duplicados.

## Seguridad

- La clave de firma es obligatoria, sin valor por defecto ni de relleno.
- En producción, la documentación interactiva de la API y el esquema OpenAPI
  devuelven 404.
- CORS restringido a los orígenes declarados, sin comodines.
- Contraseñas con bcrypt; nunca se escriben en un log.
- Ninguna entidad con historial se borra físicamente.
- Los secretos viven fuera del repositorio, y cada push escanea la historia
  completa en busca de credenciales filtradas.

## Estado

En desarrollo. Fase 0 completa: estructura, modelo de dominio, migración
inicial, suite de pruebas e integración continua.

## Licencia

Proyecto personal de [Aaron Brumat](https://aaronbrumat.com.ar).
