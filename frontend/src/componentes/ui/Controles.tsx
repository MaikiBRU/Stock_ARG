"use client";

import { Download, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type InputHTMLAttributes } from "react";

import { useTextos } from "@/i18n/proveedor";
import { descargar, mensajeDe } from "@/lib/api";

import { useAvisos } from "./Avisos";
import { claseDeEntrada } from "./Campo";

/** Caja de busqueda con lupa. */
export function Buscador({
  className = "",
  ...entrada
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={`relative ${className}`}>
      <Search
        size={15}
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-suave"
      />
      <input
        type="search"
        autoComplete="off"
        className={`${claseDeEntrada} pl-9`}
        {...entrada}
      />
    </div>
  );
}

/** Grupo de opciones excluyentes, como pestanas chicas. */
export function Segmentos<T extends string>({
  opciones,
  valor,
  alCambiar,
  etiqueta,
}: {
  opciones: { valor: T; texto: string }[];
  valor: T;
  alCambiar: (valor: T) => void;
  etiqueta: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={etiqueta}
      className="inline-flex h-9 items-center rounded-lg border border-borde bg-sutil p-0.5"
    >
      {opciones.map((opcion) => {
        const elegida = opcion.valor === valor;
        return (
          <button
            key={opcion.valor}
            type="button"
            role="radio"
            aria-checked={elegida}
            onClick={() => alCambiar(opcion.valor)}
            className={`h-full rounded-md px-3 text-[13px] font-medium transition-colors ${
              elegida
                ? "bg-superficie text-texto shadow-xs"
                : "text-suave hover:text-texto"
            }`}
          >
            {opcion.texto}
          </button>
        );
      })}
    </div>
  );
}

/** Pestanas que son enlaces: cada una es una ruta propia. */
export function Pestanas({
  pestanas,
}: {
  pestanas: { href: string; texto: string }[];
}) {
  const ruta = usePathname();
  return (
    <nav className="flex gap-5 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-borde)] [scrollbar-width:none]">
      {pestanas.map((pestana) => {
        const activa = ruta === pestana.href;
        return (
          <Link
            key={pestana.href}
            href={pestana.href}
            aria-current={activa ? "page" : undefined}
            className={`border-b-2 pb-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
              activa
                ? "border-marca text-texto"
                : "border-transparent text-suave hover:text-texto"
            }`}
          >
            {pestana.texto}
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * Descarga en CSV o PDF. `ruta` ya trae los filtros; aca se agrega el
 * formato.
 */
export function Exportar({ ruta, nombre }: { ruta: string; nombre: string }) {
  const { t } = useTextos();
  const { avisar } = useAvisos();
  const [ocupado, setOcupado] = useState(false);

  async function bajar(formato: "csv" | "pdf") {
    setOcupado(true);
    try {
      const union = ruta.includes("?") ? "&" : "?";
      await descargar(
        `${ruta}${union}formato=${formato}`,
        `${nombre}.${formato}`,
      );
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div
      role="group"
      aria-label={t.exportar}
      className="inline-flex h-9 items-center overflow-hidden rounded-lg border border-borde bg-superficie text-sm shadow-xs"
    >
      <span className="flex items-center gap-1.5 pr-1 pl-3 text-suave">
        <Download size={15} aria-hidden />
        <span className="hidden sm:inline">{t.exportar}</span>
      </span>
      {(["csv", "pdf"] as const).map((formato) => (
        <button
          key={formato}
          type="button"
          disabled={ocupado}
          onClick={() => bajar(formato)}
          className="h-full px-2.5 font-medium hover:bg-sutil disabled:opacity-50"
        >
          {formato === "csv" ? t.exportarCsv : t.exportarPdf}
        </button>
      ))}
    </div>
  );
}
