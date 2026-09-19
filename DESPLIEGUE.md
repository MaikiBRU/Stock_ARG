# Despliegue

La API corre en la EC2 de us-east-2 (Ubuntu, 1 GB), que comparte con Data
Center y BarberApp. El frontend va aparte, en Cloudflare Workers.

```
navegador -> Caddy (systemd, TLS) -> 127.0.0.1:8002 -> contenedor stockarg-api
                                                          |
                                     red data-center_default
                                                          v
                               data-center-db-1 (PostgreSQL 16), base "stockarg"
```

StockARG usa su propia base y su propio usuario dentro del PostgreSQL que ya
corre en el servidor: las tablas de Data Center no se tocan, y no se paga la
memoria de una segunda instancia.

## Lo que tiene que existir en el servidor

- Docker con el plugin de compose, y Caddy como servicio del sistema.
- El repositorio en `~/stockarg`.
- La base y el usuario de StockARG (una sola vez; `app` es el superusuario de
  ese PostgreSQL):

  ```bash
  docker exec -i data-center-db-1 psql -U app -d postgres     -c "CREATE ROLE stockarg LOGIN PASSWORD '<clave>'"     -c "CREATE DATABASE stockarg OWNER stockarg"
  ```

- El bloque de [deploy/Caddyfile.fragmento](deploy/Caddyfile.fragmento) al final
  de `/etc/caddy/Caddyfile`, validado y recargado:

  ```bash
  sudo caddy validate --config /etc/caddy/Caddyfile
  sudo systemctl reload caddy
  ```

- En Cloudflare, un registro `A` `api-stockarg` a la IP del servidor, **sin
  proxy** (nube gris): el certificado lo saca Caddy.

## Configuración

`backend/.env` en el servidor, a partir de
[backend/.env.example](backend/.env.example). Lo mínimo:

| Variable                 | Valor                                                          |
| ------------------------ | -------------------------------------------------------------- |
| `ENVIRONMENT`            | `production`                                                    |
| `SECRET_KEY`             | 48 bytes al azar, distinta de la de desarrollo                   |
| `DATABASE_URL`           | `postgresql+psycopg://stockarg:<clave>@data-center-db-1:5432/stockarg` |
| `ALLOWED_ORIGINS`        | `https://stockarg.aaronbrumat.com.ar`                            |
| `FRONTEND_URL`           | `https://stockarg.aaronbrumat.com.ar`                            |
| `DEMO_MAINTENANCE_TOKEN` | otro valor al azar, si se quiere limpiar desde afuera            |

En producción, la documentación interactiva y el esquema OpenAPI responden 404,
y CORS queda limitado a esos orígenes.

### Correo

El alta de cuentas y la recuperación de contraseña mandan correo por SMTP. Con
Resend (plan gratuito: 3.000 por mes, 100 por día) y el dominio en Cloudflare:

| Variable            | Valor                                        |
| ------------------- | -------------------------------------------- |
| `SMTP_HOST`         | `smtp.resend.com`                            |
| `SMTP_PUERTO`       | `465`                                        |
| `SMTP_USUARIO`      | `resend`                                     |
| `SMTP_CONTRASENA`   | la API key de Resend (solo en el servidor)   |
| `EMAIL_FROM`        | `no-reply@stockarg.aaronbrumat.com.ar`       |
| `EMAIL_FROM_NOMBRE` | `StockARG`                                   |

Para probarlo sin crear una cuenta en la app:

```sh
docker compose -f deploy/docker-compose.prod.yml exec api python -m app.probar_correo tu-correo@ejemplo.com
```

Cambiar de proveedor (Cloudflare Email Service, Brevo) es cambiar estas
variables: el código no depende de ninguno.

La red de la base se toma de `RED_DE_LA_BASE` (por defecto
`data-center_default`) y el puerto local de `PUERTO_LOCAL` (por defecto 8002).

## Desplegar

```bash
git pull
./deploy/desplegar.sh
```

El script, en orden:

1. respalda la base con `pg_dump` en `~/backups/stockarg`;
2. imprime el comando exacto para volver atrás, con la versión anterior y el
   archivo de respaldo;
3. construye la imagen y levanta la versión nueva;
4. espera a que `GET /salud` responda. Si no responde, muestra las últimas
   líneas del contenedor, repite cómo volver atrás y termina con error.

Las migraciones las aplica el contenedor al arrancar. Si una falla, el
contenedor no levanta y la versión anterior sigue atendiendo.

## Volver atrás

```bash
git checkout <version-anterior>
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Y, solo si hubo que revertir un cambio de esquema:

```bash
gunzip -c ~/backups/stockarg/stockarg-<marca>.sql.gz \
  | docker exec -i data-center-db-1 psql -U stockarg -d stockarg
```

## Después de desplegar

```bash
curl -s https://api-stockarg.aaronbrumat.com.ar/salud
curl -s -X POST https://api-stockarg.aaronbrumat.com.ar/demo/sesion | head -c 200
```

La primera cuenta que se registra queda como propietaria: conviene crearla
apenas termina el despliegue.

## Limpieza de la demo

La API borra sola los sandboxes vencidos cada `DEMO_CLEANUP_INTERVAL_SECONDS`.
Para forzarla desde afuera, con el token configurado:

```bash
curl -X POST https://api-stockarg.aaronbrumat.com.ar/demo/mantenimiento/limpieza \
  -H "X-Demo-Mantenimiento-Token: <token>"
```

## Frontend

Corre en Cloudflare Workers (plan gratuito) con el adaptador OpenNext, en
`stockarg.aaronbrumat.com.ar`. La configuración está en
[frontend/wrangler.jsonc](frontend/wrangler.jsonc) y
[frontend/open-next.config.ts](frontend/open-next.config.ts).

La dirección de la API se fija al compilar, desde
[frontend/.env.production](frontend/.env.production). Es pública: ahí nunca
va un secreto.

Primero tiene que estar la API respondiendo; si no, el sitio queda en línea
pero cada pantalla falla.

```bash
cd frontend
npx wrangler login      # una sola vez
npm run deploy          # compila con OpenNext y publica
```

El primer despliegue crea solo el registro DNS y el certificado del dominio
propio. La dirección `*.workers.dev` queda apagada. Para probar el paquete de
Workers en la máquina antes de publicar:

```bash
npm run preview
```

Volver atrás: en el panel de Cloudflare, Workers, `stockarg`, Deployments,
elegir la versión anterior y "Rollback".
