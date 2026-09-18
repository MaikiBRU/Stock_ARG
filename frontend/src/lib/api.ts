/**
 * Cliente de la API.
 *
 * Todas las peticiones van con `credentials: "include"`: la sesion vive
 * en una cookie HttpOnly que esta pagina no puede leer ni escribir, asi
 * que un XSS no se lleva el token puesto.
 */

import { MARCA, olvidarSesion } from "@/lib/sesion";

export const URL_DE_LA_API =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Falla que devolvio la API, con su codigo y su detalle. */
export class ErrorDeApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string | null,
    mensaje: string,
  ) {
    super(mensaje);
    this.name = "ErrorDeApi";
  }
}

type Detalle =
  | string
  | { mensaje?: string; codigo?: string; [clave: string]: unknown }
  | Array<{ msg?: string }>;

/** Saca de la respuesta algo que se le pueda mostrar a una persona. */
function leerDetalle(cuerpo: unknown, estado: number): [string | null, string] {
  const detalle = (cuerpo as { detail?: Detalle } | null)?.detail;

  if (typeof detalle === "string") return [null, detalle];
  if (Array.isArray(detalle)) {
    // Errores de validacion de FastAPI: se muestra el primero.
    return [null, detalle[0]?.msg ?? "Los datos enviados no son validos."];
  }
  if (detalle && typeof detalle === "object") {
    return [
      typeof detalle.codigo === "string" ? detalle.codigo : null,
      typeof detalle.mensaje === "string"
        ? detalle.mensaje
        : "No se pudo completar la operacion.",
    ];
  }
  if (estado >= 500) return [null, "El servidor tuvo un problema."];
  return [null, "No se pudo completar la operacion."];
}

type Opciones = Omit<RequestInit, "body"> & { cuerpo?: unknown };

// En estas rutas un 401 es "datos incorrectos", no una sesion vencida.
const RUTAS_DE_INGRESO = ["/auth/login", "/auth/google", "/auth/verificar"];

/**
 * Si la sesion vencio en medio del uso (la demo por inactividad, el
 * token por tiempo), cada pantalla mostraria "no autenticado" sin salida.
 * Se borra la marca y se vuelve al ingreso, avisando por que.
 */
function atenderSesionVencida(ruta: string, estado: number) {
  if (estado !== 401 || typeof window === "undefined") return;
  if (RUTAS_DE_INGRESO.some((r) => ruta.startsWith(r))) return;
  if (!document.cookie.includes(`${MARCA}=`)) return;
  olvidarSesion();
  // Recarga completa, y sin dejar la pagina vencida en el historial.
  window.location.replace("/ingresar?vencida=1");
}

/** Llama a la API y devuelve el cuerpo ya convertido. */
export async function pedir<T>(ruta: string, opciones: Opciones = {}) {
  const { cuerpo, headers, ...resto } = opciones;

  let respuesta: Response;
  try {
    respuesta = await fetch(`${URL_DE_LA_API}${ruta}`, {
      ...resto,
      credentials: "include",
      // Un FormData (subida de archivos) viaja tal cual: el navegador
      // arma el encabezado multipart con su separador.
      headers: {
        ...(cuerpo === undefined || cuerpo instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...headers,
      },
      body:
        cuerpo === undefined
          ? undefined
          : cuerpo instanceof FormData
            ? cuerpo
            : JSON.stringify(cuerpo),
    });
  } catch {
    // Sin red, o la API caida: no hay respuesta que interpretar.
    throw new ErrorDeApi(
      0,
      "sin_conexion",
      "No se pudo contactar al servidor.",
    );
  }

  if (respuesta.status === 204) return undefined as T;

  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    atenderSesionVencida(ruta, respuesta.status);
    const [codigo, mensaje] = leerDetalle(datos, respuesta.status);
    throw new ErrorDeApi(respuesta.status, codigo, mensaje);
  }
  return datos as T;
}

/** Descarga un archivo que genera la API (CSV o PDF). */
export async function descargar(ruta: string, nombre: string) {
  const respuesta = await fetch(`${URL_DE_LA_API}${ruta}`, {
    credentials: "include",
  });
  if (!respuesta.ok) {
    atenderSesionVencida(ruta, respuesta.status);
    const datos = await respuesta.json().catch(() => null);
    const [codigo, mensaje] = leerDetalle(datos, respuesta.status);
    throw new ErrorDeApi(respuesta.status, codigo, mensaje);
  }

  const contenido = await respuesta.blob();
  const direccion = URL.createObjectURL(contenido);
  const enlace = document.createElement("a");
  enlace.href = direccion;
  enlace.download = nombre;
  // Firefox solo descarga desde un enlace que esta en el documento, y
  // revocar la direccion en el mismo instante puede cortar la descarga.
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(direccion), 10_000);
}

/**
 * Arma "?a=1&b=2" salteando los valores vacios, para que un filtro sin
 * elegir no viaje como "a=" y la API lo tome como texto vacio.
 */
export function consulta(
  parametros: Record<string, string | number | boolean | null | undefined>,
) {
  const partes = new URLSearchParams();
  for (const [clave, valor] of Object.entries(parametros)) {
    if (valor === undefined || valor === null || valor === "" || valor === false)
      continue;
    partes.set(clave, String(valor));
  }
  const texto = partes.toString();
  return texto ? `?${texto}` : "";
}

/** Texto para mostrar de una falla cualquiera. */
export function mensajeDe(falla: unknown, respaldo: string) {
  return falla instanceof ErrorDeApi ? falla.message : respaldo;
}

/** Forma de las respuestas paginadas de la API. */
export type Pagina<T> = {
  items: T[];
  total: number;
  pagina: number;
  limite: number;
};
