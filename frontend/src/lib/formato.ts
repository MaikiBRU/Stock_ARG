/**
 * Importes en pesos y fechas en la zona del comercio (RNF-15).
 *
 * La API manda los importes como texto para no perder centavos en el
 * camino; aca se convierten solo para mostrarlos.
 */

import type { Idioma } from "@/i18n/textos";

const ZONA = "America/Argentina/Buenos_Aires";

function local(idioma: Idioma) {
  return idioma === "en" ? "en-US" : "es-AR";
}

/** Un importe en pesos, con separadores y dos decimales. */
export function pesos(valor: string | number, idioma: Idioma = "es") {
  return new Intl.NumberFormat(local(idioma), {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 2,
  }).format(Number(valor));
}

/** Una cantidad entera, con separador de miles. */
export function numero(valor: number, idioma: Idioma = "es") {
  return new Intl.NumberFormat(local(idioma)).format(valor);
}

/** Una fecha corta, siempre en la hora del comercio. */
export function fecha(valor: string, idioma: Idioma = "es") {
  return new Intl.DateTimeFormat(local(idioma), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: ZONA,
  }).format(new Date(valor));
}
