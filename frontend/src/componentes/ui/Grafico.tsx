"use client";

export type Punto = { etiqueta: string; valor: number; detalle: string };

/**
 * Columnas verticales para una serie en el tiempo.
 *
 * Esta hecho con cajas y no con una libreria de graficos: son unas
 * decenas de barras, y asi pesa nada, respeta el tema oscuro y cada
 * barra se lee con el lector de pantalla.
 */
export function GraficoDeBarras({
  puntos,
  etiquetaDeEje,
  alto = "h-48",
}: {
  puntos: Punto[];
  etiquetaDeEje: (valor: number) => string;
  alto?: string;
}) {
  const maximo = Math.max(...puntos.map((p) => p.valor), 0);
  const tope = maximo > 0 ? maximo : 1;
  // Con muchas barras no entran todas las fechas: se muestra una cada
  // tantas, siempre incluida la ultima.
  const cada = Math.max(1, Math.ceil(puntos.length / 8));

  return (
    <figure className="flex flex-col gap-2">
      <div className={`relative ${alto}`}>
        {[1, 0.5, 0].map((nivel) => (
          <div
            key={nivel}
            className="absolute inset-x-0 flex items-center gap-2"
            style={{ bottom: `${nivel * 100}%` }}
            aria-hidden
          >
            <span className="w-14 shrink-0 translate-y-1/2 pr-1 text-right text-[11px] text-suave tabular-nums">
              {nivel > 0 ? etiquetaDeEje(tope * nivel) : ""}
            </span>
            <span className="flex-1 translate-y-1/2 border-t border-dashed border-borde" />
          </div>
        ))}
        <ul className="absolute inset-y-0 right-0 left-16 flex items-end justify-center gap-[3px]">
          {puntos.map((punto) => (
            <li
              key={punto.etiqueta}
              className="group relative flex h-full max-w-14 flex-1 items-end"
            >
              <span className="sr-only">
                {punto.etiqueta}: {punto.detalle}
              </span>
              <div
                aria-hidden
                className="w-full rounded-t-[3px] bg-marca/75 transition-colors group-hover:bg-marca"
                style={{
                  height: `${(punto.valor / tope) * 100}%`,
                  minHeight: punto.valor > 0 ? 2 : 0,
                }}
              />
              <div
                aria-hidden
                className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 rounded-md bg-texto px-2 py-1 text-[11px] whitespace-nowrap text-fondo group-hover:block"
              >
                {punto.etiqueta} · {punto.detalle}
              </div>
            </li>
          ))}
        </ul>
      </div>
      <div className="ml-16 flex justify-center gap-[3px]" aria-hidden>
        {puntos.map((punto, i) => (
          <span
            key={punto.etiqueta}
            className="max-w-14 flex-1 text-center text-[11px] whitespace-nowrap text-suave"
          >
            {i % cada === 0 || i === puntos.length - 1 ? punto.etiqueta : ""}
          </span>
        ))}
      </div>
    </figure>
  );
}

/** Ranking con barras horizontales proporcionales al primero. */
export function BarrasHorizontales({
  filas,
}: {
  filas: {
    clave: string | number;
    etiqueta: string;
    valor: number;
    texto: string;
  }[];
}) {
  const maximo = Math.max(...filas.map((f) => f.valor), 0) || 1;
  return (
    <ul className="flex flex-col gap-3">
      {filas.map((fila) => (
        <li key={fila.clave} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate">{fila.etiqueta}</span>
            <span className="cifra shrink-0 text-suave">{fila.texto}</span>
          </div>
          <div
            className="h-1.5 overflow-hidden rounded-full bg-sutil"
            aria-hidden
          >
            <div
              className="h-full rounded-full bg-marca/75"
              style={{ width: `${(fila.valor / maximo) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
