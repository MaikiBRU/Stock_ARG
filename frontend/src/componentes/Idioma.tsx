"use client";

import { Languages } from "lucide-react";
import { useRouter } from "next/navigation";

import { useTextos } from "@/i18n/proveedor";
import { guardarIdioma } from "@/lib/sesion";

/**
 * Cambia entre español e inglés. El idioma vive en una cookie que lee
 * el servidor, asi que alcanza con guardarla y volver a pedir la pagina.
 */
export function CambioDeIdioma({ className = "" }: { className?: string }) {
  const { t, idioma } = useTextos();
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => {
        guardarIdioma(idioma === "es" ? "en" : "es");
        router.refresh();
      }}
      title={t.cambiarIdioma}
      className={`inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[13px] text-suave transition-colors hover:bg-sutil hover:text-texto ${className}`}
    >
      <Languages size={15} aria-hidden />
      <span lang={idioma === "es" ? "en" : "es"}>{t.idioma}</span>
    </button>
  );
}

/** Marca del producto: isotipo y nombre. */
export function Logo({ compacto = false }: { compacto?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <span
        aria-hidden
        className="inline-flex size-7 items-center justify-center rounded-lg bg-marca text-sobre-marca"
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none">
          <path
            d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5v-7Z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <path
            d="M4 8.5 12 13l8-4.5M12 13v7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {!compacto && <span>StockARG</span>}
    </span>
  );
}
