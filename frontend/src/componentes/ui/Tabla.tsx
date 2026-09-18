"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import { numero } from "@/lib/formato";

import { BotonIcono } from "./Boton";
import { Esqueleto } from "./Superficie";

export type Columna = {
  texto: string;
  alinear?: "izquierda" | "derecha" | "centro";
  oculta?: "sm" | "md" | "lg";
  sr?: boolean;
};

const ALINEAR = {
  izquierda: "text-left",
  derecha: "text-right",
  centro: "text-center",
};

// Columnas que se esconden en pantallas chicas, para que la tabla no
// obligue a desplazarse de costado en un celular.
const OCULTA = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

export function clasesDeCelda(
  alinear: Columna["alinear"] = "izquierda",
  oculta?: Columna["oculta"],
) {
  return `${ALINEAR[alinear]} ${oculta ? OCULTA[oculta] : ""}`;
}

/**
 * Tabla de datos. Mientras carga sin datos previos muestra filas
 * grises; sin filas, el estado vacio que se le pase.
 */
export function Tabla({
  columnas,
  cargando = false,
  vacia = false,
  estadoVacio,
  children,
}: {
  columnas: Columna[];
  cargando?: boolean;
  vacia?: boolean;
  estadoVacio?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-borde">
            {columnas.map((columna, i) => (
              <th
                key={i}
                scope="col"
                className={`px-4 py-2.5 text-xs font-medium whitespace-nowrap text-suave first:pl-5 last:pr-5 ${clasesDeCelda(columna.alinear, columna.oculta)}`}
              >
                {columna.sr ? (
                  <span className="sr-only">{columna.texto}</span>
                ) : (
                  columna.texto
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody
          className={`divide-y divide-borde transition-opacity ${cargando && !vacia ? "opacity-60" : ""}`}
        >
          {cargando && vacia
            ? Array.from({ length: 5 }, (_, fila) => (
                <tr key={fila}>
                  {columnas.map((columna, i) => (
                    <td
                      key={i}
                      className={`px-4 py-3 first:pl-5 last:pr-5 ${clasesDeCelda(columna.alinear, columna.oculta)}`}
                    >
                      <Esqueleto className="h-4 w-full max-w-32" />
                    </td>
                  ))}
                </tr>
              ))
            : children}
        </tbody>
      </table>
      {!cargando && vacia && estadoVacio}
    </div>
  );
}

/** Fila de tabla; si tiene accion, toda la fila es cliqueable. */
export function Fila({
  children,
  alElegir,
  apagada = false,
}: {
  children: ReactNode;
  alElegir?: () => void;
  apagada?: boolean;
}) {
  return (
    <tr
      onClick={alElegir}
      className={`group transition-colors hover:bg-sutil/60 ${alElegir ? "cursor-pointer" : ""} ${apagada ? "text-suave" : ""}`}
    >
      {children}
    </tr>
  );
}

export function Celda({
  children,
  alinear,
  oculta,
  className = "",
}: {
  children?: ReactNode;
  alinear?: Columna["alinear"];
  oculta?: Columna["oculta"];
  className?: string;
}) {
  return (
    <td
      className={`px-4 py-3 align-middle first:pl-5 last:pr-5 ${clasesDeCelda(alinear, oculta)} ${className}`}
    >
      {children}
    </td>
  );
}

/** Pie con el total de resultados y el paso de pagina. */
export function Paginacion({
  pagina,
  total,
  limite,
  alCambiar,
}: {
  pagina: number;
  total: number;
  limite: number;
  alCambiar: (pagina: number) => void;
}) {
  const { t, idioma } = useTextos();
  const paginas = Math.max(1, Math.ceil(total / limite));
  return (
    <div className="flex items-center justify-between gap-3 border-t border-borde px-5 py-2.5 text-xs text-suave">
      <span>{formatear(t.resultados, { n: numero(total, idioma) })}</span>
      <div className="flex items-center gap-1">
        <span className="mr-2">
          {formatear(t.paginaDe, { p: pagina, n: paginas })}
        </span>
        <BotonIcono
          etiqueta={t.anterior}
          icono={ChevronLeft}
          disabled={pagina <= 1}
          onClick={() => alCambiar(pagina - 1)}
        />
        <BotonIcono
          etiqueta={t.siguiente}
          icono={ChevronRight}
          disabled={pagina >= paginas}
          onClick={() => alCambiar(pagina + 1)}
        />
      </div>
    </div>
  );
}
