"use client";

import { ChevronDown } from "lucide-react";
import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { useTextos } from "@/i18n/proveedor";

export const claseDeEntrada =
  "h-9 w-full rounded-lg border border-borde bg-superficie px-3 text-sm text-texto shadow-xs outline-none transition-colors placeholder:text-suave/70 hover:border-borde-fuerte focus-visible:border-marca focus-visible:ring-3 focus-visible:ring-marca/15 focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-sutil disabled:text-suave aria-invalid:border-alerta";

type Envoltura = {
  etiqueta: string;
  ayuda?: ReactNode;
  error?: string | null;
  opcional?: boolean;
  className?: string;
};

function Marco({
  id,
  etiqueta,
  ayuda,
  error,
  opcional,
  className = "",
  children,
}: Envoltura & { id: string; children: ReactNode }) {
  const { t } = useTextos();
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-[13px] font-medium text-texto">
        {etiqueta}
        {opcional && (
          <span className="ml-1 font-normal text-suave">({t.opcional})</span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${id}-ayuda`} className="text-xs text-alerta">
          {error}
        </p>
      ) : (
        ayuda && (
          <p id={`${id}-ayuda`} className="text-xs text-suave">
            {ayuda}
          </p>
        )
      )}
    </div>
  );
}

/** Campo de texto con su etiqueta, ayuda y error. */
export function Campo({
  etiqueta,
  ayuda,
  error,
  opcional,
  className,
  ...entrada
}: Envoltura & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <Marco {...{ id, etiqueta, ayuda, error, opcional, className }}>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={ayuda || error ? `${id}-ayuda` : undefined}
        className={claseDeEntrada}
        {...entrada}
      />
    </Marco>
  );
}

/** Lista desplegable con su etiqueta. */
export function Selector({
  etiqueta,
  ayuda,
  error,
  opcional,
  className,
  children,
  ...seleccion
}: Envoltura & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <Marco {...{ id, etiqueta, ayuda, error, opcional, className }}>
      <SelectorSuelto id={id} {...seleccion}>
        {children}
      </SelectorSuelto>
    </Marco>
  );
}

/** Lista desplegable sin etiqueta visible (para barras de filtros). */
export function SelectorSuelto({
  className = "",
  children,
  ...seleccion
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={`relative ${className}`}>
      <select
        className={`${claseDeEntrada} cursor-pointer appearance-none pr-8`}
        {...seleccion}
      >
        {children}
      </select>
      <ChevronDown
        size={15}
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-suave"
      />
    </div>
  );
}

/** Texto largo con su etiqueta. */
export function AreaDeTexto({
  etiqueta,
  ayuda,
  error,
  opcional,
  className,
  ...area
}: Envoltura & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <Marco {...{ id, etiqueta, ayuda, error, opcional, className }}>
      <textarea
        id={id}
        rows={3}
        className={`${claseDeEntrada} h-auto py-2`}
        {...area}
      />
    </Marco>
  );
}

/** Casilla de verificacion con su texto al lado. */
export function Casilla({
  etiqueta,
  className = "",
  ...entrada
}: { etiqueta: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label
      className={`inline-flex cursor-pointer items-center gap-2 text-sm select-none ${className}`}
    >
      <input
        type="checkbox"
        className="size-4 cursor-pointer rounded border-borde accent-marca"
        {...entrada}
      />
      {etiqueta}
    </label>
  );
}
