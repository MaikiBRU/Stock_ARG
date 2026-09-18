# StockARG

Gestión de stock, ventas, clientes y proveedores para un comercio chico.

> Segunda versión del proyecto: nació como aplicación de escritorio y hoy es
> una aplicación web, con una demo pública para probarla sin instalar nada y
> sin crear una cuenta.

## Qué resuelve

Controlar mercadería con planillas sueltas termina siempre igual: los productos
en una, las ventas en otra y ninguna forma de saber qué pasó con el stock entre
ayer y hoy. StockARG une las cuatro cosas y deja traza de cada movimiento.

- **Punto de venta** con búsqueda por código de barras, varios medios de cobro,
  vuelto y comprobante interno en PDF.
- **Stock** con mínimos por producto, vencimientos, bajas con motivo y el
  historial completo de movimientos.
- **Compras** que dan entrada a la mercadería y actualizan el costo.
- **Reportes** de ventas, rubros, medios de cobro y rentabilidad.
- **Tres roles**: propietario, encargado y vendedor, con permisos distintos.

## Demo pública

Cualquiera puede abrir un comercio de prueba, con tres semanas de datos ya
cargados, que se borra solo a los 45 minutos. El diseño está explicado en
[DEMO.md](DEMO.md): cómo se aísla cada visitante de la aplicación real, qué
cupos tiene y cómo se limpia.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, PostgreSQL 16
- **Migraciones**: Alembic
- **Frontend**: Next.js, React, TypeScript, Tailwind
- **Pruebas**: pytest, sin contenedores ni base externa
- **Despliegue**: frontend en Cloudflare Workers, API y base en un host propio

## Estructura

```
backend/
  app/
    core/        configuración, seguridad y parámetros vivos
    db/          base declarativa, sesión y aislamiento por partición
    models/      modelo de dominio
    schemas/     entrada y salida de la API
    services/    reglas de negocio
    api/routes/  endpoints
  alembic/       migraciones de esquema
  tests/         suite de pytest
deploy/              compose de producción, script de despliegue y Caddy
docker-compose.yml   entorno local: base y API
DEMO.md              diseño de la demo pública
DESPLIEGUE.md        cómo se despliega y cómo se vuelve atrás
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
arranca sin ella y rechaza valores de relleno conocidos. Generar una con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Después, aplicar el esquema y levantar la API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

La API queda en `http://127.0.0.1:8000`, `GET /salud` informa si la base
responde y, fuera de producción, la documentación interactiva está en `/docs`.

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
catálogo sembrado, y un `UNIQUE` compuesto con la sesión no serviría, porque en
SQL dos nulos no son iguales entre sí y la aplicación real terminaría
admitiendo duplicados.

## Seguridad

- La clave de firma es obligatoria, sin valor por defecto ni de relleno.
- Contraseñas con bcrypt; nunca se escriben en un log.
- Cerrar sesión invalida de verdad el token, y cambiar o recuperar la
  contraseña cierra las demás sesiones abiertas.
- Los totales se calculan en el servidor: un total enviado por el cliente se
  rechaza.
- Las operaciones de stock corren en transacción con bloqueo de fila.
- El aislamiento entre la aplicación y cada sandbox se impone en la capa ORM,
  no solo en cada consulta.
- En producción, la documentación interactiva y el esquema OpenAPI devuelven
  404, y CORS queda restringido a los orígenes declarados.
- Ninguna entidad con historial se borra físicamente.
- Los secretos viven fuera del repositorio, y cada push escanea la historia
  completa en busca de credenciales filtradas.

## Estado

Backend completo: cuentas, catálogo, stock, punto de venta, clientes,
proveedores, compras, reportes, administración y demo pública. Frontend en
desarrollo.

## Licencia

Proyecto personal de [Aaron Brumat](https://aaronbrumat.com.ar).
