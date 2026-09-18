"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

import { useTextos } from "@/i18n/proveedor";

const ANCHOS = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

/**
 * Ventana modal sobre el <dialog> nativo.
 *
 * El navegador ya resuelve lo dificil: atrapa el foco adentro, lo
 * devuelve al cerrar, cierra con Esc y deja inerte el resto de la
 * pagina. El contenido se monta solo mientras esta abierta, asi cada
 * vez que se abre un formulario arranca limpio.
 */
export function Dialogo({
  abierto,
  alCerrar,
  titulo,
  descripcion,
  ancho = "md",
  children,
}: {
  abierto: boolean;
  alCerrar: () => void;
  titulo: ReactNode;
  descripcion?: ReactNode;
  ancho?: keyof typeof ANCHOS;
  children: ReactNode;
}) {
  const { t } = useTextos();
  const ref = useRef<HTMLDialogElement>(null);
  const idTitulo = useId();

  useEffect(() => {
    const dialogo = ref.current;
    if (!dialogo) return;
    if (abierto && !dialogo.open) {
      dialogo.showModal();
      // showModal enfoca el primer boton (la X de cerrar); se lleva el
      // foco al primer campo, que es donde se empieza a escribir.
      dialogo
        .querySelector<HTMLElement>(
          "input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled])",
        )
        ?.focus();
    }
    if (!abierto && dialogo.open) dialogo.close();
  }, [abierto]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={idTitulo}
      onCancel={(evento) => {
        // Esc: quien decide cerrar es el estado, no el navegador.
        evento.preventDefault();
        alCerrar();
      }}
      onMouseDown={(evento) => {
        // Un clic en el fondo (fuera de la caja) cierra.
        if (evento.target === ref.current) alCerrar();
      }}
      className={`m-auto max-h-[min(90dvh,56rem)] w-[calc(100%-2rem)] ${ANCHOS[ancho]} overflow-visible rounded-2xl border border-borde bg-superficie p-0 text-texto shadow-flotante backdrop:bg-transparent`}
    >
      {abierto && (
        <div className="aparecer flex max-h-[min(90dvh,56rem)] flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-borde px-5 py-4">
            <div className="min-w-0">
              <h2 id={idTitulo} className="text-base font-semibold">
                {titulo}
              </h2>
              {descripcion && (
                <p className="mt-0.5 text-sm text-suave">{descripcion}</p>
              )}
            </div>
            <button
              type="button"
              onClick={alCerrar}
              aria-label={t.cerrar}
              className="-mt-1 -mr-2 inline-flex size-8 items-center justify-center rounded-md text-suave hover:bg-sutil hover:text-texto"
            >
              <X size={16} aria-hidden />
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {children}
          </div>
        </div>
      )}
    </dialog>
  );
}

/** Botonera al pie de un dialogo. */
export function PieDeDialogo({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-5 -mb-4 mt-5 flex flex-wrap justify-end gap-2 border-t border-borde bg-fondo/60 px-5 py-3">
      {children}
    </div>
  );
}
