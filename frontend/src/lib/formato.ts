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

/** Un importe corto para ejes y tarjetas: $ 1,2 M. */
export function pesosCortos(valor: string | number, idioma: Idioma = "es") {
  return new Intl.NumberFormat(local(idioma), {
    style: "currency",
    currency: "ARS",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(valor));
}

/** Una cantidad, con separador de miles. */
export function numero(valor: number | string, idioma: Idioma = "es") {
  return new Intl.NumberFormat(local(idioma), {
    maximumFractionDigits: 2,
  }).format(Number(valor));
}

/**
 * Una fecha corta. Si viene sola ("2026-09-18") es un dia del
 * calendario y se muestra tal cual; si trae hora, se pasa a la del
 * comercio.
 */
export function fecha(valor: string, idioma: Idioma = "es") {
  const soloDia = /^\d{4}-\d{2}-\d{2}$/.test(valor);
  return new Intl.DateTimeFormat(local(idioma), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: soloDia ? "UTC" : ZONA,
  }).format(new Date(soloDia ? `${valor}T00:00:00Z` : valor));
}

/** Fecha y hora, en la hora del comercio. */
export function fechaHora(valor: string, idioma: Idioma = "es") {
  return new Intl.DateTimeFormat(local(idioma), {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: ZONA,
  }).format(new Date(valor));
}

/** Dia y mes abreviado, para ejes de graficos: "18 sep". */
export function diaCorto(valor: string, idioma: Idioma = "es") {
  return new Intl.DateTimeFormat(local(idioma), {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${valor}T00:00:00Z`));
}

/** Hoy en el calendario del comercio, como "AAAA-MM-DD". */
export function hoyEnElComercio() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: ZONA }).format(
    new Date(),
  );
}
