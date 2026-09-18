/**
 * Cliente de la API.
 *
 * Todas las peticiones van con `credentials: "include"`: la sesion vive
 * en una cookie HttpOnly que esta pagina no puede leer ni escribir, asi
 * que un XSS no se lleva el token puesto.
 */

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
    const datos = await respuesta.json().catch(() => null);
    const [codigo, mensaje] = leerDetalle(datos, respuesta.status);
    throw new ErrorDeApi(respuesta.status, codigo, mensaje);
  }

  const contenido = await respuesta.blob();
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(contenido);
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
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
