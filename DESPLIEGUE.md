# Despliegue

La API corre en un servidor propio, detrás de Caddy, junto a otro proyecto que
ya usa ese host. El frontend va aparte, en Cloudflare Workers.

```
navegador -> Caddy (TLS) -> contenedor stockarg-api -> PostgreSQL del servidor
```

## Lo que tiene que existir en el servidor

- Docker con el plugin de compose.
- Caddy corriendo en una red de docker, con el fragmento de
  [deploy/Caddyfile.fragmento](deploy/Caddyfile.fragmento) incluido en su
  Caddyfile.
- PostgreSQL con una base **propia de StockARG**, separada de la del otro
  proyecto:

  ```bash
  docker exec -it postgres psql -U postgres \
    -c "CREATE USER stockarg WITH PASSWORD '<clave>'" \
    -c "CREATE DATABASE stockarg OWNER stockarg"
  ```

- El DNS de `api-stockarg.aaronbrumat.com.ar` apuntando al servidor.

## Configuración

`backend/.env` en el servidor, a partir de
[backend/.env.example](backend/.env.example). Lo mínimo:

| Variable                 | Valor                                                          |
| ------------------------ | -------------------------------------------------------------- |
| `ENVIRONMENT`            | `production`                                                    |
| `SECRET_KEY`             | 48 bytes al azar, distinta de la de desarrollo                   |
| `DATABASE_URL`           | `postgresql+psycopg://stockarg:<clave>@postgres:5432/stockarg`   |
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

Las redes de docker se toman del entorno: `RED_DEL_PROXY` (la de Caddy) y
`RED_DE_LA_BASE` (la de PostgreSQL). Si en el servidor se llaman distinto, hay
que exportarlas antes de desplegar.

## Desplegar

```bash
git pull
./deploy/desplegar.sh
```

El script, en orden:

1. respalda la base con `pg_dump` en `/var/backups/stockarg`;
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
gunzip -c /var/backups/stockarg/stockarg-<marca>.sql.gz \
  | docker exec -i postgres psql -U stockarg -d stockarg
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

Todavía no está desplegado. Va a Cloudflare Workers, en
`stockarg.aaronbrumat.com.ar`, apuntando a esta API.
