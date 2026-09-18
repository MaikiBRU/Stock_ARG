import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** Caja con borde: la unidad basica de cada pantalla. */
export function Tarjeta({
  titulo,
  descripcion,
  accion,
  children,
  className = "",
  sinRelleno = false,
}: {
  titulo?: ReactNode;
  descripcion?: ReactNode;
  accion?: ReactNode;
  children: ReactNode;
  className?: string;
  sinRelleno?: boolean;
}) {
  return (
    <section
      className={`min-w-0 rounded-xl border border-borde bg-superficie shadow-xs ${className}`}
    >
      {(titulo || accion) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4">
          <div className="min-w-0">
            {titulo && (
              <h2 className="text-sm font-semibold text-texto">{titulo}</h2>
            )}
            {descripcion && (
              <p className="mt-0.5 text-xs text-suave">{descripcion}</p>
            )}
          </div>
          {accion}
        </header>
      )}
      <div className={sinRelleno ? "pt-3" : "p-5 pt-3"}>{children}</div>
    </section>
  );
}

export type Tono = "neutro" | "marca" | "ok" | "aviso" | "alerta";

const TONOS: Record<Tono, string> = {
  neutro: "bg-sutil text-suave",
  marca: "bg-marca-suave text-marca-texto",
  ok: "bg-ok-suave text-ok",
  aviso: "bg-aviso-suave text-aviso",
  alerta: "bg-alerta-suave text-alerta",
};

/** Una cifra destacada con su etiqueta. */
export function Indicador({
  etiqueta,
  valor,
  detalle,
  icono: Icono,
  tono = "marca",
}: {
  etiqueta: string;
  valor: ReactNode;
  detalle?: ReactNode;
  icono?: LucideIcon;
  tono?: Tono;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-borde bg-superficie p-4 shadow-xs">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-[13px] text-suave">{etiqueta}</p>
        {Icono && (
          <span
            className={`inline-flex size-7 shrink-0 items-center justify-center rounded-md ${TONOS[tono]}`}
          >
            <Icono size={15} aria-hidden />
          </span>
        )}
      </div>
      <p className="cifra mt-2 truncate text-2xl font-semibold tracking-tight">
        {valor}
      </p>
      {detalle && <p className="mt-1 text-xs text-suave">{detalle}</p>}
    </div>
  );
}

/** Etiqueta chica de estado. */
export function Insignia({
  tono = "neutro",
  children,
}: {
  tono?: Tono;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${TONOS[tono]}`}
    >
      {children}
    </span>
  );
}

/** Titulo de pantalla con su bajada y sus acciones. */
export function EncabezadoDePagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: ReactNode;
  descripcion?: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">
          {titulo}
        </h1>
        {descripcion && (
          <p className="mt-1 text-sm text-suave">{descripcion}</p>
        )}
      </div>
      {acciones && (
        <div className="flex flex-wrap items-center gap-2">{acciones}</div>
      )}
    </header>
  );
}

/** Lo que se ve cuando una lista no tiene nada. */
export function EstadoVacio({
  icono: Icono,
  titulo,
  texto,
  accion,
}: {
  icono: LucideIcon;
  titulo: string;
  texto?: string;
  accion?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <span className="mb-1 inline-flex size-10 items-center justify-center rounded-full bg-sutil text-suave">
        <Icono size={18} aria-hidden />
      </span>
      <p className="text-sm font-medium">{titulo}</p>
      {texto && <p className="max-w-sm text-sm text-suave">{texto}</p>}
      {accion && <div className="mt-2">{accion}</div>}
    </div>
  );
}

/** Mensaje de error dentro de una pantalla. */
export function Alerta({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-alerta/25 bg-alerta-suave px-3 py-2 text-sm text-alerta"
    >
      {children}
    </p>
  );
}

/** Bloque gris que late mientras carga. */
export function Esqueleto({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`esqueleto ${className}`} />;
}
