# Demo pública

Cualquier visitante del portfolio puede usar StockARG sin crear una cuenta.
Recibe un comercio propio, con datos de ejemplo, que vive unos minutos y
después se borra solo.

```
Portfolio  ->  "Probar la demo"  ->  POST /demo/sesion  ->  panel con datos
                                           |
                                  sandbox temporal
                                           |
                           vence o se termina -> datos borrados
```

La aplicación real (cuentas, roles, administración) no cambia. El sandbox es
una segunda identidad, paralela, que comparte la base pero no los datos.

---

## 1. Alta de un sandbox

`POST /demo/sesion`: público, sin credenciales y sin cuerpo.

1. **Límite por IP.** Ventana deslizante de una hora por dirección
   (`DEMO_RATE_LIMIT_PER_HOUR`). La IP sale de `X-Forwarded-For`, que Caddy
   reescribe, y se guarda solo como HMAC con la clave de la aplicación.
2. **Tope global.** Se cuentan en la base las sesiones vigentes contra
   `DEMO_MAX_ACTIVE_SESSIONS`. Si está completo, responde 503 con
   `Retry-After`.
3. **Sesión.** El id es `secrets.token_urlsafe(32)`: 43 caracteres aleatorios,
   no una secuencia.
4. **Semilla.** Se carga un kiosco verosímil a través de los mismos servicios
   que usa la aplicación (`services/demo_semilla.py`):
   - 7 categorías y 33 productos con precios en pesos;
   - 6 proveedores y 12 clientes;
   - 3 usuarios, uno por rol;
   - tres semanas de compras y ventas, con un ticket anulado.

   El stock entra por compras y sale por ventas, así que cada movimiento cuadra
   con el stock del producto. Hay productos bajo mínimo, por vencer y vencidos,
   para que el panel tenga alertas reales. La semilla aleatoria es distinta por
   sesión.
5. **Token.** Se devuelve un JWT:

   ```json
   { "sub": "demo:<id>", "typ": "demo", "sid": "<id>", "rol": "propietario", "sv": 0, "exp": "<vencimiento>" }
   ```

   El mismo token vuelve como cookie `HttpOnly`, que es la que usa el
   navegador; el del cuerpo queda para `curl` y para los clientes que no son un
   navegador. Guardarlo en `localStorage` sería entregárselo entero al primer
   XSS.

La sesión y la semilla van en una sola transacción. Si algo falla a mitad de
camino no queda ni la sesión ni ninguna fila suelta.

### Por qué el token nombra un rol y no un usuario

El token apunta al sandbox y al rol con el que se lo recorre. Así sigue
valiendo después de reiniciar, cuando los usuarios se vuelven a crear con otros
ids. `POST /demo/sesion/rol` devuelve otro token para recorrer la demo como
encargado o vendedor y ver qué cambia en cada pantalla.

---

## 2. Aislamiento

Todas las tablas del dominio tienen `id_sesion_demo`:

| Valor      | Significado                  |
| ---------- | ---------------------------- |
| `NULL`     | datos de la aplicación real  |
| `<id>`     | datos de ese sandbox         |

El aislamiento tiene tres capas, y cada una alcanza por sí sola para impedir
que se crucen datos.

1. **Servicios.** Cada consulta filtra por la partición que recibe de la ruta.
2. **Capa ORM** (`app/db/particion.py`). La dependencia de autenticación fija
   la partición del usuario en la sesión de base, y desde ahí:
   - toda lectura se restringe a esa partición: listas, conteos,
     `Session.get`, updates y deletes masivos, y cargas de relaciones;
   - un flush que cree, mueva o borre una fila de otra partición aborta con
     `FugaDeParticion`.

   Una ruta nueva que se olvide de filtrar sigue aislada. Si intenta escribir
   fuera de su partición, falla en las pruebas en lugar de mezclar datos en
   producción.
3. **Claves foráneas.** Todo cuelga de `sesiones_demo` con `ON DELETE
   CASCADE`. No puede existir una fila de sandbox sin su sesión.

El aislamiento va en los dos sentidos. Pedir un registro de otra partición
devuelve **404, no 403**, así la respuesta no confirma que exista. Un token de
la aplicación que apunte a un usuario de sandbox se rechaza, porque los ids de
usuario son una secuencia y se pueden adivinar.

Los parámetros configurables (umbrales, tope de descuento) viajan en la sesión
de base de cada petición y no en una caché global. Si no fuera así, el tope
que fija el dueño de un sandbox podría alcanzar a un vendedor real que cobra en
el mismo instante.

---

## 3. Qué se puede hacer

Todo lo de la aplicación, dentro del sandbox:

- ventas, anulaciones y comprobantes;
- stock y compras;
- clientes y proveedores;
- reportes y exportaciones;
- administración de usuarios del sandbox, auditoría y configuración.

Lo que se cierra:

- `PUT /auth/contrasena` (403): los usuarios de la demo no tienen contraseña y
  se entra por token.
- Ingreso por contraseña: `/auth/login` solo busca cuentas de la aplicación.

---

## 4. Vigencia

La sesión muere por la primera de dos condiciones:

- vencimiento absoluto: `DEMO_SESSION_TTL_MINUTES` desde la creación;
- inactividad: `DEMO_IDLE_TIMEOUT_MINUTES` desde la última petición.

Se decide **en cada petición**, no en la limpieza: una sesión vencida deja de
funcionar en el acto, aunque sus filas sigan en la base. Una sesión
desconocida, vencida, terminada o un token armado a mano reciben exactamente
la misma respuesta 401.

La última actividad se anota como mucho cada 30 segundos, para no sumarle una
escritura a cada lectura.

---

## 5. Cupos

Un visitante anónimo escribe en una base compartida, así que todo está
acotado.

**Filas por sandbox.** Se controlan en el flush (`services/demo.py`), así que
alcanzan a cualquier camino que cree filas, incluidas las importaciones. Si se
pasa un tope, responde 429 con `codigo: cupo_agotado`.

| Tabla                  | Tope                    |
| ---------------------- | ----------------------- |
| productos              | `DEMO_MAX_PRODUCTOS`    |
| ventas                 | `DEMO_MAX_VENTAS`       |
| líneas de venta        | 4000                    |
| movimientos de stock   | 8000                    |
| compras / sus líneas   | 200 / 3000              |
| clientes / proveedores | 300 / 100               |
| usuarios               | 15                      |
| auditoría              | 2000                    |

**Acciones por sandbox.** Cada exportación, comprobante PDF, importación o
vista previa descuenta un uso *antes* de ejecutarse, con un `UPDATE`
condicional que no deja pasar dos pedidos simultáneos con el último lugar. El
uso se consume aunque la operación falle, porque lo que se acota es el trabajo
del servidor.

| Acción          | Tope                     |
| --------------- | ------------------------ |
| exportaciones   | `DEMO_MAX_EXPORTACIONES` |
| importaciones   | `DEMO_MAX_IMPORTACIONES` |

Una prueba recorre las rutas y falla si aparece una exportación o importación
nueva sin su cupo.

---

## 6. Reinicio y fin

- `POST /demo/sesion/reiniciar` borra el sandbox y lo vuelve a sembrar con el
  **mismo token**. Conserva el vencimiento y los contadores de acciones: si los
  renovara, reiniciar serviría para tener una demo eterna o cupos infinitos. Se
  permiten 6 reinicios por hora por sesión.
- `POST /demo/sesion/terminar` borra todo en el acto.
- `GET /demo/sesion` informa el vencimiento, el tiempo restante, el rol y el
  uso de los cupos. Es lo que alimenta la franja de modo demo del frontend.

---

## 7. Limpieza

Las tres vías llaman a la misma función idempotente, `purgar_vencidas`:

1. **Tarea en segundo plano** dentro del proceso de la API, cada
   `DEMO_CLEANUP_INTERVAL_SECONDS` (0 la apaga). Si se cae, la demo sigue
   siendo correcta: solo se acumulan filas.
2. **`POST /demo/mantenimiento/limpieza`**, con la cabecera
   `X-Demo-Mantenimiento-Token`. Sin `DEMO_MAINTENANCE_TOKEN` configurado
   responde 404, y con un token equivocado también: nunca queda abierta por
   omisión ni confirma que existe.
3. **El visitante**, al terminar la demo.

Solo borra filas de `sesiones_demo`; lo demás cae por la clave foránea. Por
construcción no puede tocar filas con `id_sesion_demo` en `NULL`.

---

## 8. Interruptor

Con `DEMO_ENABLED=false`, todo `/demo/*` responde 404 y los tokens de demo ya
emitidos dejan de valer en la petición siguiente.

---

## 9. Variables de entorno

| Variable                        | Valor por defecto | Significado                              |
| ------------------------------- | ----------------- | ---------------------------------------- |
| `DEMO_ENABLED`                  | `true`            | Interruptor general                      |
| `DEMO_SESSION_TTL_MINUTES`      | `45`              | Vida máxima de un sandbox                |
| `DEMO_IDLE_TIMEOUT_MINUTES`     | `20`              | Vida sin actividad                       |
| `DEMO_MAX_ACTIVE_SESSIONS`      | `200`             | Tope global de sandboxes vigentes        |
| `DEMO_RATE_LIMIT_PER_HOUR`      | `12`              | Sandboxes por IP por hora                |
| `DEMO_CLEANUP_INTERVAL_SECONDS` | `300`             | Período de la limpieza; `0` la apaga     |
| `DEMO_MAINTENANCE_TOKEN`        | sin valor         | Secreto de la limpieza manual            |
| `DEMO_MAX_PRODUCTOS`            | `300`             | Productos por sandbox                    |
| `DEMO_MAX_VENTAS`               | `800`             | Ventas por sandbox                       |
| `DEMO_MAX_IMPORTACIONES`        | `15`              | Importaciones y vistas previas           |
| `DEMO_MAX_EXPORTACIONES`        | `40`              | Exportaciones y comprobantes             |

---

## 10. Límites conocidos

- **Los límites por IP y de reinicios viven en memoria del proceso.** Con una
  sola instancia de la API, que es el despliegue previsto, alcanza. Con varias
  instancias pasarían a ser por instancia. El tope global de sesiones está en
  la base y sigue valiendo.
- **El tope global es blando.** Dos altas exactamente simultáneas pueden
  pasarlo por una sesión. Los cupos por sandbox, en cambio, son exactos.

---

## 11. Pruebas

```bash
python -m pytest backend/tests/test_demo.py backend/tests/test_particion.py
```

Corren sin contenedores: SQLite en memoria y la aplicación real por encima.
Cubren:

- alta y contenido de la semilla, y que el stock cuadre con sus movimientos;
- que una semilla fallida no deje rastros;
- aislamiento entre sandboxes y con la aplicación: lecturas, escrituras, 404,
  auditoría y configuración;
- el cerrojo ORM con cada tipo de consulta;
- vencimiento, inactividad y tokens inválidos con la misma respuesta;
- roles, cada cupo y el límite por IP, el tope global y la IP hasheada;
- reinicio con el mismo token, fin, limpieza manual e idempotente, y el
  interruptor.
