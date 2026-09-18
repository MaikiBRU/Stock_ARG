/**
 * Marca de sesion para decidir rutas en el servidor.
 *
 * La sesion de verdad es la cookie HttpOnly que pone la API, y esta
 * pagina no puede leerla: vive en otro subdominio. Para que el layout
 * del servidor sepa a donde mandar a alguien sin esperar a que la
 * pantalla cargue, se deja esta marca, que no vale nada por si misma.
 *
 * Falsificarla no sirve: la pagina carga, pero cada llamada a la API
 * responde 401 igual.
 */

export const MARCA = "stockarg_activa";
export const IDIOMA = "stockarg_idioma";

const UN_ANIO = 60 * 60 * 24 * 365;

function fijar(nombre: string, valor: string, segundos: number) {
  const seguro = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${nombre}=${valor}; Path=/; Max-Age=${segundos}; SameSite=Lax${seguro}`;
}

/** Deja constancia de que hay una sesion abierta. */
export function marcarSesion(minutos: number) {
  fijar(MARCA, "1", minutos * 60);
}

/** Borra la marca al cerrar sesion o al terminar la demo. */
export function olvidarSesion() {
  fijar(MARCA, "", 0);
}

/** Guarda el idioma elegido para que el servidor lo respete. */
export function guardarIdioma(idioma: "es" | "en") {
  fijar(IDIOMA, idioma, UN_ANIO);
}
