"use client";

import { Package, X } from "lucide-react";
import { useId, useState } from "react";

import { BotonIcono } from "@/componentes/ui/Boton";
import { Buscador } from "@/componentes/ui/Controles";
import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import { consulta, type Pagina } from "@/lib/api";
import { numero } from "@/lib/formato";
import { useConsulta, useDemora } from "@/lib/ganchos";

export type ProductoElegido = {
  id: number;
  nombre: string;
  codigo_barra: string | null;
  stock_actual: number;
  precio_costo: string | null;
};

/** Busca y elige un producto del catalogo, con el stock a la vista. */
export function ElegirProducto({
  etiqueta,
  valor,
  alElegir,
  autoFocus = false,
}: {
  etiqueta: string;
  valor: ProductoElegido | null;
  alElegir: (producto: ProductoElegido | null) => void;
  autoFocus?: boolean;
}) {
  const { t, idioma } = useTextos();
  const id = useId();
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const buscado = useDemora(texto.trim(), 200);
  const { datos, alDia } = useConsulta<Pagina<ProductoElegido>>(
    buscado.length >= 1
      ? `/productos${consulta({ busqueda: buscado, limite: 8 })}`
      : null,
  );
  // Solo los resultados del texto escrito ahora, no los del anterior.
  const opciones =
    abierto && alDia && buscado === texto.trim() && buscado
      ? (datos?.items ?? [])
      : [];

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium">
        {etiqueta}
      </label>
      {valor ? (
        <div className="flex h-9 items-center justify-between gap-2 rounded-lg border border-borde bg-sutil/60 pr-1 pl-3 text-sm">
          <span className="flex min-w-0 items-center gap-2">
            <Package size={15} className="shrink-0 text-suave" aria-hidden />
            <span className="truncate">{valor.nombre}</span>
            <span className="shrink-0 text-xs text-suave">
              {formatear(t.disponibles, {
                n: numero(valor.stock_actual, idioma),
              })}
            </span>
          </span>
          <BotonIcono
            id={id}
            etiqueta={t.quitar}
            icono={X}
            onClick={() => alElegir(null)}
          />
        </div>
      ) : (
        <div className="relative">
          <Buscador
            id={id}
            autoFocus={autoFocus}
            placeholder={t.buscarProductoLista}
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setAbierto(true);
            }}
            onFocus={() => setAbierto(true)}
            onBlur={() => setTimeout(() => setAbierto(false), 150)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (opciones[0]) {
                  alElegir(opciones[0]);
                  setTexto("");
                }
              }
            }}
          />
          {opciones.length > 0 && (
            <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-borde bg-superficie py-1 shadow-flotante">
              {opciones.map((opcion) => (
                <li key={opcion.id}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      alElegir(opcion);
                      setTexto("");
                      setAbierto(false);
                    }}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-sutil"
                  >
                    <span className="truncate">{opcion.nombre}</span>
                    <span className="cifra shrink-0 text-xs text-suave">
                      {numero(opcion.stock_actual, idioma)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
