import { LoaderCircle, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

type Variante = "primario" | "secundario" | "fantasma" | "peligro";
type Tamano = "sm" | "md" | "lg";

const VARIANTES: Record<Variante, string> = {
  primario:
    "bg-marca text-sobre-marca shadow-sm hover:bg-marca-hover disabled:hover:bg-marca",
  secundario:
    "border border-borde bg-superficie text-texto shadow-xs hover:bg-sutil",
  fantasma: "text-suave hover:bg-sutil hover:text-texto",
  peligro: "bg-alerta text-white shadow-sm hover:opacity-90",
};

const TAMANOS: Record<Tamano, string> = {
  sm: "h-8 gap-1.5 rounded-md px-2.5 text-[13px]",
  md: "h-9 gap-2 rounded-lg px-3.5 text-sm",
  lg: "h-11 gap-2 rounded-lg px-5 text-[15px]",
};

/** Clases de boton, tambien para enlaces que se ven como botones. */
export function clasesDeBoton(
  variante: Variante = "secundario",
  tamano: Tamano = "md",
  extra = "",
) {
  return `inline-flex shrink-0 items-center justify-center font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${TAMANOS[tamano]} ${extra}`;
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante;
  tamano?: Tamano;
  icono?: LucideIcon;
  cargando?: boolean;
};

export function Boton({
  variante = "secundario",
  tamano = "md",
  icono: Icono,
  cargando = false,
  className = "",
  children,
  disabled,
  type = "button",
  ...resto
}: Props) {
  const medida = tamano === "sm" ? 14 : 16;
  return (
    <button
      type={type}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      className={clasesDeBoton(variante, tamano, className)}
      {...resto}
    >
      {cargando ? (
        <LoaderCircle size={medida} className="animate-spin" aria-hidden />
      ) : (
        Icono && <Icono size={medida} aria-hidden />
      )}
      {children}
    </button>
  );
}

/** Boton de solo icono: la etiqueta la leen el lector y el tooltip. */
export function BotonIcono({
  etiqueta,
  icono: Icono,
  variante = "fantasma",
  className = "",
  type = "button",
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  etiqueta: string;
  icono: LucideIcon;
  variante?: Variante;
}) {
  return (
    <button
      type={type}
      aria-label={etiqueta}
      title={etiqueta}
      className={`inline-flex size-8 shrink-0 items-center justify-center rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTES[variante]} ${className}`}
      {...resto}
    >
      <Icono size={16} aria-hidden />
    </button>
  );
}
